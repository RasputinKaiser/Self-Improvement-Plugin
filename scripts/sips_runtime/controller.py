"""Durable graph-runtime controller.

The controller is intentionally small: the event stream is the source of
truth, while the scheduler and leases provide bounded execution coordination.
Memory/context edges are carried as payload metadata only and never affect DAG
readiness.
"""
from __future__ import annotations

import importlib
import json
import os
import time
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Any, Mapping

from .budget import (
    DEFAULT_RESOURCE_LIMITS,
    RESOURCE_DIMENSIONS,
    TRANCHE_PERCENTAGES,
    BudgetLedger,
    TrancheNotReleased,
)
from .canonical import canonical_hash, canonical_json, canonical_path, task_sets_compatible
from .contracts import (
    STATE_VERSION,
    Event,
    SliceResult,
    TaskSpec,
    uuid7_str,
    validate_safe_identifier,
)
from .dag import DAGError, TaskGraph, compile_dag
from .events import (
    EventIntegrityError,
    EventStore,
    IdempotencyConflict,
    RevisionConflict,
    atomic_write_json,
    transition_lock,
)
from .leases import ATTEMPT_CEILING_SECONDS, LEASE_TTL_SECONDS, Lease, LeaseManager, StaleLeaseError
from .scheduler import PathLockTable, schedule_ready
from .snapshots import SnapshotMismatch, SnapshotStore
from .promotion import promote_lesson
from .quality import (
    HIGH_IMPACT,
    HIGH_IMPACT_RISK_TAGS,
    evaluate_gates,
    validate_evidence_items,
)
from .fanin import fan_in
from .projection import make_graph_receipt
from .context import account_context_packet, build_context_packet
from .memory_frontier import query_frontier


TERMINAL_TASK_STATES = {"succeeded", "blocked", "failed", "canceled"}
TERMINAL_RUN_STATES = {"succeeded", "blocked", "failed", "canceled"}
MAX_CONCURRENCY = 2


class ControllerError(RuntimeError):
    pass


class InvalidTransition(ControllerError):
    pass


def runtime_root(root: str | os.PathLike[str] | None = None) -> Path:
    if root is None:
        root = os.environ.get("SIPS_HOME") or (Path.home() / ".codex" / "sips")
    return Path(root).expanduser().resolve() / "runtime" / "v1" / "runs"


def guarded_transition(method):
    """Hold the run mutex across state read, validation, and event append."""
    @wraps(method)
    def wrapped(self: "RuntimeController", run_id: str, *args: Any, **kwargs: Any):
        with transition_lock(self._run_dir(run_id) / ".transition.lock"):
            return method(self, run_id, *args, **kwargs)

    return wrapped


class RuntimeController:
    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        self.root = runtime_root(root)
        self.leases = LeaseManager()
        self.locks = PathLockTable()
        self._budgets: dict[str, BudgetLedger] = {}

    def _run_dir(self, run_id: str) -> Path:
        return self.root / validate_safe_identifier(run_id, label="run_id")

    def _store(self, run_id: str) -> EventStore:
        return EventStore(self._run_dir(run_id))

    def _existing_store(self, run_id: str) -> EventStore:
        """Open a run without creating authority files for an unknown ID."""
        run_dir = self._run_dir(run_id)
        if not run_dir.is_dir() or not (run_dir / "head.json").is_file():
            raise ControllerError(f"unknown run: {run_id}")
        return EventStore(run_dir)

    def _snapshot(self, run_id: str) -> SnapshotStore:
        return SnapshotStore(self._run_dir(run_id))

    @staticmethod
    def _require_write_contract(
        idempotency_key: str | None, expected_revision: int | None
    ) -> None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if (
            not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or expected_revision < 0
        ):
            raise ValueError("expected_revision must be a non-negative integer")

    @staticmethod
    def _initial() -> dict[str, Any]:
        return {
            "schema_version": STATE_VERSION,
            "run_id": "",
            "status": "pending",
            "objective": "",
            "workspace_root": "",
            "metadata": {},
            "terminal_policy": "block_descendants",
            "budgets": {
                "soft_limit": 60_000,
                "hard_limit": 120_000,
                "resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
                "tranche_percentages": list(TRANCHE_PERCENTAGES),
                "released_tranches": 1,
            },
            "tasks": {},
            "revision": 0,
            "head_hash": "",
        }

    @staticmethod
    def _reduce(state: dict[str, Any] | None, event: Event) -> dict[str, Any]:
        current = dict(state or RuntimeController._initial())
        current["revision"] = event.revision
        current["head_hash"] = event.event_hash
        payload = dict(event.payload)
        if event.event_type == "run.created":
            current.update(
                {
                    "run_id": event.run_id,
                    "status": "pending",
                    "objective": payload.get("objective", ""),
                    "workspace_root": payload.get("workspace_root", ""),
                    "metadata": payload.get("metadata", {}),
                    "terminal_policy": payload.get("terminal_policy", "block_descendants"),
                    "budgets": payload.get("budgets", RuntimeController._initial()["budgets"]),
                }
            )
            current["tasks"] = {
                task["id"]: {
                    "spec": task,
                    "status": "pending",
                    "result": None,
                    "lease": None,
                    "reservation": None,
                    "context": None,
                    "attempts": 0,
                    "last_fencing_token": 0,
                }
                for task in payload.get("tasks", [])
            }
        elif event.event_type == "run.submitted":
            if current.get("status") == "pending":
                current["status"] = "running"
                RuntimeController._update_run_status(current)
        elif event.event_type == "task.leased":
            task_id = str(payload["task_id"])
            item = dict(current["tasks"].get(task_id, {}))
            item["status"] = "leased"
            item["lease"] = payload.get("lease")
            item["reservation"] = payload.get("reservation")
            item["context"] = payload.get("context")
            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["last_fencing_token"] = int((payload.get("lease") or {}).get("fencing_token", 0))
            current["tasks"][task_id] = item
            tranche = payload.get("tranche_release")
            if isinstance(tranche, Mapping):
                budgets = dict(current.get("budgets", {}))
                budgets["released_tranches"] = int(
                    tranche.get("released_after", budgets.get("released_tranches", 1))
                )
                budgets["released_token_limit"] = int(
                    tranche.get(
                        "released_token_limit", budgets.get("released_token_limit", 0)
                    )
                )
                current["budgets"] = budgets
            if current.get("status") == "pending":
                current["status"] = "running"
        elif event.event_type == "task.heartbeat":
            task_id = str(payload["task_id"])
            item = dict(current["tasks"].get(task_id, {}))
            item["status"] = "running"
            item["lease"] = payload.get("lease")
            current["tasks"][task_id] = item
        elif event.event_type == "task.advanced":
            task_id = str(payload["task_id"])
            result = dict(payload.get("result", {}))
            item = dict(current["tasks"].get(task_id, {}))
            status = str(result.get("status", payload.get("status", "succeeded"))).lower()
            aliases = {
                "complete": "succeeded",
                "completed": "succeeded",
                "done": "succeeded",
                "cancelled": "canceled",
            }
            status = aliases.get(status, status)
            if status == "retry":
                item["status"] = "pending"
                item["result"] = result
                item["lease"] = None
                item["reservation"] = None
                current["tasks"][task_id] = item
                return current
            if status not in {"running", *TERMINAL_TASK_STATES}:
                status = "failed"
            item["status"] = status
            item["result"] = result
            if status in TERMINAL_TASK_STATES:
                item["lease"] = None
                item["reservation"] = None
            current["tasks"][task_id] = item
            if status in {"blocked", "failed", "canceled"} and current.get("terminal_policy", "block_descendants") != "continue":
                RuntimeController._block_descendants(current)
            RuntimeController._update_run_status(current)
        elif event.event_type == "run.canceled":
            current["status"] = "canceled"
            for task_id, item in current["tasks"].items():
                if item.get("status") not in TERMINAL_TASK_STATES:
                    item = dict(item)
                    item["status"] = "canceled"
                    item["lease"] = None
                    item["reservation"] = None
                    item["result"] = {
                        "task_id": task_id,
                        "slice_id": task_id,
                        "status": "canceled",
                        "reason": str(payload.get("reason", "")),
                        "claims": [],
                        "evidence": [],
                        "artifacts": [],
                        "changed_paths": [],
                        "blockers": ["run_canceled"],
                    }
                    current["tasks"][task_id] = item
        return current

    @staticmethod
    def _block_descendants(state: dict[str, Any]) -> None:
        """Close every descendant whose AND predecessor cannot succeed."""
        tasks = state.get("tasks", {})
        changed = True
        while changed:
            changed = False
            for task_id in sorted(tasks):
                item = tasks[task_id]
                if item.get("status") not in {"pending", "leased", "running"}:
                    continue
                dependencies = item.get("spec", {}).get("depends_on", ())
                blockers = sorted(
                    dependency
                    for dependency in dependencies
                    if tasks.get(dependency, {}).get("status") in {"blocked", "failed", "canceled"}
                )
                if not blockers:
                    continue
                updated = dict(item)
                updated["status"] = "blocked"
                updated["lease"] = None
                updated["reservation"] = None
                updated["result"] = {
                    "status": "blocked",
                    "blockers": blockers,
                    "reason": "failed_predecessor",
                    "claims": [],
                    "evidence": [],
                    "artifacts": [],
                    "changed_paths": [],
                }
                tasks[task_id] = updated
                changed = True

    @staticmethod
    def _effective_required_ids(state: Mapping[str, Any]) -> set[str]:
        tasks = state.get("tasks", {})
        required = {
            str(task_id)
            for task_id, item in tasks.items()
            if (item.get("spec") or {}).get("required", True) is True
        }
        stack = list(required)
        while stack:
            task_id = stack.pop()
            for dependency in (tasks.get(task_id, {}).get("spec") or {}).get(
                "depends_on", ()
            ):
                dependency = str(dependency)
                if dependency not in required:
                    required.add(dependency)
                    stack.append(dependency)
        return required

    @staticmethod
    def _update_run_status(state: dict[str, Any]) -> None:
        tasks = state.get("tasks", {})
        required_ids = RuntimeController._effective_required_ids(state)
        statuses = [tasks[task_id].get("status") for task_id in sorted(required_ids)]
        if any(status not in TERMINAL_TASK_STATES for status in statuses):
            return
        if any(status == "failed" for status in statuses):
            state["status"] = "failed"
        elif any(status == "blocked" for status in statuses):
            state["status"] = "blocked"
        elif any(status == "canceled" for status in statuses):
            state["status"] = "canceled"
        else:
            state["status"] = "succeeded"
        # Independent optional work is no longer admissible after the required
        # closure reaches a terminal state. Preserve it explicitly as skipped
        # evidence and fence any outstanding optional lease.
        for task_id in sorted(set(tasks) - required_ids):
            item = tasks[task_id]
            if item.get("status") in TERMINAL_TASK_STATES:
                continue
            updated = dict(item)
            updated["status"] = "canceled"
            updated["lease"] = None
            updated["reservation"] = None
            updated["result"] = {
                "task_id": task_id,
                "slice_id": task_id,
                "status": "canceled",
                "reason": "optional_task_skipped_after_required_terminal",
                "claims": [],
                "evidence": [],
                "artifacts": [],
                "changed_paths": [],
                "blockers": ["optional_not_required"],
            }
            tasks[task_id] = updated

    def _state(self, run_id: str) -> dict[str, Any]:
        store = self._existing_store(run_id)
        with store.event_snapshot() as events:
            if not events:
                raise ControllerError(f"unknown run: {run_id}")
            state = self._initial()
            for event in events:
                state = self._reduce(state, event)
            revision = len(events)
            head_hash = events[-1].event_hash
            state["revision"] = revision
            state["head_hash"] = head_hash
            charged_resources = self._charged_resources(events)
            charged = charged_resources["model_tokens"]
            hard_limit = int(state.get("budgets", {}).get("hard_limit", 120_000))
            soft_limit = int(state.get("budgets", {}).get("soft_limit", 60_000))
            released_tranches = self._released_tranche_count(events)
            budget_view = BudgetLedger(
                soft_limit,
                hard_limit,
                state.get("budgets", {}).get("resource_limits", DEFAULT_RESOURCE_LIMITS),
                released_tranches=released_tranches,
            )
            state["budget_usage"] = {
                "charged_tokens": charged,
                "remaining_hard": max(0, hard_limit - charged),
                "soft_exceeded": charged > soft_limit,
                "unknown_is_zero": False,
                "resources": charged_resources,
                "resource_limits": dict(state.get("budgets", {}).get("resource_limits", DEFAULT_RESOURCE_LIMITS)),
                "tranche_percentages": list(state.get("budgets", {}).get("tranche_percentages", TRANCHE_PERCENTAGES)),
                "tranche_limits": list(budget_view.tranche_limits),
                "released_tranches": released_tranches,
                "released_token_limit": budget_view.released_token_limit,
            }
            snapshot = self._snapshot(run_id)
            try:
                snapshot.load(
                    expected_revision=revision,
                    expected_hash=head_hash,
                )
            except SnapshotMismatch:
                # The event snapshot is authoritative and remains locked until
                # this atomic projection replacement completes.
                snapshot.save(revision, head_hash, state)
        return state

    @staticmethod
    def _request_tasks(request: Any) -> list[TaskSpec]:
        if isinstance(request, Mapping):
            raw = request.get("tasks", request.get("plan", ()))
        else:
            raw = request
        if isinstance(raw, Mapping):
            raw = list(raw.values())
        tasks: list[TaskSpec] = []
        for ordinal, item in enumerate(raw):
            task = item if isinstance(item, TaskSpec) else TaskSpec.from_dict(item)
            if not isinstance(item, Mapping) or "insertion_ordinal" not in item:
                task = replace(task, insertion_ordinal=ordinal)
            tasks.append(task)
        return tasks

    @staticmethod
    def _normalize_task_paths(tasks: list[TaskSpec], workspace_root: Path) -> list[TaskSpec]:
        normalized: list[TaskSpec] = []
        for task in tasks:
            sets: list[tuple[str, ...]] = []
            for paths in (task.read_set, task.write_set):
                values: list[str] = []
                for raw in paths:
                    if not raw or any(character in raw for character in "*?[]"):
                        raise ValueError(f"task {task.id} has unresolved path: {raw!r}")
                    candidate = Path(raw)
                    absolute = canonical_path(candidate if candidate.is_absolute() else workspace_root / candidate)
                    try:
                        relative = absolute.relative_to(workspace_root)
                    except ValueError as exc:
                        raise ValueError(f"task {task.id} path escapes workspace: {raw}") from exc
                    values.append(relative.as_posix())
                sets.append(tuple(sorted(set(values))))
            merge_strategy = str(task.merge_contract.get("strategy", "")).strip()
            if merge_strategy != "deterministic":
                raise ValueError(
                    f"task {task.id} merge strategy must be deterministic, got {merge_strategy or 'missing'}"
                )
            normalized.append(replace(task, read_set=sets[0], write_set=sets[1]))
        return normalized

    @staticmethod
    def _lease_active(item: Mapping[str, Any], now: float | None = None) -> bool:
        if item.get("status") not in {"leased", "running"}:
            return False
        lease = item.get("lease") or {}
        try:
            current = time.time() if now is None else now
            return (
                float(lease.get("expires_at", 0)) > current
                and current - float(lease.get("acquired_at", current))
                < ATTEMPT_CEILING_SECONDS
            )
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _task_with_absolute_paths(task: TaskSpec, workspace_root: str) -> TaskSpec:
        root = canonical_path(workspace_root or os.getcwd())
        return replace(
            task,
            read_set=tuple(str(canonical_path(root / path)) for path in task.read_set),
            write_set=tuple(str(canonical_path(root / path)) for path in task.write_set),
        )

    @staticmethod
    def _charged_resources(
        store: EventStore | tuple[Event, ...]
    ) -> dict[str, int]:
        charges: dict[tuple[str, int], dict[str, int]] = {}

        def require_non_negative_int(value: Any, label: str) -> int:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise EventIntegrityError(
                    f"{label} must be a non-negative integer"
                )
            return int(value)

        def require_positive_fence(value: Any, label: str) -> int:
            token = require_non_negative_int(value, label)
            if token < 1:
                raise EventIntegrityError(f"{label} must be a positive integer")
            return token

        def require_resource_map(value: Any, label: str) -> dict[str, int]:
            if not isinstance(value, Mapping):
                raise EventIntegrityError(f"{label} must be an object")
            unknown = sorted(set(value) - set(RESOURCE_DIMENSIONS))
            if unknown:
                raise EventIntegrityError(
                    f"{label} contains unknown dimensions: {', '.join(map(str, unknown))}"
                )
            missing = sorted(set(RESOURCE_DIMENSIONS) - set(value))
            if missing:
                raise EventIntegrityError(
                    f"{label} is missing dimensions: {', '.join(missing)}"
                )
            return {
                dimension: require_non_negative_int(
                    value[dimension], f"{label}.{dimension}"
                )
                for dimension in RESOURCE_DIMENSIONS
            }

        events = store.events() if isinstance(store, EventStore) else store
        for event in events:
            payload = event.payload
            if event.event_type == "task.leased":
                if not isinstance(payload, Mapping):
                    raise EventIntegrityError("task.leased payload must be an object")
                task_id = payload.get("task_id")
                if not isinstance(task_id, str) or not task_id.strip():
                    raise EventIntegrityError("task.leased task_id is required")
                lease = payload.get("lease")
                reservation = payload.get("reservation")
                if not isinstance(lease, Mapping):
                    raise EventIntegrityError("task.leased lease must be an object")
                if not isinstance(reservation, Mapping):
                    raise EventIntegrityError(
                        "task.leased reservation must be an object"
                    )
                fencing_token = require_positive_fence(
                    lease.get("fencing_token"),
                    "task.leased lease.fencing_token",
                )
                tokens = require_non_negative_int(
                    reservation.get("tokens"),
                    "task.leased reservation.tokens",
                )
                resources = require_resource_map(
                    reservation.get("resources"),
                    "task.leased reservation.resources",
                )
                if resources["model_tokens"] != tokens:
                    raise EventIntegrityError(
                        "task.leased reservation model_tokens must match tokens"
                    )
                charges[(task_id, fencing_token)] = resources
            elif event.event_type == "task.advanced":
                if not isinstance(payload, Mapping):
                    raise EventIntegrityError("task.advanced payload must be an object")
                task_id = payload.get("task_id")
                if not isinstance(task_id, str) or not task_id.strip():
                    raise EventIntegrityError("task.advanced task_id is required")
                fencing_token = require_positive_fence(
                    payload.get("fencing_token"),
                    "task.advanced fencing_token",
                )
                key = (task_id, fencing_token)
                if key not in charges:
                    raise EventIntegrityError(
                        "task.advanced has no matching task.leased reservation"
                    )
                result = payload.get("result")
                if not isinstance(result, Mapping):
                    raise EventIntegrityError("task.advanced result must be an object")
                reserved = charges[key]
                measured: dict[str, int] = {}
                if "usage" in result:
                    usage = result["usage"]
                    if not isinstance(usage, Mapping):
                        raise EventIntegrityError(
                            "task.advanced result.usage must be an object"
                        )
                    if "resources" in usage:
                        actual_values = usage["resources"]
                        if not isinstance(actual_values, Mapping):
                            raise EventIntegrityError(
                                "task.advanced result.usage.resources must be an object"
                            )
                    else:
                        actual_values = usage
                    unknown = sorted(set(actual_values) - set(RESOURCE_DIMENSIONS))
                    if unknown:
                        raise EventIntegrityError(
                            "task.advanced usage contains unknown dimensions: "
                            + ", ".join(map(str, unknown))
                        )
                    for dimension, value in actual_values.items():
                        measured[str(dimension)] = require_non_negative_int(
                            value,
                            f"task.advanced usage.{dimension}",
                        )
                if "cost_tokens" in result and result["cost_tokens"] is not None:
                    measured["model_tokens"] = require_non_negative_int(
                        result["cost_tokens"],
                        "task.advanced result.cost_tokens",
                    )
                # Provider-unknown dimensions are charged at reservation,
                # never silently rewritten as zero.
                charges[key] = {
                    dimension: measured.get(dimension, reserved[dimension])
                    for dimension in RESOURCE_DIMENSIONS
                }
        return {
            dimension: sum(max(0, attempt[dimension]) for attempt in charges.values())
            for dimension in RESOURCE_DIMENSIONS
        }

    @staticmethod
    def _charged_tokens(store: EventStore) -> int:
        return RuntimeController._charged_resources(store)["model_tokens"]

    @staticmethod
    def _released_tranche_count(
        store: EventStore | tuple[Event, ...]
    ) -> int:
        released = 1
        events = store.events() if isinstance(store, EventStore) else store
        for event in events:
            if event.event_type == "run.created":
                budgets = event.payload.get("budgets")
                if isinstance(budgets, Mapping):
                    try:
                        released = max(
                            released, int(budgets.get("released_tranches", released))
                        )
                    except (TypeError, ValueError):
                        pass
                continue
            if event.event_type != "task.leased":
                continue
            tranche = event.payload.get("tranche_release")
            if not isinstance(tranche, Mapping):
                continue
            try:
                released = max(released, int(tranche.get("released_after", released)))
            except (TypeError, ValueError):
                continue
        return min(len(TRANCHE_PERCENTAGES), max(1, released))

    @staticmethod
    def _task_resource_reservation(task: TaskSpec) -> dict[str, int]:
        if task.estimated_tokens is None:
            # Unknown model usage blocks admission in BudgetLedger.
            return {}
        metadata_packet = build_context_packet(
            (),
            task=task,
            required_sources=task.required_sources,
            max_records=8,
            max_tokens=4_000,
        )
        context_floor = max(
            512,
            int(metadata_packet.get("response_token_estimate", 0)) + 256,
        )
        if task.context_query or task.required_sources:
            context_floor = max(4_000, context_floor)
        defaults = {
            "model_tokens": int(task.estimated_tokens),
            "retrieval_tokens": context_floor,
            "output_tokens": min(8_000, max(1_024, int(task.estimated_tokens) // 4)),
            "delegations": 1,
            "tool_calls": 16,
            "repairs": int(task.retry_limit),
            "wall_time_seconds": int(ATTEMPT_CEILING_SECONDS),
            "memory_bytes": 8 * 1024 * 1024,
        }
        supplied = {str(key): int(value) for key, value in task.resource_estimates.items()}
        below_floor = sorted(
            dimension
            for dimension, value in supplied.items()
            if value < defaults[dimension]
        )
        if below_floor:
            detail = ", ".join(
                f"{dimension}={supplied[dimension]}<{defaults[dimension]}"
                for dimension in below_floor
            )
            raise ValueError(
                f"task {task.id} resource estimate is below mandatory reservation: {detail}"
            )
        defaults.update(supplied)
        return defaults

    @staticmethod
    def _context_for_task(state: Mapping[str, Any], task: TaskSpec) -> dict[str, Any]:
        metadata = state.get("metadata") if isinstance(state.get("metadata"), Mapping) else {}
        task_metadata = task.metadata if isinstance(task.metadata, Mapping) else {}
        scope = str(task_metadata.get("memory_scope") or metadata.get("memory_scope") or "").strip()
        records: list[dict[str, Any]] = []
        frontier: dict[str, Any] | None = None
        if task.context_query:
            if not scope:
                raise InvalidTransition(f"task {task.id} context_query requires memory_scope")
            frontier = query_frontier(
                scope=scope,
                query=task.context_query,
                store=metadata.get("memory_store"),
                seed_limit=8,
                fanout=4,
                max_depth=2,
                max_nodes=24,
                max_edges=80,
                max_paths=8,
                token_budget=4_000,
            )
            records.extend(dict(item) for item in frontier.get("records", ()))
        workspace = canonical_path(state.get("workspace_root") or os.getcwd())
        for source in task.required_sources:
            if isinstance(source, Mapping):
                records.append(dict(source))
                continue
            source_id = str(source)
            candidate = canonical_path(
                Path(source_id) if Path(source_id).is_absolute() else workspace / source_id
            )
            try:
                candidate.relative_to(workspace)
            except ValueError:
                # A non-path required source may be a Memory Fabric record id.
                continue
            if candidate.is_file():
                body = candidate.read_text(encoding="utf-8", errors="replace")[:12_000]
                records.append(
                    {
                        "id": source_id,
                        "scope": scope or str(workspace),
                        "status": "active",
                        "trust": "verified",
                        "text": body,
                        "provenance": {
                            "type": "source_file",
                            "evidence_path": str(candidate),
                            "digest": canonical_hash(body),
                        },
                    }
                )
        packet = build_context_packet(
            records,
            task=task,
            required_sources=[
                str(item.get("id", item)) if isinstance(item, Mapping) else str(item)
                for item in task.required_sources
            ],
            scope=scope,
            query=task.context_query or "",
            max_records=8,
            max_tokens=4_000,
        )
        if packet.get("ok") is not True:
            if packet.get("error") == "required_sources_unavailable":
                raise InvalidTransition(f"required context source missing for task {task.id}")
            raise InvalidTransition(f"context assembly failed for {task.id}: {packet.get('error')}")
        required_ids = {
            str(item.get("id", item)) if isinstance(item, Mapping) else str(item)
            for item in task.required_sources
        }
        if required_ids - set(map(str, packet.get("selected_ids", ()))):
            raise InvalidTransition(f"required context source missing for task {task.id}")
        packet["frontier"] = {
            "seed_ids": list(
                (
                    (frontier or {}).get("selected", {})
                    if isinstance((frontier or {}).get("selected"), Mapping)
                    else {}
                ).get("seed_ids", ())
            ),
            "node_count": int((frontier or {}).get("node_count", 0)),
            "edge_count": int((frontier or {}).get("edge_count", 0)),
            "path_count": int((frontier or {}).get("path_count", 0)),
            "limits": dict((frontier or {}).get("limits", {})),
            "token_estimate": int((frontier or {}).get("token_estimate", 0)),
            "token_budget": int((frontier or {}).get("token_budget", 4_000)),
            "truncated": bool((frontier or {}).get("truncated", False)),
            "truncation": dict((frontier or {}).get("truncation", {})),
            "omitted": list((frontier or {}).get("omitted", ())),
            "omitted_ids": list((frontier or {}).get("omitted_ids", ())),
            "omitted_reasons": dict((frontier or {}).get("omitted_reasons", {})),
        }
        if frontier:
            existing_omissions = {
                (str(item.get("id", "")), str(item.get("reason", "")))
                for item in packet.get("omitted", ())
                if isinstance(item, Mapping)
            }
            for item in frontier.get("omitted", ()):
                if not isinstance(item, Mapping):
                    continue
                merged = {
                    **dict(item),
                    "reason": f"frontier_{item.get('reason', 'omitted')}",
                    "stage": "memory_frontier",
                }
                key = (str(merged.get("id", "")), str(merged.get("reason", "")))
                if key not in existing_omissions:
                    packet.setdefault("omitted", []).append(merged)
                    existing_omissions.add(key)
            packet["omitted"] = sorted(
                packet.get("omitted", ()),
                key=lambda item: (
                    str(item.get("id", "")),
                    str(item.get("reason", "")),
                ),
            )
            packet["omitted_ids"] = sorted(
                {str(item.get("id", "")) for item in packet["omitted"]}
            )
            packet["omitted_count"] = len(packet["omitted"])
        # Reserve the fixed digest width before final envelope accounting, then
        # hash the complete packet projection without self-reference.
        packet["digest"] = "0" * 64
        account_context_packet(packet)
        packet["digest"] = canonical_hash(
            {key: value for key, value in packet.items() if key != "digest"}
        )
        account_context_packet(packet)
        return packet

    def _idempotent_event(self, run_id: str, key: str | None, event_types: set[str]) -> Event | None:
        if not key:
            return None
        prior = self._store(run_id).find_idempotency(key)
        if prior is None:
            return None
        if prior.event_type not in event_types:
            raise IdempotencyConflict(f"idempotency key already used by {prior.event_type}: {key}")
        return prior

    def _write_result_receipt(self, run_id: str, task_id: str, event: Event) -> None:
        result = dict(event.payload.get("result") or {})
        receipt = {
            "schema": "sips.runtime.slice-receipt.v1",
            "schema_version": 1,
            "run_id": run_id,
            "task_id": task_id,
            "seq": event.revision,
            "event_digest": event.event_digest,
            "result": result,
            "result_digest": canonical_hash(result),
        }
        run_dir = self._run_dir(run_id)
        filename = f"{event.revision:06d}-{task_id}-{event.event_digest[:12]}.json"

        def write_immutable(target: Path) -> None:
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise InvalidTransition(
                        f"immutable slice receipt is unreadable: {target}"
                    ) from exc
                if canonical_hash(existing) != canonical_hash(receipt):
                    raise InvalidTransition(
                        f"immutable slice receipt already differs: {target}"
                    )
                return
            atomic_write_json(target, receipt)

        write_immutable(run_dir / "receipts" / filename)
        # Bind the immutable slice path to the attempt that produced this
        # event. A later retry may already be leased when a crashed receipt is
        # reconstructed, so current materialized state is not authoritative
        # for this filename.
        attempts = sum(
            1
            for prior in self._store(run_id).events()
            if prior.revision <= event.revision
            and prior.event_type == "task.leased"
            and str(prior.payload.get("task_id", "")) == task_id
        )
        if attempts < 1:
            raise InvalidTransition(
                f"task result event has no preceding lease: {task_id}"
            )
        write_immutable(
            run_dir / "slices" / task_id / f"attempt-{attempts:03d}.json"
        )

    def _validate_graph_receipt(
        self,
        run_id: str,
        value: Any,
        *,
        expected: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise InvalidTransition("immutable GraphReceipt must be an object")
        receipt = dict(value)
        structured = receipt.get("structured")
        if not isinstance(structured, Mapping):
            raise InvalidTransition("immutable GraphReceipt structured content is missing")
        structured = dict(structured)
        if (
            structured.get("schema") != "sips.runtime.graph-receipt.v1"
            or structured.get("schema_version") != 1
        ):
            raise InvalidTransition("immutable GraphReceipt schema or version mismatch")
        digest = str(receipt.get("digest", ""))
        if not digest or digest != canonical_hash(structured):
            raise InvalidTransition("immutable GraphReceipt structured digest mismatch")
        if (
            str(receipt.get("run_id", "")) != run_id
            or str(structured.get("run_id", "")) != run_id
            or str(receipt.get("status", "")) != str(structured.get("status", ""))
        ):
            raise InvalidTransition("immutable GraphReceipt run or status mismatch")
        for key in ("revision", "event_digest", "generated_at"):
            if receipt.get(key) != structured.get(key):
                raise InvalidTransition(
                    f"immutable GraphReceipt {key} alias mismatch"
                )
        limits = structured.get("projection_limits")
        if not isinstance(limits, Mapping):
            raise InvalidTransition("immutable GraphReceipt projection limits are missing")
        try:
            limit_values = (
                limits["max_chars"],
                limits["max_answer_units"],
                limits["max_omissions"],
            )
        except KeyError as exc:
            raise InvalidTransition(
                "immutable GraphReceipt projection limits are invalid"
            ) from exc
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 0
            for item in limit_values
        ):
            raise InvalidTransition(
                "immutable GraphReceipt projection limits are invalid"
            )
        max_chars, max_answer_units, max_omissions = limit_values
        if max_chars > 8_000 or max_answer_units > 12 or max_omissions > 5:
            raise InvalidTransition(
                "immutable GraphReceipt projection limits exceed runtime bounds"
            )
        markdown = receipt.get("markdown")
        if not isinstance(markdown, str) or len(markdown) > max_chars:
            raise InvalidTransition(
                "immutable GraphReceipt Markdown projection is invalid"
            )
        if expected is not None and canonical_hash(receipt) != canonical_hash(expected):
            raise InvalidTransition(
                "immutable GraphReceipt differs from authoritative projection"
            )
        return receipt

    def _write_graph_receipt(self, run_id: str, event: Event) -> dict[str, Any] | None:
        state = self._state(run_id)
        if state.get("status") not in TERMINAL_RUN_STATES:
            return None
        ordered_ids = sorted(state["tasks"])
        required_ids = sorted(self._effective_required_ids(state))
        results: list[dict[str, Any]] = []
        for task_id in ordered_ids:
            item_result = dict(
                state["tasks"][task_id].get("result")
                or {"task_id": task_id, "status": "missing"}
            )
            item_result.setdefault("task_id", task_id)
            item_result.setdefault("slice_id", task_id)
            results.append(item_result)
        merged = fan_in(
            results,
            expected_task_ids=required_ids,
            require_lease=False,
            legacy=True,
        )
        omissions = [
            {"task_id": item, "reason": "missing_slice"} for item in merged.get("missing", [])
        ] + list(merged.get("blocked", [])) + list(merged.get("conflicts", []))
        receipt = make_graph_receipt(
            {
                "run_id": run_id,
                "status": state["status"],
                "revision": event.revision,
                "event_digest": event.event_digest,
                "generated_at": event.timestamp,
                "plan_digest": canonical_hash(
                    [state["tasks"][task_id]["spec"] for task_id in ordered_ids]
                ),
                "task_results": results,
                "task_ids": ordered_ids,
                "required_task_ids": required_ids,
                "optional_task_ids": sorted(set(ordered_ids) - set(required_ids)),
                "claims": merged.get("claims", []),
                "evidence": merged.get("evidence", []),
                "artifacts": merged.get("artifacts", []),
                "conflicts": merged.get("conflicts", []),
                "result_conflicts": merged.get("result_conflicts", []),
                "duplicates": merged.get("duplicates", []),
                "missing": merged.get("missing", []),
                "blocked": merged.get("blocked", []),
                "budget_usage": state.get("budget_usage", {}),
                "quality": {
                    task_id: state["tasks"][task_id].get("result", {}).get("quality", {})
                    if isinstance(state["tasks"][task_id].get("result"), Mapping)
                    else {}
                    for task_id in ordered_ids
                },
                "omissions": omissions,
            },
            status=state["status"],
        ).to_dict()
        target = self._run_dir(run_id) / "receipts" / "graph-receipt.json"
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidTransition("immutable GraphReceipt is unreadable") from exc
            return self._validate_graph_receipt(
                run_id, existing, expected=receipt
            )
        atomic_write_json(target, receipt)
        return receipt

    @staticmethod
    def _next_fencing_token(store: EventStore) -> int:
        highest = 0
        for event in store.events():
            if event.event_type != "task.leased":
                continue
            lease = event.payload.get("lease", {})
            try:
                highest = max(highest, int(lease.get("fencing_token", 0)))
            except (TypeError, ValueError):
                continue
        return highest + 1

    @staticmethod
    def _active_path_compatible(state: Mapping[str, Any], chosen: TaskSpec) -> bool:
        active = []
        for item in state.get("tasks", {}).values():
            if not RuntimeController._lease_active(item):
                continue
            active.append(
                RuntimeController._task_with_absolute_paths(
                    TaskSpec.from_dict(item["spec"]), str(state.get("workspace_root", ""))
                )
            )
        chosen = RuntimeController._task_with_absolute_paths(
            chosen, str(state.get("workspace_root", ""))
        )
        return all(
            task_sets_compatible(chosen.read_set, chosen.write_set, task.read_set, task.write_set)
            for task in active
        )

    def create(
        self,
        request: Mapping[str, Any] | list[TaskSpec | Mapping[str, Any]],
        idempotency_key: str | None = None,
        expected_revision: int | None = 0,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        request_map = dict(request) if isinstance(request, Mapping) else {"tasks": request}
        raw_run_id = request_map.get("run_id")
        requested_run_id = (
            ""
            if raw_run_id in (None, "")
            else validate_safe_identifier(raw_run_id, label="run_id")
        )
        workspace_root = canonical_path(request_map.get("workspace_root") or os.getcwd())
        tasks = self._normalize_task_paths(self._request_tasks(request_map), workspace_root)
        compile_dag(tasks)
        soft_limit = request_map.get("soft_budget", 60_000)
        hard_limit = request_map.get("hard_budget", 120_000)
        if (
            not isinstance(soft_limit, int)
            or isinstance(soft_limit, bool)
            or not isinstance(hard_limit, int)
            or isinstance(hard_limit, bool)
        ):
            raise ValueError("soft_budget and hard_budget must be integers")
        resource_limits = dict(DEFAULT_RESOURCE_LIMITS)
        resource_limits["model_tokens"] = hard_limit
        supplied_limits = {
            str(key): value
            for key, value in dict(request_map.get("resource_limits", {})).items()
        }
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in supplied_limits.values()
        ):
            raise ValueError("resource_limits values must be integers")
        resource_limits.update(supplied_limits)
        budget = BudgetLedger(soft_limit, hard_limit, resource_limits)
        for task in tasks:
            if task.estimated_tokens is None:
                continue
            reservation = self._task_resource_reservation(task)
            exceeded = sorted(
                dimension
                for dimension in RESOURCE_DIMENSIONS
                if reservation[dimension] > budget.resource_limits[dimension]
            )
            if exceeded:
                detail = ", ".join(
                    f"{dimension}={reservation[dimension]}>"
                    f"{budget.resource_limits[dimension]}"
                    for dimension in exceeded
                )
                raise ValueError(
                    f"task {task.id} reservation exceeds run resource limits: {detail}"
                )
        terminal_policy = str(request_map.get("terminal_policy", "block_descendants"))
        if terminal_policy not in {"block_descendants", "continue"}:
            raise ValueError("terminal_policy must be block_descendants or continue")
        runtime_metadata = dict(request_map.get("metadata", {}))
        if request_map.get("memory_store") is not None:
            runtime_metadata["memory_store"] = str(request_map["memory_store"])
        if request_map.get("memory_scope") is not None:
            runtime_metadata["memory_scope"] = str(request_map["memory_scope"])
        runtime_metadata.setdefault("mode", str(request_map.get("mode", "runtime")))
        created_payload = {
            "objective": request_map.get("objective", ""),
            "workspace_root": str(workspace_root),
            "metadata": runtime_metadata,
            "terminal_policy": terminal_policy,
            "budgets": {
                "soft_limit": soft_limit,
                "hard_limit": hard_limit,
                "resource_limits": dict(budget.resource_limits),
                "tranche_percentages": list(TRANCHE_PERCENTAGES),
                "tranche_limits": budget.snapshot()["tranche_limits"],
                "released_tranches": budget.released_tranches,
                "released_token_limit": budget.released_token_limit,
            },
            "tasks": [task.to_dict() for task in tasks],
            # Context/memory edges remain descriptive and never enter compile_dag.
            "memory_edges": request_map.get("memory_edges", []),
        }
        run_id = requested_run_id
        if not run_id:
            if not idempotency_key:
                raise ValueError("create without run_id requires idempotency_key")
            registry = EventStore(self.root / ".create-registry")
            request_digest = canonical_hash(created_payload)
            # Serialize find-then-append intent resolution.  Without this
            # registry mutex, two first callers can both generate a run ID
            # for one idempotency key before either intent is durable.
            with transition_lock(registry.run_dir / ".transition.lock"):
                prior_intent = registry.find_idempotency(idempotency_key)
                if prior_intent is not None:
                    if (
                        prior_intent.event_type != "run.create.intent"
                        or prior_intent.payload.get("request_digest") != request_digest
                    ):
                        raise IdempotencyConflict(
                            f"idempotency key payload changed: {idempotency_key}"
                        )
                    run_id = str(prior_intent.payload["run_id"])
                else:
                    run_id = uuid7_str()
                    registry.append(
                        "run.create.intent",
                        "sips-runtime-create-registry",
                        {"run_id": run_id, "request_digest": request_digest},
                        idempotency_key=idempotency_key,
                    )
        # The resolved run ID (including one recovered from the registry) is
        # the mutex key for the complete existence/idempotency/append
        # transaction.  This keeps concurrent creates deterministic and also
        # makes EventStore head initialization part of that transaction.
        with transition_lock(self._run_dir(run_id) / ".transition.lock"):
            store = self._store(run_id)
            if store.revision:
                prior = self._idempotent_event(run_id, idempotency_key, {"run.created"})
                if prior is not None:
                    if canonical_hash(prior.payload) != canonical_hash(created_payload):
                        raise IdempotencyConflict(
                            f"idempotency key payload changed: {idempotency_key}"
                        )
                    return self._state(run_id)
                raise ControllerError(f"run already exists: {run_id}")
            store.append(
                "run.created",
                run_id,
                created_payload,
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
            )
            (self._run_dir(run_id) / "receipts").mkdir(parents=True, exist_ok=True)
            (self._run_dir(run_id) / "slices").mkdir(parents=True, exist_ok=True)
        return self._state(run_id)

    @guarded_transition
    def submit(
        self,
        run_id: str,
        payload: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        state = self._state(run_id)
        submit_payload = dict(payload or {})
        prior = self._idempotent_event(run_id, idempotency_key, {"run.submitted"})
        if prior is not None:
            if canonical_hash(prior.payload) != canonical_hash(submit_payload):
                raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
            self._write_graph_receipt(run_id, prior)
            return state
        if state["status"] != "pending":
            raise InvalidTransition(f"cannot submit run in state {state['status']}")
        event = self._store(run_id).append(
            "run.submitted", run_id, submit_payload, idempotency_key=idempotency_key, expected_revision=expected_revision
        )
        state = self._state(run_id)
        if state.get("status") in TERMINAL_RUN_STATES:
            self._write_graph_receipt(run_id, event)
        return state

    @guarded_transition
    def lease(
        self,
        run_id: str,
        owner: str,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        if (
            not isinstance(owner, str)
            or not owner.strip()
            or owner != owner.strip()
        ):
            raise ValueError("lease owner must be a non-empty trimmed string")
        prior = self._idempotent_event(run_id, idempotency_key, {"task.leased"})
        if prior is not None:
            if str(prior.payload.get("owner", "")) != owner:
                raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
            if task_id and str(prior.payload.get("task_id", "")) != task_id:
                raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
            return self._state(run_id)
        state = self._state(run_id)
        if state["status"] not in {"running", "pending"}:
            raise InvalidTransition(f"cannot lease run in state {state['status']}")
        completed = {
            candidate_id
            for candidate_id, item in state["tasks"].items()
            if item.get("status") == "succeeded"
            or (
                state.get("terminal_policy") == "continue"
                and item.get("status") in TERMINAL_TASK_STATES
            )
        }
        running = {
            active_task_id
            for active_task_id, item in state["tasks"].items()
            if self._lease_active(item)
        }
        if len(running) >= MAX_CONCURRENCY:
            raise InvalidTransition(f"concurrency limit reached: {MAX_CONCURRENCY}")
        graph = compile_dag([TaskSpec.from_dict(item["spec"]) for item in state["tasks"].values()])
        ready = tuple(
            task
            for task in graph.ready(completed, running)
            if state["tasks"][task.id].get("status") == "pending"
            or (
                state["tasks"][task.id].get("status") in {"leased", "running"}
                and not self._lease_active(state["tasks"][task.id])
            )
        )
        if task_id:
            chosen = next((task for task in ready if task.id == task_id), None)
        else:
            chosen = ready[0] if ready else None
        if chosen is None:
            raise InvalidTransition("no ready task available")
        chosen_state = state["tasks"][chosen.id]
        if int(chosen_state.get("attempts", 0)) > chosen.retry_limit:
            raise InvalidTransition(f"retry limit exhausted: {chosen.id}")
        if not self._active_path_compatible(state, chosen):
            raise InvalidTransition(f"task paths conflict: {chosen.id}")
        # Rebuild budget authority from event-derived state.  A missing estimate
        # is unknown cost and therefore cannot be leased.
        budget_cfg = state.get("budgets", self._initial()["budgets"])
        store = self._store(run_id)
        budget = BudgetLedger(
            int(budget_cfg.get("soft_limit", 60_000)),
            int(budget_cfg.get("hard_limit", 120_000)),
            budget_cfg.get("resource_limits", DEFAULT_RESOURCE_LIMITS),
            released_tranches=self._released_tranche_count(store),
        )
        charged = self._charged_resources(store)
        budget._spent = charged["model_tokens"]  # type: ignore[attr-defined]
        budget._spent_resources = dict(charged)  # type: ignore[attr-defined]
        resources = self._task_resource_reservation(chosen)
        released_before = budget.released_tranches
        while True:
            try:
                reservation = budget.reserve(chosen.id, chosen.estimated_tokens, resources)
                break
            except TrancheNotReleased:
                if not budget.release_next_tranche():
                    raise
        released_after = budget.released_tranches
        context_packet = self._context_for_task(state, chosen)
        reserved_resources = dict(reservation.resources or {})
        context_tokens = int(context_packet.get("response_token_estimate", 0))
        if context_tokens > int(reserved_resources.get("retrieval_tokens", 0)):
            raise InvalidTransition(
                f"context retrieval exceeds reservation for task {chosen.id}: "
                f"{context_tokens}>{reserved_resources.get('retrieval_tokens', 0)}"
            )
        context_bytes = len(
            canonical_json(context_packet).encode("utf-8")
        )
        if context_bytes > int(reserved_resources.get("memory_bytes", 0)):
            raise InvalidTransition(
                f"context memory exceeds reservation for task {chosen.id}: "
                f"{context_bytes}>{reserved_resources.get('memory_bytes', 0)}"
            )
        token = self._next_fencing_token(store)
        now = time.time()
        lease = Lease(
            task_id=chosen.id,
            owner=owner,
            fencing_token=token,
            acquired_at=now,
            last_heartbeat=now,
            expires_at=now + LEASE_TTL_SECONDS,
        )
        payload = {
            "task_id": chosen.id,
            "owner": owner,
            "lease": {
                **lease.to_dict(),
                "heartbeat_interval_seconds": 15,
                "next_heartbeat_due": now + 15,
                "attempt_ceiling_seconds": int(ATTEMPT_CEILING_SECONDS),
            },
            "reservation": reservation.to_dict(),
            "tranche_release": {
                "released_before": released_before,
                "released_after": released_after,
                "advanced": released_after > released_before,
                "released_token_limit": budget.released_token_limit,
                "tranche_limits": list(budget.tranche_limits),
                "reason": "accepted_reservation_demand"
                if released_after > released_before
                else "already_within_released_tranche",
            },
            "context": context_packet,
            "side_effect_intent": {
                "kind": "worker_execution",
                "journaled_before_dispatch": True,
            },
        }
        store.append(
            "task.leased", run_id, payload, idempotency_key=idempotency_key, expected_revision=expected_revision
        )
        return self._state(run_id)

    @guarded_transition
    def advance(
        self,
        run_id: str,
        payload: Mapping[str, Any] | SliceResult,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        if isinstance(payload, SliceResult):
            raw = payload.to_dict()
        else:
            raw = dict(payload)
        # Selectors are path-backed identities.  Keep them typed and bounded
        # before the historical ``str(... or ...)`` fallback can target a
        # different task (for example, ``True`` becoming ``"True"``).
        task_aliases: list[str] = []
        for key in ("task_id", "slice_id", "taskId", "sliceId"):
            if key not in raw or raw[key] is None:
                continue
            try:
                validate_safe_identifier(raw[key], label=key)
            except ValueError as exc:
                raise InvalidTransition(f"{key} must be a safe task identifier") from exc
            task_aliases.append(raw[key])
        if task_aliases and any(value != task_aliases[0] for value in task_aliases[1:]):
            raise InvalidTransition("task_id and slice_id aliases disagree")
        request_digest = canonical_hash(raw)
        prior = self._idempotent_event(run_id, idempotency_key, {"task.advanced", "task.heartbeat"})
        if prior is not None:
            if str(prior.payload.get("request_digest", "")) != request_digest:
                raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
            if prior.event_type == "task.advanced":
                prior_task_id = str(prior.payload.get("task_id", ""))
                self._write_result_receipt(run_id, prior_task_id, prior)
                self._write_graph_receipt(run_id, prior)
            return self._state(run_id)
        state = self._state(run_id)
        task_id = task_aliases[0] if task_aliases else ""
        if not task_id:
            leased = [key for key, item in state["tasks"].items() if item.get("status") == "leased"]
            if len(leased) != 1:
                raise InvalidTransition("advance requires task_id when multiple tasks are leased")
            task_id = leased[0]
        item = state["tasks"].get(task_id)
        if item is None:
            raise InvalidTransition(f"unknown task: {task_id}")
        owner_value = raw.get("owner")
        token_aliases = [
            raw[key]
            for key in ("fencing_token", "fence_token", "fenceToken", "token")
            if key in raw
        ]
        for supplied_token in token_aliases:
            if type(supplied_token) is not int or isinstance(supplied_token, bool):
                raise StaleLeaseError(f"invalid fencing token for task {task_id}")
        if token_aliases and any(value != token_aliases[0] for value in token_aliases[1:]):
            raise StaleLeaseError(f"fencing token aliases disagree for task {task_id}")
        token = token_aliases[0] if token_aliases else None
        if not isinstance(owner_value, str) or not owner_value.strip():
            raise StaleLeaseError(f"missing lease fencing for task {task_id}")
        if (
            not isinstance(token, int)
            or isinstance(token, bool)
            or token < 1
        ):
            raise StaleLeaseError(f"missing lease fencing for task {task_id}")
        owner = owner_value
        persisted_lease = item.get("lease") or {}
        try:
            current_time = time.time()
            valid = (
                str(persisted_lease.get("owner")) == owner
                and int(persisted_lease.get("fencing_token")) == int(token)
                and current_time < float(persisted_lease.get("expires_at"))
                and current_time - float(persisted_lease.get("acquired_at")) < ATTEMPT_CEILING_SECONDS
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise StaleLeaseError(f"stale fencing token for task {task_id}")
        result = raw.get("result", raw)
        if isinstance(result, SliceResult):
            result = result.to_dict()
        result = dict(result)
        supplied_hash = result.pop("result_hash", None)
        if supplied_hash and str(supplied_hash) != canonical_hash(result):
            raise InvalidTransition("result_hash does not match the submitted SliceResult")
        expected_attempt_id = (
            f"{task_id}-attempt-{int(item.get('attempts', 0)):03d}"
        )
        expected_lease_id = f"{run_id}:{task_id}:{int(token)}"

        def require_bound_value(
            label: str, keys: tuple[str, ...], expected: object
        ) -> None:
            for key in keys:
                if key not in result:
                    continue
                if type(result[key]) is not str or result[key] != expected:
                    raise InvalidTransition(
                        f"result {label} does not match the active lease"
                    )

        def require_bound_token(keys: tuple[str, ...], expected: int) -> None:
            for key in keys:
                if key not in result:
                    continue
                supplied = result[key]
                if (
                    not isinstance(supplied, int)
                    or isinstance(supplied, bool)
                    or supplied != expected
                ):
                    raise InvalidTransition(
                        "result fencing_token does not match the active lease"
                    )

        require_bound_value("run_id", ("run_id", "runId"), run_id)
        require_bound_value(
            "task_id", ("task_id", "taskId", "slice_id", "sliceId"), task_id
        )
        require_bound_value("owner", ("owner", "lease_owner"), owner)
        require_bound_token(
            ("fencing_token", "fence_token", "fenceToken", "token"),
            int(token),
        )
        require_bound_value(
            "attempt_id", ("attempt_id", "attemptId"), expected_attempt_id
        )
        require_bound_value("lease_id", ("lease_id", "leaseId"), expected_lease_id)
        if "lease" in result or "active_lease" in result:
            embedded_lease = result.get("lease", result.get("active_lease"))
            if not isinstance(embedded_lease, Mapping):
                raise InvalidTransition("result lease must be an object")
            if (
                embedded_lease.get("active") is False
                or embedded_lease.get("valid") is False
                or embedded_lease.get("expired") is True
            ):
                raise InvalidTransition("result lease is not active")
            required_lease_bindings = {"owner", "fencing_token"}
            for label, keys, expected in (
                ("owner", ("owner", "lease_owner"), owner),
                (
                    "fencing_token",
                    ("fencing_token", "fence_token", "fenceToken", "token"),
                    int(token),
                ),
                ("task_id", ("task_id", "taskId", "slice_id", "sliceId"), task_id),
                (
                    "acquired_at",
                    ("acquired_at", "acquiredAt"),
                    persisted_lease.get("acquired_at"),
                ),
                (
                    "expires_at",
                    ("expires_at", "expiresAt"),
                    persisted_lease.get("expires_at"),
                ),
            ):
                present = False
                for key in keys:
                    if key not in embedded_lease:
                        continue
                    present = True
                    supplied = embedded_lease[key]
                    invalid = (
                        not isinstance(supplied, int)
                        or isinstance(supplied, bool)
                        or supplied != expected
                    ) if label == "fencing_token" else (
                        (
                            type(supplied) not in (int, float)
                            or isinstance(supplied, bool)
                            or supplied != expected
                        )
                        if label in {"acquired_at", "expires_at"}
                        else (type(supplied) is not str or supplied != expected)
                    )
                    if invalid:
                        raise InvalidTransition(
                            f"result lease {label} does not match the active lease"
                        )
                if label in required_lease_bindings and not present:
                    raise InvalidTransition(
                        f"result lease {label} does not match the active lease"
                    )
            result["lease"] = {
                **dict(persisted_lease),
                "active": True,
                "owner": owner,
                "fencing_token": int(token),
            }
            result.pop("active_lease", None)
        result_status = str(result.get("status", "succeeded")).lower()
        if result_status == "running":
            now = time.time()
            if now - float(persisted_lease.get("acquired_at", now)) >= ATTEMPT_CEILING_SECONDS:
                raise StaleLeaseError(f"attempt ceiling exceeded for task {task_id}")
            heartbeat_lease = {
                **persisted_lease,
                "last_heartbeat": now,
                "next_heartbeat_due": now + 15,
                "expires_at": min(
                    now + LEASE_TTL_SECONDS,
                    float(persisted_lease.get("acquired_at", now))
                    + ATTEMPT_CEILING_SECONDS,
                ),
            }
            event_payload = {
                "task_id": task_id,
                "owner": owner,
                "fencing_token": int(token),
                "lease": heartbeat_lease,
                "request_digest": request_digest,
            }
            self._store(run_id).append(
                "task.heartbeat",
                run_id,
                event_payload,
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
            )
            return self._state(run_id)

        spec = TaskSpec.from_dict(item["spec"])
        expected_plan_digest = canonical_hash(spec.to_dict())
        submitted_result_digest = canonical_hash(
            {
                key: value
                for key, value in result.items()
                if key not in {"reviewer", "reviewer_receipt", "reviewer_id"}
            }
        )
        if result_status == "retry" and int(item.get("attempts", 0)) > spec.retry_limit:
            raise InvalidTransition(f"retry limit exhausted: {task_id}")
        changed_paths = result.get("changed_paths", [])
        if isinstance(changed_paths, str):
            changed_paths = [changed_paths]
        elif not isinstance(changed_paths, (list, tuple, set, frozenset)):
            raise InvalidTransition("changed_paths must contain only strings")
        workspace_root = canonical_path(state.get("workspace_root") or os.getcwd())
        allowed = [canonical_path(workspace_root / path) for path in spec.write_set]
        normalized_changed: list[str] = []
        for changed in changed_paths:
            if type(changed) is not str:
                raise InvalidTransition("changed_paths must contain only strings")
            candidate = canonical_path(Path(changed) if Path(changed).is_absolute() else workspace_root / changed)
            try:
                relative = candidate.relative_to(workspace_root)
            except ValueError as exc:
                raise InvalidTransition(f"changed path escapes workspace: {changed}") from exc
            if not any(candidate == root or root in candidate.parents for root in allowed):
                raise InvalidTransition(f"changed path outside declared write set: {changed}")
            normalized_changed.append(relative.as_posix())
        result["changed_paths"] = sorted(set(normalized_changed))
        if result_status in {"succeeded", "complete", "completed", "done"}:
            evidence_items = result.get("evidence", [])
            if isinstance(evidence_items, Mapping):
                evidence_items = [evidence_items]
            evidence_by_id: dict[str, list[Any]] = {}
            for entry in evidence_items:
                if not isinstance(entry, Mapping):
                    continue
                evidence_id = str(entry.get("id", entry.get("evidence_id", "")))
                if evidence_id:
                    evidence_by_id.setdefault(evidence_id, []).append(entry)

            def resolve_evidence(values: Any) -> list[Any]:
                if isinstance(values, (str, bytes)):
                    values = [values]
                elif isinstance(values, Mapping):
                    values = [values]
                elif not isinstance(values, (list, tuple, set, frozenset)):
                    values = [] if values is None else [values]
                resolved: list[Any] = []
                for entry in values:
                    if isinstance(entry, str) and entry in evidence_by_id:
                        resolved.extend(evidence_by_id[entry])
                    else:
                        resolved.append(entry)
                return resolved

            acceptance_results = result.get("acceptance_results", [])
            if isinstance(acceptance_results, Mapping):
                acceptance_results = list(acceptance_results.values())
            if len(acceptance_results) != len(spec.acceptance):
                if spec.acceptance:
                    raise InvalidTransition(f"acceptance proof count mismatch for task {task_id}")
            for index, criterion_result in enumerate(acceptance_results):
                item_result = (
                    dict(criterion_result)
                    if isinstance(criterion_result, Mapping)
                    else {"ok": bool(criterion_result)}
                )
                evidence = item_result.get("evidence", ())
                resolved_evidence = resolve_evidence(evidence)
                evidence_ok, evidence_reasons = validate_evidence_items(
                    resolved_evidence
                )
                if item_result.get("ok") is not True or not evidence_ok:
                    raise InvalidTransition(
                        f"acceptance criterion {index + 1} lacks passing evidence: "
                        + ", ".join(evidence_reasons or ["criterion_failed"])
                    )
            claims = result.get("claims", [])
            if isinstance(claims, Mapping):
                claims = [claims]
            unsupported: list[str] = []
            for index, claim in enumerate(claims):
                claim_map = dict(claim) if isinstance(claim, Mapping) else {"text": claim}
                if claim_map.get("material", True) is False:
                    continue
                refs = claim_map.get("evidence_refs", claim_map.get("evidence", ()))
                if isinstance(refs, str):
                    refs = [refs]
                claim_id = str(claim_map.get("id", f"claim-{index + 1}"))
                resolved_evidence = resolve_evidence(refs)
                evidence_ok, _ = validate_evidence_items(resolved_evidence)
                if not refs or not evidence_ok:
                    unsupported.append(claim_id)
            if unsupported:
                raise InvalidTransition(
                    "material claims lack usable evidence: "
                    + ", ".join(sorted(unsupported))
                )
            reviewer_value = result.get("reviewer_receipt", result.get("reviewer"))
            reviewer = dict(reviewer_value) if isinstance(reviewer_value, Mapping) else {}
            raw_reviewer_id = reviewer.get("id", result.get("reviewer_id", ""))
            reviewer_id = raw_reviewer_id if type(raw_reviewer_id) is str else ""
            reviewer_identity_valid = (
                type(raw_reviewer_id) is str
                and raw_reviewer_id == reviewer_id
                and raw_reviewer_id
                and raw_reviewer_id == raw_reviewer_id.strip()
                and 0 < len(reviewer_id) <= 128
                and all(ord(character) >= 32 and ord(character) != 127 for character in reviewer_id)
            )
            reviewer_required = (
                str(spec.risk).strip().lower() in HIGH_IMPACT
                or bool(
                    {tag.lower() for tag in spec.risk_tags}.intersection(
                        HIGH_IMPACT_RISK_TAGS
                    )
                )
            )
            reviewer_valid = False
            if reviewer_required:
                review_status = str(
                    reviewer.get("status", reviewer.get("outcome", ""))
                ).lower()
                review_evidence = reviewer.get("evidence", ())
                review_evidence_ok, _ = validate_evidence_items(
                    resolve_evidence(review_evidence)
                )
                supplied_review_digest = reviewer.get("receipt_digest", "")
                review_body = {
                    key: value
                    for key, value in reviewer.items()
                    if key != "receipt_digest"
                }
                reviewer_bound = (
                    reviewer_identity_valid
                    and reviewer_id.casefold() != owner.strip().casefold()
                    and reviewer.get("independent") is True
                    and review_status in {"passed", "approved", "verified"}
                    and type(reviewer.get("run_id")) is str
                    and reviewer.get("run_id") == run_id
                    and type(reviewer.get("task_id")) is str
                    and reviewer.get("task_id") == task_id
                    and type(reviewer.get("plan_digest")) is str
                    and reviewer.get("plan_digest") == expected_plan_digest
                    and type(reviewer.get("result_digest")) is str
                    and reviewer.get("result_digest") == submitted_result_digest
                    and review_evidence_ok
                    and type(supplied_review_digest) is str
                    and supplied_review_digest
                    == canonical_hash(review_body)
                )
                if not reviewer_bound:
                    raise InvalidTransition(f"independent reviewer required for task {task_id}")
                reviewer_valid = True
            quality = evaluate_gates(
                result.get("gates") if isinstance(result.get("gates"), Mapping) else {},
                impact=spec.risk,
                risk_tags=spec.risk_tags,
                reviewer_tags=(
                    (f"reviewer:{reviewer_id}",) if reviewer_valid else ()
                ),
            )
            if not quality["ok"]:
                raise InvalidTransition(
                    "quality gates failed: "
                    + ", ".join(quality["failed_gates"] + quality["missing_reviewer_tags"])
                )
            result["quality"] = quality
        reservation = item.get("reservation") or {}
        reserved_tokens = reservation.get("tokens", spec.estimated_tokens)
        if reserved_tokens is None:
            raise InvalidTransition(f"unknown usage for task {task_id}")
        reserved_resources = dict(reservation.get("resources") or {})
        reserved_resources.setdefault("model_tokens", int(reserved_tokens))
        usage_input = result.get("usage") if isinstance(result.get("usage"), Mapping) else {}
        measured_input = (
            usage_input.get("resources")
            if isinstance(usage_input.get("resources"), Mapping)
            else usage_input
        )
        unknown_usage_dimensions = sorted(
            str(key)
            for key in measured_input
            if type(key) is not str or key not in RESOURCE_DIMENSIONS
        )
        if unknown_usage_dimensions:
            raise InvalidTransition(
                "usage contains unknown resource dimensions: "
                + ", ".join(unknown_usage_dimensions)
            )
        if result.get("cost_tokens") is not None:
            measured_input = {**dict(measured_input), "model_tokens": result["cost_tokens"]}
        measured_dimensions = {
            dimension
            for dimension in RESOURCE_DIMENSIONS
            if measured_input.get(dimension) is not None
        }
        actual_resources: dict[str, int] = {}
        for dimension in RESOURCE_DIMENSIONS:
            value = measured_input.get(
                dimension, reserved_resources.get(dimension, 0)
            )
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise InvalidTransition(
                    f"usage {dimension} must be a non-negative integer"
                )
            actual_resources[dimension] = value
        exceeded = [
            dimension
            for dimension in RESOURCE_DIMENSIONS
            if actual_resources[dimension] > int(reserved_resources.get(dimension, 0))
        ]
        if exceeded:
            raise InvalidTransition(
                "actual usage exceeds reservation: " + ", ".join(sorted(exceeded))
            )
        unknown_dimensions = sorted(set(RESOURCE_DIMENSIONS) - measured_dimensions)
        result["cost_tokens"] = actual_resources["model_tokens"]
        result["usage"] = {
            **dict(usage_input),
            "resources": actual_resources,
            "source": "provider" if not unknown_dimensions else "reservation",
            "provider_reported_dimensions": sorted(measured_dimensions),
            "unknown_dimensions": unknown_dimensions,
            "efficiency_claim_eligible": not unknown_dimensions,
        }
        result["run_id"] = run_id
        result["task_id"] = task_id
        result["slice_id"] = task_id
        result["attempt_id"] = expected_attempt_id
        result["lease_id"] = expected_lease_id
        result["owner"] = owner
        result["lease_owner"] = owner
        result["fencing_token"] = int(token)
        result["fence_token"] = int(token)
        require_bound_value(
            "plan_digest", ("plan_digest", "plan_id", "planId"), expected_plan_digest
        )
        result["plan_digest"] = expected_plan_digest
        result["plan_id"] = expected_plan_digest
        leased_context = item.get("context") if isinstance(item.get("context"), Mapping) else {}
        supplied_context_digest = leased_context.get("digest")
        if supplied_context_digest:
            if type(supplied_context_digest) is not str:
                raise InvalidTransition("leased context digest must be a string")
            expected_context_digest = supplied_context_digest
        else:
            expected_context_digest = canonical_hash(leased_context)
        require_bound_value(
            "context_digest",
            ("context_digest", "context_id", "contextId"),
            expected_context_digest,
        )
        result["context_digest"] = expected_context_digest
        result["context_id"] = expected_context_digest
        result["lease"] = {
            **dict(persisted_lease),
            "active": True,
            "owner": owner,
            "fencing_token": int(token),
        }
        for collection in ("claims", "evidence", "artifacts", "blockers"):
            result.setdefault(collection, [])
        result.setdefault("lesson_candidate", None)
        result_usage = dict(result["usage"])
        result_usage["runtime_output_token_estimate"] = 0
        result["usage"] = result_usage
        provider_or_reserved_output = actual_resources["output_tokens"]
        output_estimate = 0
        result_bytes = 0
        for _ in range(16):
            projected_result = {**result, "result_hash": "0" * 64}
            encoded_result = canonical_json(projected_result).encode("utf-8")
            measured_output = max(1, (len(encoded_result) + 3) // 4)
            charged_output = max(provider_or_reserved_output, measured_output)
            if (
                measured_output == output_estimate
                and actual_resources["output_tokens"] == charged_output
            ):
                result_bytes = len(encoded_result)
                break
            output_estimate = measured_output
            result_usage["runtime_output_token_estimate"] = output_estimate
            actual_resources["output_tokens"] = charged_output
            result_usage["resources"] = actual_resources
        else:
            encoded_result = canonical_json(
                {**result, "result_hash": "0" * 64}
            ).encode("utf-8")
            result_bytes = len(encoded_result)
            output_estimate = max(1, (result_bytes + 3) // 4)
            result_usage["runtime_output_token_estimate"] = output_estimate
            actual_resources["output_tokens"] = max(
                provider_or_reserved_output, output_estimate
            )
            result_usage["resources"] = actual_resources
            # The two numeric fields affect their own serialized width.  A
            # final conservative pass must agree with the persisted payload.
            encoded_result = canonical_json(
                {**result, "result_hash": "0" * 64}
            ).encode("utf-8")
            result_bytes = len(encoded_result)
            output_estimate = max(1, (result_bytes + 3) // 4)
            result_usage["runtime_output_token_estimate"] = output_estimate
            actual_resources["output_tokens"] = max(
                provider_or_reserved_output, output_estimate
            )
        output_cap = int(reserved_resources.get("output_tokens", 0))
        if output_estimate > output_cap:
            raise InvalidTransition(
                f"result output exceeds reservation for task {task_id}: "
                f"{output_estimate}>{output_cap}"
            )
        memory_cap = int(reserved_resources.get("memory_bytes", 0))
        if result_bytes > memory_cap:
            raise InvalidTransition(
                f"result memory exceeds reservation for task {task_id}: "
                f"{result_bytes}>{memory_cap}"
            )
        result_usage["resources"] = actual_resources
        success_aliases = {"succeeded", "complete", "completed", "done"}
        prospective_statuses = {
            other_id: (
                "succeeded"
                if other_id == task_id and result_status in success_aliases
                else str(other["status"])
            )
            for other_id, other in state["tasks"].items()
        }
        required_task_ids = sorted(self._effective_required_ids(state))
        if all(
            prospective_statuses.get(task_id) == "succeeded"
            for task_id in required_task_ids
        ):
            prospective_results: list[dict[str, Any]] = []
            for other_id in required_task_ids:
                if other_id == task_id:
                    prospective_results.append(result)
                    continue
                prior_result = state["tasks"][other_id].get("result")
                if isinstance(prior_result, Mapping):
                    prospective_results.append(dict(prior_result))
            merged = fan_in(
                prospective_results,
                expected_task_ids=required_task_ids,
                require_lease=False,
                legacy=True,
            )
            if merged.get("ok") is not True:
                conflict_ids = sorted(
                    {
                        str(conflict.get("id", conflict.get("task_id", "unknown")))
                        for conflict in [
                            *merged.get("conflicts", []),
                            *merged.get("result_conflicts", []),
                        ]
                    }
                )
                detail = ", ".join(conflict_ids) or "incomplete or invalid slice"
                raise InvalidTransition(f"fan-in gate failed: {detail}")
        result_hash = canonical_hash(result)
        result["result_hash"] = result_hash
        event_payload = {
            "task_id": task_id,
            "owner": owner,
            "fencing_token": int(token),
            "result": result,
            "request_digest": request_digest,
        }
        event = self._store(run_id).append(
            "task.advanced", run_id, event_payload, idempotency_key=idempotency_key, expected_revision=expected_revision
        )
        self._write_result_receipt(run_id, task_id, event)
        self._write_graph_receipt(run_id, event)
        if result_status in TERMINAL_TASK_STATES | {"complete", "completed", "retry"}:
            # Durable state is the authority; in-memory helpers are merely a
            # local optimization and may be absent in a fresh process.
            active = self.leases.get(task_id)
            if active is not None and active.owner == owner and active.fencing_token == int(token):
                self.leases.release(task_id, owner, int(token))
            self.locks.release(task_id)
        return self._state(run_id)

    @staticmethod
    def _memory_record_exists(
        path: Path, expected_record: Mapping[str, Any]
    ) -> bool:
        if not path.exists():
            return False
        record_id = str(expected_record.get("id", ""))
        matches: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if isinstance(value, Mapping) and str(value.get("id", "")) == record_id:
                        matches.append(dict(value))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError(f"cannot verify Memory Fabric writer target: {exc}") from exc
        if not matches:
            return False
        expected_digest = canonical_hash(dict(expected_record))
        if (
            len(matches) != 1
            or canonical_hash(matches[0]) != expected_digest
        ):
            raise IdempotencyConflict(
                f"Memory Fabric record id already has different content: {record_id}"
            )
        return True

    @staticmethod
    def _memory_reference_audit(
        path: Path, references: Any
    ) -> dict[str, Any]:
        if isinstance(references, Mapping):
            references = [references]
        elif not isinstance(references, (list, tuple)):
            references = [] if references in (None, "") else [references]
        normalized: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []
        for index, reference in enumerate(references):
            if not isinstance(reference, Mapping):
                invalid.append({"type": "invalid_reference", "index": index})
                continue
            item = dict(reference)
            target_id = str(item.get("target_id", item.get("target", item.get("id", "")))).strip()
            edge_type = str(item.get("type", item.get("edge_type", "references"))).strip().lower()
            if not target_id:
                invalid.append({"type": "invalid_reference", "index": index})
                continue
            normalized.append({**item, "target_id": target_id, "type": edge_type})

        records: list[dict[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []
        if normalized:
            if path.exists() and not path.is_file():
                parse_errors.append({"type": "memory_store_not_file", "path": str(path)})
            elif path.is_file():
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        for line_number, line in enumerate(handle, 1):
                            if not line.strip():
                                continue
                            value = json.loads(line)
                            if not isinstance(value, Mapping):
                                parse_errors.append(
                                    {"type": "invalid_memory_record", "line": line_number}
                                )
                                continue
                            records.append(dict(value))
                except (OSError, json.JSONDecodeError) as exc:
                    parse_errors.append(
                        {"type": "memory_store_unreadable", "error": f"{type(exc).__name__}: {exc}"}
                    )
        by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: set[str] = set()
        for record in records:
            record_id = str(record.get("id", "")).strip()
            if not record_id:
                continue
            if record_id in by_id:
                duplicate_ids.add(record_id)
            by_id[record_id] = record
        dangling = sorted(
            {
                str(reference["target_id"])
                for reference in normalized
                if str(reference["target_id"]) not in by_id
            }
        )
        conflicts = [*invalid, *parse_errors]
        conflicts.extend(
            {"type": "duplicate_memory_id", "target_id": record_id}
            for record_id in sorted(duplicate_ids)
        )
        for reference in normalized:
            target_id = str(reference["target_id"])
            target = by_id.get(target_id)
            if target is None:
                continue
            if (
                reference["type"] in {"contradicts", "supersedes"}
                and str(target.get("status", "active")).lower() == "active"
            ):
                conflicts.append(
                    {
                        "type": f"active_{reference['type']}_target",
                        "target_id": target_id,
                    }
                )
        return {
            "ok": not conflicts and not dangling,
            "references": normalized,
            "known_record_ids": sorted(by_id),
            "dangling": dangling,
            "conflicts": conflicts,
            "store_digest": canonical_hash(records),
            "store": str(path),
        }

    @guarded_transition
    def promote(
        self,
        run_id: str,
        lesson: Mapping[str, Any],
        *,
        activate: bool = False,
        memory_store: str | os.PathLike[str] | None = None,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        if type(activate) is not bool:
            raise ValueError("activate must be a boolean")
        state = self._state(run_id)
        receipt_path = self._run_dir(run_id) / "receipts" / "graph-receipt.json"
        receipt = self.read_receipt(run_id)
        target = Path(
            memory_store
            or os.environ.get("CODEX_MEMORY_FABRIC_STORE")
            or (Path.home() / ".codex" / "memory-fabric" / "memory.jsonl")
        ).expanduser().resolve()
        memory_audit = self._memory_reference_audit(
            target, lesson.get("references", lesson.get("refs", ()))
        )
        structured = (
            dict(receipt.get("structured", {}))
            if isinstance(receipt.get("structured"), Mapping)
            else {}
        )
        all_task_results = [
            dict(item)
            for item in structured.get("task_results", ())
            if isinstance(item, Mapping)
        ]
        required_receipt_ids = {
            str(value) for value in structured.get("required_task_ids", ())
        }
        task_results = [
            item
            for item in all_task_results
            if not required_receipt_ids
            or str(item.get("task_id", item.get("slice_id", "")))
            in required_receipt_ids
        ]
        unknown_dimensions: set[str] = set()
        usage_eligible = bool(task_results)
        for task_result in task_results:
            usage = (
                task_result.get("usage")
                if isinstance(task_result.get("usage"), Mapping)
                else {}
            )
            unknown_dimensions.update(
                str(value) for value in usage.get("unknown_dimensions", ())
            )
            usage_eligible = usage_eligible and (
                usage.get("efficiency_claim_eligible") is True
                and str(task_result.get("status", "")).lower()
                in {"succeeded", "complete", "completed", "done"}
            )
        receipt_conflicts = [
            dict(item) if isinstance(item, Mapping) else item
            for item in (
                list(structured.get("conflicts", ()))
                + list(structured.get("result_conflicts", ()))
            )
        ]
        receipt_digest = str(receipt.get("digest", ""))
        authoritative_usage = {
            "source": "graph_receipt",
            "receipt_digest": receipt_digest,
            "task_count": len(task_results),
            "unknown_dimensions": sorted(unknown_dimensions),
            "efficiency_claim_eligible": (
                usage_eligible and not unknown_dimensions
            ),
        }
        authoritative_conflict_audit = {
            "ok": (
                str(receipt.get("status", "")) == "succeeded"
                and not receipt_conflicts
                and memory_audit["ok"] is True
            ),
            "source": "graph_receipt_and_memory_store",
            "receipt_digest": receipt_digest,
            "memory_store": str(target),
            "memory_store_digest": memory_audit["store_digest"],
            "conflicts": [*receipt_conflicts, *memory_audit["conflicts"]],
        }
        request_digest = canonical_hash(
            {
                "lesson": dict(lesson),
                "activate": activate,
                "memory_store": str(target),
            }
        )
        bound = {
            **dict(lesson),
            "run_id": run_id,
            "receipt_digest": receipt_digest,
            "evidence_path": str(lesson.get("evidence_path") or receipt_path),
            "provenance_type": str(lesson.get("provenance_type") or "source_backed_agent_run"),
            # Promotion eligibility is receipt-derived authority. Callers may
            # provide descriptive usage or audit fields, but cannot attest
            # themselves into an active lesson.
            "usage": authoritative_usage,
            "conflict_audit": authoritative_conflict_audit,
            "known_record_ids": memory_audit["known_record_ids"],
            "references": memory_audit["references"],
        }
        assessed = promote_lesson(bound, activate=activate)
        candidate = {
            **assessed,
            "status": "candidate",
            "verify_before_use": True,
            "proposed_status": assessed.get("status", "candidate"),
        }
        prior = self._idempotent_event(
            run_id, idempotency_key, {"memory.promotion.candidate"}
        )
        recorded_candidate: dict[str, Any] | None = None
        if prior is not None:
            if prior.payload.get("request_digest") != request_digest:
                raise IdempotencyConflict(
                    f"idempotency key payload changed: {idempotency_key}"
                )
            receipt_event = self._store(run_id).find_idempotency(
                f"{idempotency_key}:receipt"
            )
            if receipt_event is not None:
                result_state = self._state(run_id)
                result_state["promotion"] = dict(
                    receipt_event.payload.get("promotion", {})
                )
                return result_state
            candidate_event = prior
            prior_promotion = prior.payload.get("promotion", {})
            if isinstance(prior_promotion, Mapping) and isinstance(
                prior_promotion.get("candidate"), Mapping
            ):
                recorded_candidate = dict(prior_promotion["candidate"])
        else:
            candidate_event = self._store(run_id).append(
                "memory.promotion.candidate",
                run_id,
                {
                    "request_digest": request_digest,
                    "memory_store": str(target),
                    "memory_store_audit_digest": memory_audit["store_digest"],
                    "promotion": {
                        "ok": True,
                        "candidate": candidate,
                        "activated": False,
                    },
                },
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
            )
        if not activate:
            # Candidate-only retries replay the immutable candidate intent.
            # Activation resumes are different: the target store is mutable,
            # so the freshly assessed candidate above must control eligibility.
            if recorded_candidate is not None:
                candidate = recorded_candidate
            result_state = self._state(run_id)
            result_state["promotion"] = {"ok": True, "candidate": candidate, "activated": False}
            return result_state

        promotion_result: dict[str, Any]
        if state.get("status") not in TERMINAL_RUN_STATES or receipt.get("provisional"):
            promotion_result = {
                "ok": False,
                "candidate": candidate,
                "activated": False,
                "error": "terminal GraphReceipt required before activation",
            }
        elif candidate.get("can_promote") is not True or candidate.get(
            "proposed_status"
        ) != "active":
            promotion_result = {
                "ok": False,
                "candidate": candidate,
                "activated": False,
                "error": "promotion audits failed",
            }
        else:
            record_id = "mem_graph_" + canonical_hash(
                {
                    "run_id": run_id,
                    "receipt_digest": receipt.get("digest"),
                    "lesson": dict(lesson),
                }
            )[:20]
            raw_tags = bound.get("tags", ())
            if isinstance(raw_tags, str):
                raw_tags = (raw_tags,)
            elif not isinstance(raw_tags, (list, tuple, set, frozenset)):
                raw_tags = ()
            normalized_tags = {str(value).strip() for value in raw_tags if str(value).strip()}
            record = {
                "id": record_id,
                "tier": str(candidate.get("tier", "learning")),
                "title": str(bound.get("title") or f"SIPS graph lesson {run_id}"),
                "body": str(bound.get("text", bound.get("body", ""))),
                "scope": str(bound.get("scope", state.get("workspace_root", "global"))),
                "tags": sorted(normalized_tags | {"sips-graph-runtime", "receipt-bound"}),
                "provenance": {
                    "type": str(bound["provenance_type"]),
                    "detail": f"run={run_id};receipt={receipt.get('digest', '')}",
                    "evidence_path": str(bound["evidence_path"]),
                },
                "confidence": str(bound.get("confidence", "medium")),
                "verify_before_use": False,
                "status": "active",
                "run_id": run_id,
                "receipt_digest": receipt.get("digest", ""),
            }
            if memory_audit["references"]:
                record["references"] = memory_audit["references"]
            expected_record: dict[str, Any] | None = None
            try:
                module = importlib.import_module("memory_fabric_jsonl")
                writer = getattr(module, "append_record")
                normalizer = getattr(module, "normalize_record", lambda value: dict(value))
                expected_record = dict(normalizer(record))
                if not self._memory_record_exists(target, expected_record):
                    writer(record, target)
                    if not self._memory_record_exists(target, expected_record):
                        raise ControllerError(
                            "Memory Fabric writer returned without persisting the expected record"
                        )
                promotion_result = {
                    "ok": True,
                    "candidate": candidate,
                    "activated": True,
                    "record_id": record_id,
                    "store": str(target),
                    "receipt_digest": receipt.get("digest", ""),
                }
            except Exception as exc:
                persisted_after_error = False
                if expected_record is not None:
                    try:
                        persisted_after_error = self._memory_record_exists(
                            target, expected_record
                        )
                    except Exception:
                        persisted_after_error = False
                if persisted_after_error:
                    promotion_result = {
                        "ok": True,
                        "candidate": candidate,
                        "activated": True,
                        "record_id": record_id,
                        "store": str(target),
                        "receipt_digest": receipt.get("digest", ""),
                        "writer_outcome": "persisted_despite_writer_exception",
                        "writer_exception": f"{type(exc).__name__}: {exc}",
                    }
                else:
                    promotion_result = {
                        "ok": False,
                        "candidate": candidate,
                        "activated": False,
                        "error": f"Memory Fabric writer failed: {type(exc).__name__}: {exc}",
                    }

        event_type = "memory.promotion.receipt" if promotion_result["ok"] else "memory.promotion.failed"
        promotion_store = self._store(run_id)
        # A candidate intent may be resumed after another valid event has
        # interleaved. The candidate digest preserves linkage; the append must
        # fence against the current verified head, not the candidate's old
        # revision, or a recoverable side effect would remain permanently
        # receipt-less.
        promotion_store.append(
            event_type,
            run_id,
            {
                "candidate_event_digest": candidate_event.event_digest,
                "promotion": promotion_result,
            },
            idempotency_key=f"{idempotency_key}:receipt",
            expected_revision=promotion_store.revision,
        )
        result_state = self._state(run_id)
        result_state["promotion"] = promotion_result
        return result_state

    @guarded_transition
    def cancel(
        self,
        run_id: str,
        reason: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self._require_write_contract(idempotency_key, expected_revision)
        state = self._state(run_id)
        cancel_payload = {"reason": reason or ""}
        prior = self._idempotent_event(run_id, idempotency_key, {"run.canceled"})
        if prior is not None:
            if canonical_hash(prior.payload) != canonical_hash(cancel_payload):
                raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
            self._write_graph_receipt(run_id, prior)
            return self._state(run_id)
        if state["status"] in TERMINAL_RUN_STATES:
            raise InvalidTransition(f"cannot cancel run in state {state['status']}")
        event = self._store(run_id).append(
            "run.canceled",
            run_id,
            cancel_payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )
        self._write_graph_receipt(run_id, event)
        return self._state(run_id)

    def read_status(self, run_id: str) -> dict[str, Any]:
        return self._state(run_id)

    def read_plan(self, run_id: str) -> dict[str, Any]:
        state = self._state(run_id)
        return {"run_id": run_id, "tasks": [item["spec"] for item in state["tasks"].values()]}

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._existing_store(run_id).events()]

    def read_receipt(self, run_id: str) -> dict[str, Any]:
        graph_receipt = self._run_dir(run_id) / "receipts" / "graph-receipt.json"
        if graph_receipt.exists():
            try:
                raw = json.loads(graph_receipt.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidTransition("immutable GraphReceipt is unreadable") from exc
            receipt = self._validate_graph_receipt(run_id, raw)
            revision = receipt.get("revision")
            if (
                not isinstance(revision, int)
                or isinstance(revision, bool)
                or revision < 1
            ):
                raise InvalidTransition("immutable GraphReceipt revision is invalid")
            events = self._existing_store(run_id).events()
            event = next(
                (candidate for candidate in events if candidate.revision == revision),
                None,
            )
            if event is None or event.event_digest != receipt.get("event_digest"):
                raise InvalidTransition(
                    "immutable GraphReceipt event linkage is invalid"
                )
            authoritative = self._write_graph_receipt(run_id, event)
            if authoritative is None:
                raise InvalidTransition(
                    "immutable GraphReceipt exists for a nonterminal run"
                )
            return authoritative
        state = self._state(run_id)
        return {
            "run_id": run_id,
            "revision": state["revision"],
            "head_hash": state["head_hash"],
            "status": state["status"],
            "state": state,
            "provisional": True,
        }

    def read(self, operation: str, run_id: str) -> Any:
        return {
            "status": self.read_status,
            "plan": self.read_plan,
            "events": self.read_events,
            "receipt": self.read_receipt,
        }[operation](run_id)


RunController = RuntimeController
