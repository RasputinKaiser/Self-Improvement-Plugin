"""Read-only Clonk-style campaign board projection for the graph runtime.

The board is intentionally a projection, not another controller.  It reads
the materialized runtime state plus the append-only event stream and exposes a
small, poll-friendly surface for a UI or command.  Runtime state and event
digests remain the proof boundary; the labels here are presentation aliases.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .dag import compile_dag
from .projection import project_receipt


BOARD_SCHEMA = "sips.runtime.campaign-board.v1"
BOARD_STATUS = {
    "pending": "queued",
    "leased": "starting",
    "running": "running",
    "succeeded": "complete",
    "blocked": "blocked",
    "failed": "failed",
    "canceled": "canceled",
}
TERMINAL = {"succeeded", "blocked", "failed", "canceled"}
MAX_CHANGES = 100
PLAN_PHASES = ("observe", "plan", "execute", "verify", "record")
PHASE_TITLES = {
    "observe": "Observe",
    "plan": "Plan",
    "execute": "Execute",
    "verify": "Verify",
    "record": "Record",
}
PHASE_PROOF = {
    "observe": "Evidence or a bounded context scan is attached before choosing work.",
    "plan": "The plan names scope, dependencies, and an acceptance check.",
    "execute": "The worker receipt names changed paths, claims, and artifacts.",
    "verify": "A focused verification result is attached before claiming completion.",
    "record": "The durable lesson or outcome is written after the proof-bearing result.",
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _role(spec: Mapping[str, Any]) -> str:
    metadata = _as_mapping(spec.get("metadata"))
    raw = (
        metadata.get("role")
        or metadata.get("agent_role")
        or metadata.get("assignee")
        or metadata.get("owner")
    )
    if raw:
        return str(raw)
    task_id = str(spec.get("id", "")).lower()
    if any(word in task_id for word in ("scout", "research", "discover")):
        return "Scout"
    if any(word in task_id for word in ("judge", "review", "evaluate", "verify")):
        return "Judge"
    if any(word in task_id for word in ("plan", "pm", "coord")):
        return "PM"
    return "Worker"


def _presentation_status(item: Mapping[str, Any]) -> str:
    raw = str(item.get("status", "pending")).lower()
    result = _as_mapping(item.get("result"))
    metadata = _as_mapping(_as_mapping(item.get("spec")).get("metadata"))
    explicit = result.get("ui_status") or result.get("phase") or metadata.get("ui_status")
    if explicit:
        value = str(explicit).strip().lower().replace(" ", "_")
        aliases = {
            "complete": "complete",
            "completed": "complete",
            "waiting": "waiting_for_child",
            "waiting_child": "waiting_for_child",
            "waiting_evaluation": "waiting_for_evaluation",
            "verify": "verifying",
            "verification": "verifying",
            "retry": "retry_scheduled",
        }
        if value in {
            "queued", "starting", "running", "waiting_for_child",
            "waiting_for_evaluation", "verifying", "retry_scheduled",
            "blocked", "complete", "failed", "canceled",
        }:
            return aliases.get(value, value)
    if raw == "pending" and result.get("status") == "retry":
        return "retry_scheduled"
    return {"done": "complete", "completed": "complete"}.get(raw, BOARD_STATUS.get(raw, raw or "queued"))


def _task_result_receipt(run_id: str, task_id: str, item: Mapping[str, Any]) -> dict[str, Any] | None:
    result = item.get("result")
    if not isinstance(result, Mapping):
        return None
    # Keep the board card compact while retaining the exact structured result
    # in the immutable per-attempt receipt under the runtime run directory.
    content = {
        "task_id": task_id,
        "slice_id": result.get("slice_id", task_id),
        "status": result.get("status", item.get("status", "unknown")),
        "answer": result.get("answer", result.get("summary", "")),
        "claims": result.get("claims", []),
        "evidence": result.get("evidence", []),
        "artifacts": result.get("artifacts", []),
        "blockers": result.get("blockers", []),
        "changed_paths": result.get("changed_paths", []),
    }
    return project_receipt(content, run_id=f"{run_id}:{task_id}", status=str(content["status"])).to_dict()


def _dependencies(task: Mapping[str, Any]) -> list[str]:
    raw = task.get("depends_on", [])
    if isinstance(raw, str):
        return [raw]
    return [str(value) for value in raw] if isinstance(raw, Sequence) else []


def _ready_ids(tasks: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    specs = [item.get("spec", {}) for item in tasks.values()]
    try:
        graph = compile_dag(specs)
    except (TypeError, ValueError):
        return ()
    # Legacy goal state uses ``done`` while the graph runtime uses
    # ``succeeded``.  Treat both as completed so a restarted legacy board does
    # not advertise already-finished cards as ready work.
    completed = [
        task_id
        for task_id, item in tasks.items()
        if str(item.get("status", "")).lower() in {"succeeded", "done", "complete", "completed"}
    ]
    running = [task_id for task_id, item in tasks.items() if item.get("status") in {"leased", "running"}]
    return graph.ready_ids(completed=completed, running=running)


def _foreground(tasks: Mapping[str, Mapping[str, Any]], ready_ids: Sequence[str]) -> tuple[str | None, str]:
    # One visible next action keeps the board responsive even when the runtime
    # has multiple bounded workers.  Ties are stable and never imply control.
    active = sorted(task_id for task_id, item in tasks.items() if item.get("status") in {"leased", "running"})
    if active:
        return active[0], "active"
    ready = [task_id for task_id in ready_ids if task_id in tasks and tasks[task_id].get("status") == "pending"]
    if ready:
        return ready[0], "ready"
    pending = sorted(task_id for task_id, item in tasks.items() if item.get("status") == "pending")
    if pending:
        return pending[0], "waiting"
    attention = sorted(task_id for task_id, item in tasks.items() if item.get("status") in {"blocked", "failed"})
    if attention:
        return attention[0], "needs-attention"
    return None, "terminal"


def _phase_for(spec: Mapping[str, Any], role: str) -> str:
    metadata = _as_mapping(spec.get("metadata"))
    explicit = str(metadata.get("phase") or "").strip().lower().replace(" ", "_")
    if explicit in PLAN_PHASES:
        return explicit
    return {
        "Scout": "observe",
        "PM": "plan",
        "Judge": "verify",
        "Worker": "execute",
    }.get(role, "execute")


def _phase_status(items: Sequence[Mapping[str, Any]], ready_ids: set[str]) -> str:
    if not items:
        return "not_applicable"
    statuses = {str(item.get("status", "queued")) for item in items}
    if "failed" in statuses or "blocked" in statuses:
        return "needs_attention"
    if statuses and statuses <= {"complete", "canceled"}:
        return "complete" if "complete" in statuses else "canceled"
    if statuses & {"starting", "running"}:
        return "active"
    if any(str(item.get("id")) in ready_ids for item in items):
        return "next"
    if "waiting_for_child" in statuses:
        return "waiting"
    return "queued"


def _plan_summary(tasks: Sequence[Mapping[str, Any]], ready_ids: Sequence[str], foreground_id: str | None) -> dict[str, Any]:
    ready = {str(item) for item in ready_ids}
    phases: list[dict[str, Any]] = []
    for phase in PLAN_PHASES:
        phase_tasks = [item for item in tasks if item.get("phase") == phase]
        phases.append({
            "id": phase,
            "title": PHASE_TITLES[phase],
            "status": _phase_status(phase_tasks, ready),
            "task_ids": [str(item.get("id")) for item in phase_tasks],
            "proof": PHASE_PROOF[phase],
        })
    foreground = next((item for item in tasks if item.get("id") == foreground_id), None)
    if foreground:
        next_phase = str(foreground.get("phase", "execute"))
    else:
        next_phase = next(
            (phase["id"] for phase in phases if phase["status"] in {"needs_attention", "next", "active", "waiting", "queued"}),
            None,
        )
    return {
        "schema": "sips.runtime.goal-plan.v1",
        "phases": phases,
        "next_phase": next_phase,
        "proof_boundary": "Plan phases are deterministic presentation guidance; runtime events and receipts remain authoritative.",
    }


def _recommendation(
    foreground: Mapping[str, Any] | None,
    focus_reason: str,
    plan: Mapping[str, Any],
    idea_cards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if foreground:
        phase = str(foreground.get("phase", "execute"))
        why = {
            "active": "It is already in progress, so the next useful move is to continue or inspect its live receipt.",
            "ready": "Its dependencies are satisfied and it is the first deterministic next action on the board.",
            "waiting": "It is the next queued task, but the runtime is still waiting for its dependencies.",
            "needs-attention": "It has a blocked or failed state that should be understood before more work is started.",
        }.get(focus_reason, "It is the board's stable foreground action for this run.")
        return {
            "kind": "foreground_action",
            "task_id": foreground.get("id"),
            "phase": phase,
            "title": str(foreground.get("title", foreground.get("id", "Continue goal"))),
            "why": why,
            "proof_required": PHASE_PROOF.get(phase, "Attach a proof-bearing receipt before completion."),
        }
    if idea_cards:
        card = idea_cards[0]
        return {
            "kind": "idea_review",
            "idea_id": card.get("id"),
            "phase": "observe",
            "title": str(card.get("title") or card.get("name") or "Review the top suggested idea"),
            "why": "The goal has no active task, so the next bounded move is to review one suggestion before creating work.",
            "proof_required": "Convert the idea into a scoped plan with an acceptance check before execution.",
        }
    return {
        "kind": "no_action",
        "phase": plan.get("next_phase"),
        "title": "No foreground action",
        "why": "The board has no active task or suggested idea to advance.",
        "proof_required": "Create or attach a bounded goal before execution.",
    }


def _changes(events: Sequence[Mapping[str, Any]], since_revision: int | None) -> list[dict[str, Any]]:
    if since_revision is None:
        return []
    result: list[dict[str, Any]] = []
    for event in events:
        try:
            revision = int(event.get("revision", 0))
        except (TypeError, ValueError):
            continue
        if revision <= since_revision:
            continue
        payload = _as_mapping(event.get("payload"))
        result.append({
            "revision": revision,
            "event_type": str(event.get("event_type", "")),
            "event_digest": str(event.get("event_digest", "")),
            "timestamp": event.get("timestamp"),
            "task_id": payload.get("task_id"),
            "status": _as_mapping(payload.get("result")).get("status", payload.get("status")),
        })
    return result[-MAX_CHANGES:]


def build_board(
    state: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]] = (),
    *,
    run_id: str = "",
    since_revision: int | None = None,
    max_changes: int = 24,
) -> dict[str, Any]:
    """Build a bounded board from already-read authoritative runtime values."""
    tasks = _as_mapping(state.get("tasks"))
    normalized_tasks: list[dict[str, Any]] = []
    ready_ids = _ready_ids(tasks)
    counts: Counter[str] = Counter()
    for task_id in sorted(tasks):
        item = _as_mapping(tasks[task_id])
        spec = _as_mapping(item.get("spec"))
        raw_status = str(item.get("status", "pending"))
        display_status = _presentation_status(item)
        if raw_status == "pending" and _dependencies(spec) and str(task_id) not in ready_ids:
            display_status = "waiting_for_child"
        counts[display_status] += 1
        normalized_tasks.append({
            "id": str(task_id),
            # A legacy task carries the parent objective for context, but its
            # description is the actionable card title.  Showing the parent
            # objective for every subtask makes the foreground recommendation
            # look useful while hiding the work the user actually needs to do.
            "title": str(spec.get("title") or spec.get("description") or spec.get("objective") or task_id),
            "description": str(spec.get("description", "")),
            "role": _role(spec),
            "phase": _phase_for(spec, _role(spec)),
            "status": display_status,
            "runtime_status": raw_status,
            "required": bool(spec.get("required", True)),
            "depends_on": _dependencies(spec),
            "priority": spec.get("priority", 0),
            "attempts": item.get("attempts", 0),
            "receipt": _task_result_receipt(run_id, str(task_id), item),
        })
    foreground_id, focus_reason = _foreground(tasks, ready_ids)
    total = len(normalized_tasks)
    complete = counts.get("complete", 0)
    changes = _changes(events, since_revision)
    max_changes = min(MAX_CHANGES, max(0, int(max_changes)))
    suggestions: list[dict[str, Any]] = []
    if foreground_id is not None:
        foreground = next(item for item in normalized_tasks if item["id"] == foreground_id)
        if focus_reason == "ready":
            suggestions.append({"kind": "next_action", "task_id": foreground_id, "title": f"Start {foreground['title']}"})
        elif focus_reason == "needs-attention":
            suggestions.append({"kind": "attention", "task_id": foreground_id, "title": f"Inspect {foreground['title']}"})
        elif focus_reason == "waiting":
            suggestions.append({"kind": "waiting", "task_id": foreground_id, "title": f"Waiting on {foreground['title']} dependencies"})
        else:
            suggestions.append({"kind": "progress", "task_id": foreground_id, "title": f"Continue {foreground['title']}"})
    metadata = _as_mapping(state.get("metadata"))
    idea_cards = metadata.get("idea_cards", [])
    if not isinstance(idea_cards, list):
        idea_cards = []
    plan = _plan_summary(normalized_tasks, ready_ids, foreground_id)
    recommendation = _recommendation(
        next((item for item in normalized_tasks if item["id"] == foreground_id), None),
        focus_reason,
        plan,
        [item for item in idea_cards if isinstance(item, Mapping)],
    )
    if suggestions:
        suggestions[0].update({
            "phase": recommendation.get("phase"),
            "why": recommendation.get("why"),
            "proof_required": recommendation.get("proof_required"),
        })
    elif recommendation["kind"] != "no_action":
        suggestions.append(recommendation)
    board = {
        "schema": BOARD_SCHEMA,
        "authority": "runtime-events",
        "read_only": True,
        "run_id": str(state.get("run_id") or run_id),
        "objective": str(state.get("objective", "")),
        "status": str(state.get("status", "pending")),
        "revision": int(state.get("revision", 0)),
        "head_hash": str(state.get("head_hash", "")),
        "foreground_task_id": foreground_id,
        "focus_reason": focus_reason,
        "ready_task_ids": list(ready_ids),
        "progress": {"complete": complete, "total": total, "ratio": (complete / total if total else 0.0)},
        "counts": dict(sorted(counts.items())),
        "tasks": normalized_tasks,
        "plan": plan,
        "recommendation": recommendation,
        "suggestions": suggestions,
        "idea_cards": idea_cards[:5],
        "changes": changes[-max_changes:] if max_changes else [],
        "next_revision": int(state.get("revision", 0)),
        "claim_boundary": "This is a read-only UI projection. Runtime events, leases, and immutable receipts remain authoritative.",
    }
    provenance = _as_mapping(state.get("provenance"))
    if provenance:
        board["provenance"] = dict(provenance)
    campaign_id = str(metadata.get("campaign_id") or "").strip()
    if campaign_id:
        board["campaign_id"] = campaign_id
        try:
            # Campaign metadata is an optional presentation join.  Keeping the
            # import lazy preserves the runtime's legacy/module-light path and
            # makes a missing campaign non-fatal to the Goal Board.
            from .campaign_fleet import CampaignFleet

            board["campaign"] = CampaignFleet().read(campaign_id, include_archived=True)
        except Exception as exc:  # pragma: no cover - exercised by host drift
            board["campaign_error"] = {
                "campaign_id": campaign_id,
                "error": str(exc),
                "claim_boundary": "The runtime board remains valid; campaign lookup is an optional metadata join.",
            }
    board["digest"] = canonical_hash({key: value for key, value in board.items() if key != "digest"})
    return board


def project_board(controller: Any, run_id: str, *, since_revision: int | None = None, max_changes: int = 24) -> dict[str, Any]:
    """Read a run through the controller and return its board projection."""
    if controller is None:
        return build_board({"run_id": run_id, "status": "idle", "tasks": {}, "revision": 0}, run_id=run_id)
    state = controller.read_status(run_id)
    events = controller.read_events(run_id)
    return build_board(state, events, run_id=run_id, since_revision=since_revision, max_changes=max_changes)


__all__ = ["BOARD_SCHEMA", "build_board", "project_board"]
