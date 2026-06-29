#!/usr/bin/env python3
"""Goal state manager for the /goal RALPH loop.

Reads/writes ~/.ncode/goal_state.json. Provides:
  set <objective>               — create or replace the active goal
  status                       — print current goal state
  complete                     — mark goal as complete
  clear                        — delete goal state (stop loop)
  pause                        — set status to paused
  resume                       — set status to active
  is-active                    — exit 0 if goal is active, 1 otherwise (for hook use)
  increment-turn               — bump turnCount

Subtask DAG (Tier 5 capability — works across crashes/restarts/compaction):
  add-subtask "<description>"  — append a pending subtask
  complete-subtask <id>        — mark subtask done, advance pointer
  fail-subtask <id> "<reason>" — mark subtask failed
  next                         — print the current (pending) subtask description
  progress                     — print "N/M subtasks done; current: <desc>"
  reset-subtasks               — clear all subtasks but keep the objective

Subtask format in state file:
  "subtasks": [
    {"id": "st-1", "description": "...", "status": "pending|done|failed",
     "addedAt": "...", "completedAt": null}
  ]

The current subtask is the first one with status="pending" (in insertion order).
The `next` command prints it; `complete-subtask` marks it done and the next
`next` call yields the following pending one.

Usage:
  goal_state.py set "Fix the fizzbuzz bug"
  goal_state.py add-subtask "Write failing test"
  goal_state.py add-subtask "Implement fix"
  goal_state.py next          # → "Write failing test"
  goal_state.py complete-subtask st-1
  goal_state.py next          # → "Implement fix"
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
        "subtasks": [],
    }
    save(state)
    print(json.dumps({"ok": True, "objective": objective, "status": "active"}))


def _ensure_subtasks(state: dict) -> list:
    if "subtasks" not in state:
        state["subtasks"] = []
    return state["subtasks"]


def _next_id(subtasks: list) -> str:
    if not subtasks:
        return "st-1"
    max_n = 0
    for st in subtasks:
        sid = st.get("id", "st-0")
        if sid.startswith("st-"):
            try:
                max_n = max(max_n, int(sid[3:]))
            except ValueError:
                pass
    return f"st-{max_n + 1}"


def cmd_add_subtask(description: str) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    subtasks = _ensure_subtasks(state)
    st = {
        "id": _next_id(subtasks),
        "description": description,
        "status": "pending",
        "addedAt": datetime.now(timezone.utc).isoformat(),
        "completedAt": None,
    }
    subtasks.append(st)
    save(state)
    print(json.dumps({"ok": True, "subtask": st}))


def _find_subtask(state: dict, subtask_id: str):
    for st in state.get("subtasks", []):
        if st.get("id") == subtask_id:
            return st
    return None


def cmd_complete_subtask(subtask_id: str) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    st = _find_subtask(state, subtask_id)
    if st is None:
        print(json.dumps({"ok": False, "error": f"subtask not found: {subtask_id}"}))
        sys.exit(1)
    st["status"] = "done"
    st["completedAt"] = datetime.now(timezone.utc).isoformat()
    save(state)
    print(json.dumps({"ok": True, "subtask": st}))


def cmd_fail_subtask(subtask_id: str, reason: str) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    st = _find_subtask(state, subtask_id)
    if st is None:
        print(json.dumps({"ok": False, "error": f"subtask not found: {subtask_id}"}))
        sys.exit(1)
    st["status"] = "failed"
    st["completedAt"] = datetime.now(timezone.utc).isoformat()
    st["failureReason"] = reason
    save(state)
    print(json.dumps({"ok": True, "subtask": st}))


def _current_pending(state: dict):
    for st in state.get("subtasks", []):
        if st.get("status") == "pending":
            return st
    return None


def cmd_next() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    st = _current_pending(state)
    if st is None:
        done = sum(1 for s in state.get("subtasks", []) if s.get("status") == "done")
        total = len(state.get("subtasks", []))
        print(json.dumps({"ok": True, "allDone": True,
                          "summary": f"all {total} subtasks done"}))
    else:
        print(json.dumps({"ok": True, "subtask": st}))


def cmd_progress() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    subtasks = state.get("subtasks", [])
    done = sum(1 for s in subtasks if s.get("status") == "done")
    failed = sum(1 for s in subtasks if s.get("status") == "failed")
    pending = sum(1 for s in subtasks if s.get("status") == "pending")
    total = len(subtasks)
    current = _current_pending(state)
    current_desc = current["description"][:80] if current else "(none — all done)"
    print(json.dumps({
        "ok": True,
        "summary": f"{done}/{total} subtasks done; {failed} failed; {pending} pending",
        "current": current_desc,
        "subtasks": subtasks,
    }, indent=2))


def cmd_reset_subtasks() -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["subtasks"] = []
    save(state)
    print(json.dumps({"ok": True, "cleared": True}))


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
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("usage: goal_state.py {set|status|complete|clear|pause|resume|increment-turn|is-active|add-subtask|complete-subtask|fail-subtask|next|progress|reset-subtasks} [args]")
        print("\nSubtask DAG: add-subtask, complete-subtask, fail-subtask, next, progress, reset-subtasks")
        sys.exit(0 if sys.argv[1:] and sys.argv[1] in ("-h", "--help") else 2)

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
    elif cmd == "add-subtask":
        description = " ".join(sys.argv[2:]).strip()
        if not description:
            print("usage: goal_state.py add-subtask \"<description>\"", file=sys.stderr)
            sys.exit(2)
        cmd_add_subtask(description)
    elif cmd == "complete-subtask":
        if len(sys.argv) < 3:
            print("usage: goal_state.py complete-subtask <id>", file=sys.stderr)
            sys.exit(2)
        cmd_complete_subtask(sys.argv[2])
    elif cmd == "fail-subtask":
        if len(sys.argv) < 4:
            print("usage: goal_state.py fail-subtask <id> \"<reason>\"", file=sys.stderr)
            sys.exit(2)
        cmd_fail_subtask(sys.argv[2], " ".join(sys.argv[3:]).strip())
    elif cmd == "next":
        cmd_next()
    elif cmd == "progress":
        cmd_progress()
    elif cmd == "reset-subtasks":
        cmd_reset_subtasks()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()