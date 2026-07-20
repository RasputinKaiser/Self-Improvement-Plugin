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
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sips_paths import goal_state_path

STATE_PATH = goal_state_path()

try:
    from sips_runtime.adapters import MODES, import_legacy
    from sips_runtime.api import RuntimeAPI
    from sips_runtime.controller import RuntimeController
    from sips_runtime.dag import compile_dag
except ImportError:  # pragma: no cover - direct package/script execution fallback
    from scripts.sips_runtime.adapters import MODES, import_legacy
    from scripts.sips_runtime.api import RuntimeAPI
    from scripts.sips_runtime.controller import RuntimeController
    from scripts.sips_runtime.dag import compile_dag


RUNTIME_MODE_ENV = "SIPS_RUNTIME_MODE"
RUNTIME_SCHEMA = "sips.runtime.legacy-projection.v1"


def resolve_mode(mode: str | None = None) -> str:
    """Resolve compatibility mode, with legacy as the stable default."""
    selected = mode if mode is not None else os.environ.get(RUNTIME_MODE_ENV, "legacy")
    selected = str(selected).strip().lower() or "legacy"
    if selected not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    return selected


def _legacy_source(state: Mapping[str, Any]) -> dict[str, Any]:
    """Exclude compatibility metadata from the legacy source hash."""
    return {key: deepcopy(value) for key, value in state.items() if key != "runtime"}


def _runtime_tasks(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    subtasks = state.get("subtasks", [])
    tasks: list[dict[str, Any]] = []
    for ordinal, item in enumerate(subtasks):
        if not isinstance(item, Mapping):
            continue
        task_id = str(item.get("id") or f"st-{ordinal + 1}")
        tasks.append(
            {
                "id": task_id,
                "objective": str(state.get("objective", "")),
                "description": str(item.get("description", "")),
                "depends_on": [],
                "estimated_tokens": 1,
                "insertion_ordinal": ordinal,
                "metadata": {"legacy_id": task_id},
            }
        )
    # A goal with no explicit subtasks still compiles as a one-node runtime
    # plan, while preserving the legacy empty-subtask representation.
    if not tasks and str(state.get("objective", "")).strip():
        tasks.append(
            {
                "id": "goal",
                "objective": str(state.get("objective", "")),
                "description": str(state.get("objective", "")),
                "depends_on": [],
                "estimated_tokens": 1,
                "insertion_ordinal": 0,
                "metadata": {"legacy_id": "goal"},
            }
        )
    return tasks


def legacy_runtime_projection(state: Mapping[str, Any], *, mode: str = "legacy") -> dict[str, Any]:
    """Read and compile a legacy goal state without writing to its source."""
    selected = resolve_mode(mode)
    source = _legacy_source(state)
    imported = import_legacy(source, mode=selected, namespace="goal")
    tasks = _runtime_tasks(source)
    graph: dict[str, Any] = {"ok": False, "error": "legacy goal has no objective"}
    if tasks:
        try:
            graph = {"ok": True, **compile_dag(tasks).to_dict()}
        except (TypeError, ValueError) as exc:
            graph = {"ok": False, "error": str(exc), "task_count": len(tasks)}
    return {
        "schema": RUNTIME_SCHEMA,
        "kind": "goal_state",
        "mode": selected,
        "raw_hash": imported["raw_hash"],
        "migration_id": imported["migration_id"],
        "record_count": imported["record_count"],
        "read_only": True,
        "write_performed": False,
        "graph": graph,
        "tasks": tasks,
    }


def _runtime_plan(state: Mapping[str, Any], projection: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Create a runtime goal plan; execution handoff is intentionally closed."""
    if mode not in {"dual", "runtime"}:
        return {}
    legacy_id = str(state.get("id") or uuid.uuid4().hex[:10])
    run_id = f"goal-{legacy_id}"
    try:
        controller = RuntimeController()
        runtime_state = controller.create(
            {
                "run_id": run_id,
                "objective": str(state.get("objective", "")),
                "workspace_root": str(Path.cwd()),
                "metadata": {
                    "legacy_mode": mode,
                    "legacy_goal_id": legacy_id,
                    "migration_id": projection.get("migration_id", ""),
                    "raw_hash": projection.get("raw_hash", ""),
                },
                "tasks": projection.get("tasks", []),
            },
            idempotency_key=f"legacy-plan:{legacy_id}",
            expected_revision=0,
        )
        receipt = RuntimeAPI(controller=controller).read("receipt", {"run_id": run_id})
        return {
            "run_id": run_id,
            "authority": "runtime-plan",
            "status": runtime_state.get("status", "pending"),
            "receipt": receipt.get("data", receipt),
            "execution": "blocked",
            "blocker": "legacy goal commands lack runtime lease/fencing transitions; legacy state remains authoritative",
        }
    except Exception as exc:
        return {
            "run_id": None,
            "authority": "legacy",
            "execution": "blocked",
            "blocker": f"runtime plan transition failed closed: {type(exc).__name__}: {exc}",
        }


def attach_runtime(state: Mapping[str, Any], *, mode: str | None = None, create_runtime: bool = False) -> dict[str, Any]:
    """Attach a read-only projection and optional runtime plan to a state copy."""
    prior = state.get("runtime") if isinstance(state.get("runtime"), Mapping) else {}
    selected = resolve_mode(mode or prior.get("mode"))
    projected = deepcopy(dict(state))
    if selected == "legacy":
        projected.pop("runtime", None)
        return projected
    projection = legacy_runtime_projection(projected, mode=selected)
    runtime = {
        "mode": selected,
        "raw_hash": projection["raw_hash"],
        "migration_id": projection["migration_id"],
        "projection": projection,
        "run_id": prior.get("run_id"),
        "authority": prior.get("authority", "legacy"),
        "execution": prior.get("execution", "shadow"),
        "blocker": prior.get("blocker"),
    }
    if create_runtime and selected in {"dual", "runtime"} and not runtime.get("run_id"):
        runtime.update(_runtime_plan(projected, projection, selected))
    elif runtime.get("run_id") and selected in {"dual", "runtime"}:
        runtime["execution"] = "blocked"
        runtime["blocker"] = runtime.get("blocker") or "legacy goal mutation is not replayed into the runtime plan"
    projected["runtime"] = runtime
    return projected


def load() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save(state: dict, *, mode: str | None = None, create_runtime: bool = False) -> dict:
    """Persist state, enriching only explicitly selected compatibility modes."""
    state_runtime = state.get("runtime")
    prior_mode = state_runtime.get("mode") if isinstance(state_runtime, Mapping) else None
    selected = resolve_mode(mode or prior_mode)
    projected = attach_runtime(state, mode=selected, create_runtime=create_runtime)
    state.clear()
    state.update(projected)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))
    return state


def _response_with_runtime(response: dict[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    """Expose transition mode/blocker without changing legacy response keys."""
    runtime = state.get("runtime")
    if isinstance(runtime, Mapping):
        response["mode"] = runtime.get("mode", "legacy")
        response["runtime"] = runtime
    return response


def cmd_set(objective: str, mode: str | None = None) -> None:
    selected = resolve_mode(mode)
    state = {
        "objective": objective,
        "status": "active",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "turnCount": 0,
        "subtasks": [],
    }
    if selected in {"dual", "runtime"}:
        state["id"] = uuid.uuid4().hex[:10]
    save(state, mode=selected, create_runtime=True)
    response = {"ok": True, "objective": objective, "status": "active", "mode": selected}
    if state.get("runtime"):
        response["runtime"] = state["runtime"]
    print(json.dumps(response))


def cmd_selfloop_set(focus: str, mode: str | None = None) -> None:
    selected = resolve_mode(mode)
    focus = focus.strip()
    objective = (
        "Continuously improve SIPS and the agent operating it through "
        "evidence-backed, verified iterations. Work only on reasoning quality, "
        "tool reliability, memory and recall, verification, context efficiency, "
        "autonomy, or self-correction."
    )
    if focus:
        objective += f" Focus: {focus}"
    state = {
        "objective": objective,
        "status": "active",
        "mode": "selfloop",
        "focus": focus,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "turnCount": 0,
        "cycleCount": 0,
        "plateauStreak": 0,
        "cycleHistory": [],
        "subtasks": [],
    }
    if selected in {"dual", "runtime"}:
        state["id"] = uuid.uuid4().hex[:10]
    save(state, mode=selected, create_runtime=True)
    response = {
        "ok": True,
        "objective": objective,
        "status": "active",
        "mode": "selfloop",
        "focus": focus,
    }
    if state.get("runtime"):
        response["runtime"] = state["runtime"]
    print(json.dumps(response))


def cmd_selfloop_record(outcome: str, summary: str) -> None:
    if outcome not in {"improved", "plateau", "blocked"}:
        print(json.dumps({"ok": False, "error": f"invalid selfloop outcome: {outcome}"}))
        sys.exit(2)
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    if state.get("mode") != "selfloop":
        print(json.dumps({"ok": False, "error": "active goal is not a selfloop"}))
        sys.exit(1)
    summary = summary.strip()
    if not summary:
        print(json.dumps({"ok": False, "error": "cycle summary is required"}))
        sys.exit(2)

    recorded_at = datetime.now(timezone.utc).isoformat()
    state["cycleCount"] = int(state.get("cycleCount", 0)) + 1
    state["plateauStreak"] = int(state.get("plateauStreak", 0)) + 1 if outcome == "plateau" else 0
    cycle = {
        "cycle": state["cycleCount"],
        "outcome": outcome,
        "summary": summary,
        "recordedAt": recorded_at,
    }
    history = list(state.get("cycleHistory") or [])
    history.append(cycle)
    state["cycleHistory"] = history[-25:]
    state["lastCycle"] = cycle
    save(state)
    print(json.dumps({
        "ok": True,
        "mode": "selfloop",
        "cycleCount": state["cycleCount"],
        "plateauStreak": state["plateauStreak"],
        "cycle": cycle,
    }))


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


def cmd_add_subtask(description: str, mode: str | None = None) -> None:
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
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "subtask": st}, state)))


def _find_subtask(state: dict, subtask_id: str):
    for st in state.get("subtasks", []):
        if st.get("id") == subtask_id:
            return st
    return None


def cmd_complete_subtask(subtask_id: str, mode: str | None = None) -> None:
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
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "subtask": st}, state)))


def cmd_fail_subtask(subtask_id: str, reason: str, mode: str | None = None) -> None:
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
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "subtask": st}, state)))


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


def cmd_reset_subtasks(mode: str | None = None) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["subtasks"] = []
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "cleared": True}, state)))


def cmd_status(mode: str | None = None) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state_runtime = state.get("runtime")
    prior_mode = state_runtime.get("mode") if isinstance(state_runtime, Mapping) else None
    selected = resolve_mode(mode or prior_mode)
    # Status must stay read-only: projection may compile, but cannot create a
    # runtime controller plan as a side effect.
    print(json.dumps(attach_runtime(state, mode=selected, create_runtime=False), indent=2))


def cmd_complete(mode: str | None = None) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "complete"
    state["completedAt"] = datetime.now(timezone.utc).isoformat()
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime(
        {"ok": True, "status": "complete", "objective": state.get("objective", "?")}, state
    )))


def cmd_clear() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print(json.dumps({"ok": True, "cleared": True}))


def cmd_pause(mode: str | None = None) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "paused"
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "status": "paused"}, state)))


def cmd_resume(mode: str | None = None) -> None:
    state = load()
    if state is None:
        print(json.dumps({"ok": False, "error": "no goal set"}))
        sys.exit(1)
    state["status"] = "active"
    save(state, mode=mode)
    print(json.dumps(_response_with_runtime({"ok": True, "status": "active"}, state)))


def cmd_increment_turn(mode: str | None = None) -> None:
    state = load()
    if state is None:
        return
    state["turnCount"] = state.get("turnCount", 0) + 1
    save(state, mode=mode)


def cmd_is_active() -> None:
    state = load()
    if state and state.get("status") == "active":
        sys.exit(0)
    else:
        sys.exit(1)


def _parse_mode(argv: list[str]) -> tuple[list[str], str | None]:
    """Accept --mode before or after the legacy command without changing it."""
    cleaned: list[str] = []
    mode: str | None = None
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--mode":
            if index + 1 >= len(argv):
                raise ValueError("--mode requires one of: " + ", ".join(MODES))
            mode = argv[index + 1]
            index += 2
            continue
        if value.startswith("--mode="):
            mode = value.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(value)
        index += 1
    return cleaned, mode


def main(argv: list[str] | None = None):
    try:
        args, mode = _parse_mode(list(sys.argv[1:] if argv is None else argv))
        selected_mode = resolve_mode(mode)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    if not args or args[0] in ("-h", "--help"):
        print("usage: goal_state.py [--mode legacy|shadow|dual|runtime] {set|selfloop-set|selfloop-record|status|complete|clear|pause|resume|increment-turn|is-active|add-subtask|complete-subtask|fail-subtask|next|progress|reset-subtasks} [args]")
        print("\nSubtask DAG: add-subtask, complete-subtask, fail-subtask, next, progress, reset-subtasks")
        return 0 if args and args[0] in ("-h", "--help") else 2

    cmd = args[0]
    if cmd == "set":
        objective = " ".join(args[1:]).strip()
        if not objective:
            print("usage: goal_state.py set \"<objective>\"", file=sys.stderr)
            return 2
        cmd_set(objective, selected_mode)
    elif cmd == "selfloop-set":
        cmd_selfloop_set(" ".join(args[1:]), selected_mode)
    elif cmd == "selfloop-record":
        if len(args) < 3:
            print("usage: goal_state.py selfloop-record {improved|plateau|blocked} \"<summary>\"", file=sys.stderr)
            return 2
        cmd_selfloop_record(args[1], " ".join(args[2:]))
    elif cmd == "status":
        cmd_status(mode)
    elif cmd == "complete":
        cmd_complete(mode)
    elif cmd == "clear":
        cmd_clear()
    elif cmd == "pause":
        cmd_pause(mode)
    elif cmd == "resume":
        cmd_resume(mode)
    elif cmd == "increment-turn":
        cmd_increment_turn(mode)
    elif cmd == "is-active":
        cmd_is_active()
    elif cmd == "add-subtask":
        description = " ".join(args[1:]).strip()
        if not description:
            print("usage: goal_state.py add-subtask \"<description>\"", file=sys.stderr)
            return 2
        cmd_add_subtask(description, mode)
    elif cmd == "complete-subtask":
        if len(args) < 2:
            print("usage: goal_state.py complete-subtask <id>", file=sys.stderr)
            return 2
        cmd_complete_subtask(args[1], mode)
    elif cmd == "fail-subtask":
        if len(args) < 3:
            print("usage: goal_state.py fail-subtask <id> \"<reason>\"", file=sys.stderr)
            return 2
        cmd_fail_subtask(args[1], " ".join(args[2:]).strip(), mode)
    elif cmd == "next":
        cmd_next()
    elif cmd == "progress":
        cmd_progress()
    elif cmd == "reset-subtasks":
        cmd_reset_subtasks(mode)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
