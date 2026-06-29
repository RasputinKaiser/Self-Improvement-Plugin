#!/usr/bin/env python3
"""Goal state manager for the /goal RALPH loop.

Reads/writes ~/.ncode/goal_state.json. Provides:
  set <objective>     — create or replace the active goal
  status              — print current goal state
  complete            — mark goal as complete
  clear               — delete goal state (stop loop)
  pause               — set status to paused
  resume              — set status to active
  is-active           — exit 0 if goal is active, 1 otherwise (for hook use)

Usage:
  goal_state.py set "Fix the fizzbuzz bug"
  goal_state.py status
  goal_state.py complete
  goal_state.py clear
  goal_state.py is-active
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path.home() / ".ncode" / "goal_state.json"


def load() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def cmd_set(objective: str) -> None:
    state = {
        "objective": objective,
        "status": "active",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "turnCount": 0,
    }
    save(state)
    print(json.dumps({"ok": True, "objective": objective, "status": "active"}))


def cmd_status() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    print(json.dumps(state, indent=2))


def cmd_complete() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "complete"
    state["completedAt"] = datetime.now(timezone.utc).isoformat()
    save(state)
    print(json.dumps({"ok": True, "status": "complete", "objective": state.get("objective", "?")}))


def cmd_clear() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print(json.dumps({"ok": True, "cleared": True}))


def cmd_pause() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "paused"
    save(state)
    print(json.dumps({"ok": True, "status": "paused"}))


def cmd_resume() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "active"
    save(state)
    print(json.dumps({"ok": True, "status": "active"}))


def cmd_increment_turn() -> None:
    state = load()
    if state is None:
        return
    state["turnCount"] = state.get("turnCount", 0) + 1
    save(state)


def cmd_is_active() -> None:
    state = load()
    if state and state.get("status") == "active":
        sys.exit(0)
    else:
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("usage: goal_state.py {set|status|complete|clear|pause|resume|increment-turn|is-active} [objective]")
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "set":
        objective = " ".join(sys.argv[2:]).strip()
        if not objective:
            print("usage: goal_state.py set \"<objective>\"", file=sys.stderr)
            sys.exit(2)
        cmd_set(objective)
    elif cmd == "status":
        cmd_status()
    elif cmd == "complete":
        cmd_complete()
    elif cmd == "clear":
        cmd_clear()
    elif cmd == "pause":
        cmd_pause()
    elif cmd == "resume":
        cmd_resume()
    elif cmd == "increment-turn":
        cmd_increment_turn()
    elif cmd == "is-active":
        cmd_is_active()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()