#!/usr/bin/env python3
"""fan_out.py — multi-agent fan-out coordinator (Tier 5 #4).

Spawns N fan-out agents in parallel via the NCode Agent tool, each given a
distinct slice of a decomposable parent task. Merges outputs, surfaces
disagreements, and captures one lesson per slice to Memory Fabric.

CLI:
  fan_out.py --parent "<objective>" --slices "<slice1>" "<slice2>" "<slice3>"
  fan_out.py --parent "..." --slices "..." --json
  fan_out.py --parent "..." --handoff-only   # write HANDOFF.md files, no spawn
  fan_out.py --list-handoffs                  # list existing handoff dirs

Writes N HANDOFF.md files under ~/.ncode/fan_out/<run_id>/slice_<i>/HANDOFF.md
capturing the parent objective + each slice's description + dependencies.
The Agent tool spawns the fan-out agent definition per slice; outputs
return as the agent's text response (parsed for SLICE/DIFF/LESSON/BLOCKED).

Output:
- ~/.ncode/fan_out/<run_id>/run.json — full state per slice (status, lesson, diff_path)
- One Memory Fabric learning-tier record per slice capturing its lesson.

This script does NOT spawn agents directly — it prepares the handoff
environment and tells the main thread what to dispatch. The main thread
(or operator) invokes the Agent tool per slice. Once agents complete,
their outputs can be replayed back into this script via --ingest.

Workflow:
  1. fan_out.py --parent ... --slices ...    # prepares handoff dirs, prints dispatch plan
  2. main thread spawns N fan-out agents (each with cwd = slice dir)
  3. fan_out.py --ingest <run_id>             # consolidates results
"""
import argparse
from copy import deepcopy
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sips_paths import harness_home

FAN_OUT_DIR = harness_home() / "fan_out"

SLICE_STATES = ("pending", "running", "done", "blocked", "failed")


from sips_memory_fabric import find_memory_fabric_cli

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
    """Resolve the compatibility mode, preserving legacy behavior by default."""
    selected = mode if mode is not None else os.environ.get(RUNTIME_MODE_ENV, "legacy")
    selected = str(selected).strip().lower() or "legacy"
    if selected not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    return selected


def _legacy_source(state: Mapping[str, Any]) -> dict[str, Any]:
    """Return only legacy fields so runtime metadata cannot hash itself."""
    return {key: deepcopy(value) for key, value in state.items() if key != "runtime"}


def _runtime_tasks(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    slices = state.get("slices", [])
    known_ids = {str(item.get("id")) for item in slices if isinstance(item, Mapping)}
    tasks: list[dict[str, Any]] = []
    for ordinal, item in enumerate(slices):
        if not isinstance(item, Mapping):
            continue
        task_id = str(item.get("id") or f"slice_{ordinal + 1}")
        raw_dependencies = item.get("dependencies", [])
        if isinstance(raw_dependencies, str):
            raw_dependencies = [raw_dependencies]
        # Legacy dependencies are often prose descriptions.  Only exact slice
        # IDs can safely become runtime edges; unknown values are retained in
        # the projection as ignored legacy metadata rather than guessed edges.
        depends_on = [str(value) for value in raw_dependencies if str(value) in known_ids]
        tasks.append(
            {
                "id": task_id,
                "objective": str(state.get("parent", "")),
                "description": str(item.get("description", "")),
                "depends_on": depends_on,
                "estimated_tokens": 1,
                "insertion_ordinal": ordinal,
                "metadata": {"legacy_id": task_id},
            }
        )
    return tasks


def legacy_runtime_projection(state: Mapping[str, Any], *, mode: str = "legacy") -> dict[str, Any]:
    """Read and compile a legacy run without mutating or controlling it."""
    selected = resolve_mode(mode)
    source = _legacy_source(state)
    imported = import_legacy(source, mode=selected, namespace="fan-out")
    tasks = _runtime_tasks(source)
    graph: dict[str, Any] = {"ok": False, "error": "no legacy slices"}
    if tasks:
        try:
            graph = {"ok": True, **compile_dag(tasks).to_dict()}
        except (TypeError, ValueError) as exc:
            graph = {"ok": False, "error": str(exc), "task_count": len(tasks)}
    return {
        "schema": RUNTIME_SCHEMA,
        "kind": "fan_out",
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
    """Create a runtime plan only when explicitly requested.

    Legacy agent responses do not carry the runtime lease/fencing contract, so
    execution handoff remains fail-closed.  The controller is authoritative for
    the compiled plan; legacy dispatch continues until a future explicit bridge.
    """
    if mode not in {"dual", "runtime"}:
        return {}
    run_id = f"fan-out-{state.get('id', uuid.uuid4().hex[:10])}"
    try:
        controller = RuntimeController()
        runtime_state = controller.create(
            {
                "run_id": run_id,
                "objective": str(state.get("parent", "")),
                "workspace_root": str(Path.cwd()),
                "metadata": {
                    "legacy_mode": mode,
                    "legacy_run_id": state.get("id", ""),
                    "migration_id": projection.get("migration_id", ""),
                    "raw_hash": projection.get("raw_hash", ""),
                },
                "tasks": projection.get("tasks", []),
            },
            idempotency_key=f"legacy-plan:{state.get('id', '')}",
            expected_revision=0,
        )
        receipt = RuntimeAPI(controller=controller).read("receipt", {"run_id": run_id})
        return {
            "run_id": run_id,
            "authority": "runtime-plan",
            "status": runtime_state.get("status", "pending"),
            "receipt": receipt.get("data", receipt),
            "execution": "blocked",
            "blocker": "legacy fan-out responses lack runtime lease/fencing metadata; legacy dispatch remains authoritative",
        }
    except Exception as exc:
        return {
            "run_id": None,
            "authority": "legacy",
            "execution": "blocked",
            "blocker": f"runtime plan transition failed closed: {type(exc).__name__}: {exc}",
        }


def attach_runtime(state: Mapping[str, Any], *, mode: str | None = None, create_runtime: bool = False) -> dict[str, Any]:
    """Attach a non-authoritative projection or a safely-created runtime plan."""
    prior_state_runtime = state.get("runtime")
    prior_mode = prior_state_runtime.get("mode") if isinstance(prior_state_runtime, Mapping) else None
    selected = resolve_mode(mode or prior_mode)
    projected = deepcopy(dict(state))
    if selected == "legacy":
        projected.pop("runtime", None)
        return projected
    projection = legacy_runtime_projection(projected, mode=selected)
    prior = projected.get("runtime") if isinstance(projected.get("runtime"), Mapping) else {}
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
    projected["runtime"] = runtime
    return projected


def cmd_prepare(parent, slices, dependencies=None, mode=None):
    """Create the run dir + write one HANDOFF.md per slice. Print dispatch plan."""
    selected_mode = resolve_mode(mode)
    run_id = uuid.uuid4().hex[:10]
    run_dir = FAN_OUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    deps = dependencies or {}
    state = {
        "id": run_id,
        "parent": parent,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "slices": [],
    }
    for i, slice_text in enumerate(slices, start=1):
        slice_dir = run_dir / f"slice_{i}"
        slice_dir.mkdir(exist_ok=True)
        slice_deps = deps.get(str(i), [])
        handoff_md = slice_dir / "HANDOFF.md"
        handoff_md.write_text(build_handoff_md(
            parent=parent, slice_text=slice_text, slice_number=i,
            total=len(slices), dependencies=slice_deps,
        ), encoding="utf-8")
        state["slices"].append({
            "id": f"slice_{i}",
            "description": slice_text,
            "dependencies": slice_deps,
            "cwd": str(slice_dir),
            "handoffPath": str(handoff_md),
            "status": "pending",
            "startedAt": None,
            "finishedAt": None,
            "slice": None,
            "diff": None,
            "lesson": None,
            "blockedReason": None,
        })

    state_path = run_dir / "run.json"
    state = attach_runtime(state, mode=selected_mode, create_runtime=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "mode": selected_mode,
        "runId": run_id,
        "statePath": str(state_path),
        "sliceCount": len(slices),
        "runtime": state.get("runtime"),
        "dispatchHint": (
            f"For each slice, dispatch a fan-out agent with cwd = the slice dir.\n"
            f"Each agent reads HANDOFF.md, does its slice, returns SLICE/DIFF/LESSON."
        ),
    }, indent=2))
    return 0


def build_handoff_md(parent, slice_text, slice_number, total, dependencies):
    """Markdown describing the parent objective + this slice's role."""
    deps_text = ("## Dependencies\n\nNone — your slice is independent.\n" if not dependencies
                 else "## Dependencies\n\n" + "\n".join(f"- `{d}`" for d in dependencies) + "\n")
    return f"""# Handoff — Slice {slice_number} of {total}

## Parent objective

{parent}

## Your slice

{slice_text}

{deps_text}
## Output format

End your turn with:
1. `SLICE:` one sentence stating what you delivered.
2. `DIFF:` unified diff of every change within your slice.
3. `LESSON:` one line (<=140 chars) capturing the non-obvious insight.

If you cannot deliver, return `BLOCKED:` instead of `SLICE:` + one-sentence reason.

## Files

- Your cwd is the slice directory — edits land here, not in the parent repo.
- Do NOT touch files outside this directory.
- Other slices may have adjoining scope; communicate via diffs in HANDOFF output only.
"""


def cmd_ingest(run_id, slice_outputs=None, mode=None):
    """Replay agent outputs back into the run state. Each output is {slice_id, raw_response}."""
    state_path = FAN_OUT_DIR / run_id / "run.json"
    if not state_path.exists():
        print(f"ERR: run {run_id} not found at {state_path}", file=sys.stderr)
        return 1
    state = json.loads(state_path.read_text())
    state_runtime = state.get("runtime")
    prior_mode = state_runtime.get("mode") if isinstance(state_runtime, Mapping) else None
    selected_mode = resolve_mode(mode or prior_mode)
    outputs = slice_outputs or []
    updated = 0
    for output in outputs:
        slice_id = output.get("sliceId")
        sid = output.get("response", "")
        parsed = parse_agent_response(sid)
        for slice_state in state["slices"]:
            if slice_state["id"] == slice_id:
                slice_state["status"] = "blocked" if parsed["blocked"] or parsed["malformed"] else "done"
                slice_state["finishedAt"] = datetime.now(timezone.utc).isoformat()
                if parsed["blocked"] or parsed["malformed"]:
                    slice_state["blockedReason"] = parsed.get("blockedReason") or "malformed structured slice result"
                else:
                    slice_state["slice"] = parsed.get("slice", "")
                    slice_state["diff"] = parsed.get("diff", "")
                    slice_state["lesson"] = parsed.get("lesson", "")
                if parsed.get("lesson"):
                    record_lesson(state, slice_state, parsed["lesson"])
                updated += 1
                break
    # Save updated state
    state = attach_runtime(state, mode=selected_mode, create_runtime=False)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "mode": selected_mode,
        "runId": run_id,
        "updated": updated,
        "summary": build_summary(state),
        "runtime": state.get("runtime"),
    }, indent=2))
    return 0


def parse_agent_response(raw_text):
    """Extract SLICE/DIFF/LESSON/BLOCKED from agent output. Tolerant of formatting."""
    text = (raw_text or "").strip()
    result = {
        "slice": None,
        "diff": None,
        "lesson": None,
        "blocked": False,
        "blockedReason": None,
        "malformed": False,
    }

    # BLOCKED short-circuits everything else
    blocked_match = find_block(text, "BLOCKED:")
    if blocked_match is not None:
        result["blocked"] = True
        result["blockedReason"] = blocked_match.strip().splitlines()[0] if blocked_match.strip() else ""
        return result

    for label in ("SLICE", "DIFF", "LESSON"):
        content = find_block(text, f"{label}:")
        if content is not None:
            key = label.lower()
            result[key] = content.strip()
    result["malformed"] = any(not result[key] for key in ("slice", "diff", "lesson"))
    return result


def find_block(text, marker):
    """Find content after a `MARKER:` header. Marker may be at start of a line.
    Returns the content following the marker (until the next marker or end).
    """
    idx = text.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    # Find next marker
    rest = text[start:]
    # Look for any of the candidate markers that may follow
    next_idx = len(rest)
    for next_marker in ("DIFF:", "LESSON:", "SLICE:", "BLOCKED:"):
        pos = rest.find(next_marker, 1)  # skip 0 to avoid matching the same marker
        if 0 < pos < next_idx:
            next_idx = pos
    return rest[:next_idx].strip()


def record_lesson(state, slice_state, lesson_text):
    """Write a learning-tier Memory Fabric record for this slice's lesson."""
    mf = find_memory_fabric_cli()
    if not mf:
        return False
    title = f"Fan-out slice {slice_state['id']} lesson — {state['id']}"
    body = (f"Parent: {state['parent']}\n"
            f"Slice: {slice_state['description']}\n"
            f"Lesson: {lesson_text}")
    try:
        completed = subprocess.run(
            ["python3", mf, "record",
             "--tier", "learning",
             "--title", title,
             "--body", body,
             "--scope", str(harness_home()),
             "--tags", f"fan_out,slice:{slice_state['id']},run:{state['id']}",
             "--provenance-type", "user_or_agent_observation",
             "--confidence", "medium",
             "--status", "candidate",
             "--verify-before-use"],
            capture_output=True, text=True, timeout=10
        )
        return completed.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def build_summary(state):
    """One-line summary of run state."""
    slices = state.get("slices", [])
    if not slices:
        return "no slices"
    done = sum(1 for s in slices if s.get("status") == "done")
    blocked = sum(1 for s in slices if s.get("status") == "blocked")
    pending = sum(1 for s in slices if s.get("status") == "pending")
    return f"{done} done, {blocked} blocked, {pending} pending of {len(slices)}"


def cmd_list_handoffs(mode=None):
    """List all fan-out run dirs."""
    selected_mode = resolve_mode(mode)
    if not FAN_OUT_DIR.exists():
        print(json.dumps({"ok": True, "mode": selected_mode, "runs": []}))
        return 0
    runs = []
    for entry in sorted(FAN_OUT_DIR.iterdir(), reverse=True):
        state_path = entry / "run.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            continue
        runs.append({
            "id": state.get("id"),
            "parent": state.get("parent", "")[:80],
            "summary": build_summary(state),
            "createdAt": state.get("createdAt", "?"),
        })
    print(json.dumps({"ok": True, "mode": selected_mode, "runs": runs}, indent=2))
    return 0


def cmd_status(run_id, mode=None):
    """Print detailed state for one run."""
    state_path = FAN_OUT_DIR / run_id / "run.json"
    if not state_path.exists():
        print(f"ERR: run {run_id} not found", file=sys.stderr)
        return 1
    state = json.loads(state_path.read_text())
    state_runtime = state.get("runtime")
    prior_mode = state_runtime.get("mode") if isinstance(state_runtime, Mapping) else None
    selected_mode = resolve_mode(mode or prior_mode)
    # Status is always read-only; do not create a runtime run as a side effect.
    state = attach_runtime(state, mode=selected_mode, create_runtime=False)
    print(json.dumps(state, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Multi-agent fan-out coordinator (Tier 5 #4)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="write HANDOFF.md per slice; print dispatch plan")
    p_prep.add_argument("--parent", required=True, help="parent objective")
    p_prep.add_argument("--slices", nargs="+", required=True, help="one slice description per arg")
    p_prep.add_argument("--deps", help="JSON dict {slice_num: [list of dependency slice descriptions]}")
    p_prep.add_argument("--mode", choices=MODES, default=None, help="legacy, shadow, dual, or runtime (default: legacy)")

    p_ingest = sub.add_parser("ingest", help="replay completed agent outputs into run state")
    p_ingest.add_argument("--run-id", required=True)
    p_ingest.add_argument("--outputs", help="JSON list of {sliceId, response}")
    p_ingest.add_argument("--mode", choices=MODES, default=None)

    p_list = sub.add_parser("list", help="list all fan-out runs")
    p_list.add_argument("--mode", choices=MODES, default=None)
    p_status = sub.add_parser("status", help="print detailed state for one run")
    p_status.add_argument("--run-id", required=True)
    p_status.add_argument("--mode", choices=MODES, default=None)

    args = ap.parse_args()
    if args.command == "prepare":
        deps = json.loads(args.deps) if args.deps else None
        return cmd_prepare(args.parent, args.slices, deps, args.mode)
    elif args.command == "ingest":
        outputs = json.loads(args.outputs) if args.outputs else []
        return cmd_ingest(args.run_id, outputs, args.mode)
    elif args.command == "list":
        return cmd_list_handoffs(args.mode)
    elif args.command == "status":
        return cmd_status(args.run_id, args.mode)


if __name__ == "__main__":
    sys.exit(main())
