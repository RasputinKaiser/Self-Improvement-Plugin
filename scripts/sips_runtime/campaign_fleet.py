"""Durable campaign spine and child-thread fleet projection.

The fleet groups durable child work under a campaign without pretending to
own the host's conversation store.  Runtime task events remain authoritative
for execution; this event stream records the campaign contract, external
thread handles, lifecycle state, and retrieval metadata.  Projections are
rebuildable and deliberately bounded so an archived child remains evidence,
not sidebar clutter.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from sips_paths import harness_home
except ImportError:  # pragma: no cover - package import fallback
    from scripts.sips_paths import harness_home

from .canonical import canonical_hash
from .contracts import validate_safe_identifier, uuid7_str
from .events import (
    Event,
    EventIntegrityError,
    EventStore,
    IdempotencyConflict,
    RevisionConflict,
    atomic_write_json,
    transition_lock,
)


FLEET_SCHEMA = "sips.runtime.campaign-fleet.v1"
CAMPAIGN_SCHEMA = "sips.runtime.campaign.v1"
CAMPAIGN_EVENT_SCHEMA = "sips.runtime.campaign-event.v1"
FLEET_DIR_NAME = "campaigns"
MAX_CHILDREN = 200
MAX_ACTIVITY = 50
MAX_SEARCH_LIMIT = 100
MAX_INCARNATIONS = 8

CAMPAIGN_STATUSES = {"active", "completed", "archived", "abandoned"}
CAMPAIGN_TRANSITIONS = {
    "active": {"completed", "archived", "abandoned"},
    "completed": {"active", "archived", "abandoned"},
    "archived": {"active", "abandoned"},
    "abandoned": {"active", "completed", "archived"},
}
CHILD_STATUSES = {
    "planned",
    "active",
    "waiting",
    "blocked",
    "completed",
    "failed",
    "canceled",
    "archived",
    "abandoned",
}
TERMINAL_CHILD_STATUSES = {"completed", "failed", "canceled", "archived", "abandoned"}
OPEN_CHILD_STATUSES = {"planned", "active", "waiting", "blocked"}
ACTIVE_CHILD_STATUSES = OPEN_CHILD_STATUSES
ALLOWED_CHILD_TRANSITIONS = {
    "planned": {"active", "waiting", "blocked", "completed", "failed", "canceled", "abandoned"},
    "active": {"waiting", "blocked", "completed", "failed", "canceled", "abandoned"},
    "waiting": {"active", "blocked", "completed", "failed", "canceled", "abandoned"},
    "blocked": {"active", "waiting", "completed", "failed", "canceled", "abandoned"},
    "completed": {"active", "archived", "abandoned"},
    "failed": {"active", "archived", "abandoned"},
    "canceled": {"active", "archived", "abandoned"},
    "archived": {"active", "abandoned"},
    "abandoned": {"active", "archived"},
}


class CampaignFleetError(RuntimeError):
    """Base error for campaign-fleet operations."""


class CampaignNotFound(CampaignFleetError):
    pass


class CampaignExists(CampaignFleetError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, *, label: str, required: bool = False, max_length: int = 512) -> str:
    if value is None:
        value = ""
    text = str(value).strip()
    if required and not text:
        raise ValueError(f"{label} is required")
    if len(text) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    if "\n" in text or "\r" in text:
        raise ValueError(f"{label} must be single-line text")
    return text


def _identifier(value: Any, *, label: str) -> str:
    return validate_safe_identifier(_text(value, label=label, required=True, max_length=128), label=label)


def _mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _tags(values: Sequence[str] | None) -> list[str]:
    normalized: set[str] = set()
    for item in values or []:
        value = _text(item, label="tag", max_length=64)
        if value:
            normalized.add(value)
    return sorted(normalized)


def fleet_root(home: str | os.PathLike[str] | None = None) -> Path:
    base = Path(home).expanduser().resolve() if home is not None else harness_home().expanduser().resolve()
    return base / "runtime" / "v1" / FLEET_DIR_NAME


def _campaign_dir(campaign_id: str, home: str | os.PathLike[str] | None = None) -> Path:
    return fleet_root(home) / _identifier(campaign_id, label="campaign_id")


def _child_id(value: Any = None) -> str:
    if value:
        return _identifier(value, label="child_id")
    return f"child-{uuid7_str().replace('-', '')[:20]}"


def _child_instance_id(value: Any = None) -> str:
    if value:
        return _identifier(value, label="child_instance_id")
    return f"instance-{uuid7_str().replace('-', '')[:20]}"


def _derived_child_instance_id(*parts: str) -> str:
    return f"instance-{canonical_hash(list(parts))[:20]}"


def _request_digest(payload: Mapping[str, Any]) -> str:
    return canonical_hash(
        {key: value for key, value in payload.items() if key not in {"created_at", "updated_at"}}
    )


def _campaign_id(value: Any = None) -> str:
    if value:
        return _identifier(value, label="campaign_id")
    return f"campaign-{uuid7_str().replace('-', '')[:20]}"


def _event_summary(event: Event) -> dict[str, Any]:
    payload = event.payload
    return {
        "revision": event.revision,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "child_id": payload.get("child_id"),
        "thread_id": payload.get("thread_id"),
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "digest": event.event_digest,
    }


def _initial_state(campaign_id: str) -> dict[str, Any]:
    return {
        "schema": CAMPAIGN_SCHEMA,
        "schema_version": 1,
        "campaign_id": campaign_id,
        "objective": "",
        "contract": {},
        "status": "active",
        "parent_thread_id": "",
        "runtime_run_id": "",
        "workspace_root": "",
        "tags": [],
        "created_at": "",
        "updated_at": "",
        "children": {},
        "revision": 0,
        "head_hash": "",
    }


def _reduce(state: Mapping[str, Any] | None, event: Event) -> dict[str, Any]:
    current = dict(state or _initial_state(event.run_id))
    current["revision"] = event.revision
    current["head_hash"] = event.event_digest
    current["updated_at"] = event.timestamp
    payload = dict(event.payload)
    if event.event_type == "campaign.created":
        current.update(
            {
                "campaign_id": event.run_id,
                "objective": payload.get("objective", ""),
                "contract": payload.get("contract", {}),
                "status": payload.get("status", "active"),
                "parent_thread_id": payload.get("parent_thread_id", ""),
                "runtime_run_id": payload.get("runtime_run_id", ""),
                "workspace_root": payload.get("workspace_root", ""),
                "tags": payload.get("tags", []),
                "created_at": payload.get("created_at", event.timestamp),
                "updated_at": payload.get("created_at", event.timestamp),
            }
        )
        current["children"] = {}
        return current
    if event.event_type == "child.attached":
        child_id = str(payload["child_id"])
        child = dict(payload)
        child.setdefault("status", "planned")
        child.setdefault("created_at", event.timestamp)
        child.setdefault("updated_at", event.timestamp)
        child.setdefault("archived_at", None)
        child.setdefault("reopened_at", None)
        # Legacy campaign events may not have an instance field.  Use a
        # deterministic fallback so rebuilding a projection never changes its
        # digest merely because a UUID was generated during replay.
        child.setdefault("child_instance_id", f"instance-{child_id}")
        child.setdefault(
            "incarnations",
            [
                {
                    "child_instance_id": child["child_instance_id"],
                    "thread_id": child.get("thread_id", ""),
                    "task_id": child.get("task_id", ""),
                    "status": child.get("status", "planned"),
                    "created_at": child.get("created_at", event.timestamp),
                    "updated_at": child.get("updated_at", event.timestamp),
                    "archived_at": child.get("archived_at"),
                    "reopened_from": None,
                }
            ],
        )
        current.setdefault("children", {})[child_id] = child
        return current
    child_id = str(payload.get("child_id", ""))
    if event.event_type in {"child.status_changed", "child.archived", "child.reopened"} and child_id:
        child = dict(current.setdefault("children", {}).get(child_id, {}))
        if event.event_type == "child.reopened":
            previous_instance_id = str(child.get("child_instance_id", ""))
            incarnations = [dict(item) for item in child.get("incarnations", []) if isinstance(item, Mapping)]
            for incarnation in incarnations:
                if str(incarnation.get("child_instance_id", "")) == previous_instance_id:
                    incarnation["status"] = "archived"
                    incarnation["archived_at"] = event.timestamp
                    incarnation["updated_at"] = event.timestamp
            new_instance_id = str(payload.get("child_instance_id") or _child_instance_id())
            incarnations.append(
                {
                    "child_instance_id": new_instance_id,
                    "thread_id": payload.get("thread_id", ""),
                    "task_id": payload.get("task_id", ""),
                    "status": "active",
                    "created_at": event.timestamp,
                    "updated_at": event.timestamp,
                    "archived_at": None,
                    "reopened_from": previous_instance_id or None,
                }
            )
            child.update({key: value for key, value in payload.items() if key != "child_id"})
            child["child_instance_id"] = new_instance_id
            child["incarnations"] = incarnations
            child["updated_at"] = event.timestamp
        else:
            child.update({key: value for key, value in payload.items() if key != "child_id"})
            child["updated_at"] = event.timestamp
            incarnations = [dict(item) for item in child.get("incarnations", []) if isinstance(item, Mapping)]
            current_instance_id = str(child.get("child_instance_id", ""))
            for incarnation in incarnations:
                if str(incarnation.get("child_instance_id", "")) == current_instance_id:
                    incarnation["status"] = child.get("status", incarnation.get("status", "planned"))
                    incarnation["updated_at"] = event.timestamp
                    if child.get("receipt_id"):
                        incarnation["receipt_id"] = child["receipt_id"]
                    if child.get("reason"):
                        incarnation["reason"] = child["reason"]
            child["incarnations"] = incarnations
        if event.event_type == "child.archived":
            child["status"] = "archived"
            child["archived_at"] = event.timestamp
            for incarnation in child.get("incarnations", []):
                if str(incarnation.get("child_instance_id", "")) == str(child.get("child_instance_id", "")):
                    incarnation["status"] = "archived"
                    incarnation["archived_at"] = event.timestamp
        elif event.event_type == "child.reopened":
            child["status"] = "active"
            child["reopened_at"] = event.timestamp
            child["archived_at"] = None
        current.setdefault("children", {})[child_id] = child
        return current
    if event.event_type in {"campaign.status_changed", "campaign.completed", "campaign.archived"}:
        current["status"] = str(payload.get("status", "completed" if event.event_type == "campaign.completed" else "archived"))
        if payload.get("reason"):
            current["status_reason"] = payload["reason"]
        return current
    return current


def _project(events: Sequence[Event], *, include_archived: bool = True, max_children: int = MAX_CHILDREN, max_activity: int = MAX_ACTIVITY) -> dict[str, Any]:
    if not events:
        raise CampaignFleetError("campaign event stream is empty")
    state: dict[str, Any] | None = None
    for event in events:
        state = _reduce(state, event)
    assert state is not None
    all_children = [dict(item) for item in state.get("children", {}).values()]
    for child in all_children:
        incarnations = [dict(item) for item in child.get("incarnations", []) if isinstance(item, Mapping)]
        child["incarnation_count"] = len(incarnations)
        child["incarnations"] = incarnations[-MAX_INCARNATIONS:]
    all_children.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))))
    archived = [item for item in all_children if item.get("status") == "archived"]
    archived_incarnations = sum(
        sum(1 for incarnation in child.get("incarnations", []) if incarnation.get("status") == "archived")
        for child in all_children
    )
    visible = all_children if include_archived else [item for item in all_children if item.get("status") != "archived"]
    visible = visible[: max(0, min(MAX_CHILDREN, int(max_children)))]
    counts: dict[str, int] = {}
    for child in all_children:
        status = str(child.get("status", "planned"))
        counts[status] = counts.get(status, 0) + 1
    active = [item for item in all_children if item.get("status") in ACTIVE_CHILD_STATUSES and item.get("status") != "completed"]
    foreground = next((item for item in active if item.get("status") in {"active", "waiting", "blocked"}), None)
    if foreground is None:
        foreground = next((item for item in active if item.get("status") == "planned"), None)
    activity = [_event_summary(event) for event in events[-max(0, min(MAX_ACTIVITY, int(max_activity))):]]
    projection = {
        "schema": CAMPAIGN_SCHEMA,
        "fleet_schema": FLEET_SCHEMA,
        "campaign_id": state["campaign_id"],
        "objective": state.get("objective", ""),
        "contract": state.get("contract", {}),
        "status": state.get("status", "active"),
        "status_reason": state.get("status_reason", ""),
        "parent_thread_id": state.get("parent_thread_id", ""),
        "runtime_run_id": state.get("runtime_run_id", ""),
        "workspace_root": state.get("workspace_root", ""),
        "tags": list(state.get("tags", [])),
        "created_at": state.get("created_at", ""),
        "updated_at": state.get("updated_at", ""),
        "revision": int(state.get("revision", 0)),
        "head_hash": state.get("head_hash", ""),
        "child_count": len(all_children),
        "visible_child_count": len(visible),
        "archived_child_count": len(archived),
        "counts": dict(sorted(counts.items())),
        "foreground_child_id": foreground.get("id") if foreground else None,
            "children": visible,
        "activity": activity,
        "archive_summary": {
            "archived_count": len(archived),
            "archived_incarnation_count": archived_incarnations,
            "latest_archived_at": max((str(item.get("archived_at", "")) for item in archived), default=""),
            "claim_boundary": "Archived children remain retrievable evidence; their external chat lifecycle is not mutated by this registry.",
        },
        "claim_boundary": "Campaign metadata is event-backed and hash-chained. Runtime task events remain authoritative for execution, leases, and receipts.",
    }
    projection["digest"] = canonical_hash({key: value for key, value in projection.items() if key != "digest"})
    return projection


def _summary(projection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": projection.get("campaign_id", ""),
        "objective": projection.get("objective", ""),
        "status": projection.get("status", "active"),
        "parent_thread_id": projection.get("parent_thread_id", ""),
        "runtime_run_id": projection.get("runtime_run_id", ""),
        "created_at": projection.get("created_at", ""),
        "updated_at": projection.get("updated_at", ""),
        "child_count": projection.get("child_count", 0),
        "archived_child_count": projection.get("archived_child_count", 0),
        "counts": projection.get("counts", {}),
        "tags": projection.get("tags", []),
        "digest": projection.get("digest", ""),
    }


class CampaignFleet:
    """Append-only campaign registry with rebuildable fleet projections."""

    def __init__(self, home: str | os.PathLike[str] | None = None) -> None:
        self.home = Path(home).expanduser().resolve() if home is not None else harness_home().expanduser().resolve()
        self.root = fleet_root(self.home)

    def _store(self, campaign_id: str, *, require_existing: bool = False) -> EventStore:
        directory = _campaign_dir(campaign_id, self.home)
        if require_existing and not (directory / "head.json").is_file():
            raise CampaignNotFound(f"campaign not found: {campaign_id}")
        return EventStore(directory)

    def _read_events(self, campaign_id: str) -> tuple[Event, ...]:
        return self._store(campaign_id, require_existing=True).events()

    def read(self, campaign_id: str, *, include_archived: bool = True, max_children: int = MAX_CHILDREN, max_activity: int = MAX_ACTIVITY) -> dict[str, Any]:
        return _project(
            self._read_events(_identifier(campaign_id, label="campaign_id")),
            include_archived=include_archived,
            max_children=max_children,
            max_activity=max_activity,
        )

    def _append(self, campaign_id: str, event_type: str, payload: Mapping[str, Any], *, idempotency_key: str, expected_revision: int | None) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        store = self._store(campaign_id, require_existing=event_type != "campaign.created")
        with transition_lock(store.run_dir / ".transition.lock"):
            if idempotency_key:
                prior = store.find_idempotency(idempotency_key)
                if prior is not None:
                    if prior.event_type != event_type or canonical_hash(prior.payload) != canonical_hash(dict(payload)):
                        raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
                    return _project(store.events())
            event = store.append(
                event_type,
                campaign_id,
                dict(payload),
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
            )
            projection = _project(store.events())
            atomic_path = store.run_dir / "projection.json"
            atomic_write_json(atomic_path, projection)
            return projection

    def _replay_if_idempotent(
        self,
        campaign_id: str,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        prior = self._store(campaign_id, require_existing=True).find_idempotency(idempotency_key)
        if prior is None:
            return None
        if prior.event_type != event_type or _request_digest(prior.payload) != _request_digest(payload):
            raise IdempotencyConflict(f"idempotency key payload changed: {idempotency_key}")
        return _project(self._read_events(campaign_id))

    def create(
        self,
        objective: str,
        *,
        campaign_id: str | None = None,
        contract: Mapping[str, Any] | None = None,
        parent_thread_id: str = "",
        runtime_run_id: str = "",
        workspace_root: str = "",
        tags: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        objective = _text(objective, label="objective", required=True, max_length=2_000)
        campaign_id = _campaign_id(campaign_id)
        key = _text(idempotency_key or f"campaign-create:{campaign_id}", label="idempotency_key", required=True, max_length=256)
        request_payload = {
            "schema": CAMPAIGN_EVENT_SCHEMA,
            "campaign_id": campaign_id,
            "objective": objective,
            "contract": _mapping(contract, label="contract"),
            "status": "active",
            "parent_thread_id": _text(parent_thread_id, label="parent_thread_id", max_length=256),
            "runtime_run_id": _text(runtime_run_id, label="runtime_run_id", max_length=128),
            "workspace_root": _text(workspace_root, label="workspace_root", max_length=2_000),
            "tags": _tags(tags),
        }
        directory = _campaign_dir(campaign_id, self.home)
        if (directory / "head.json").exists():
            store = self._store(campaign_id, require_existing=True)
            prior = store.find_idempotency(key)
            if prior is not None:
                if prior.event_type != "campaign.created":
                    raise IdempotencyConflict(f"idempotency key already used: {key}")
                prior_request = {field: prior.payload.get(field) for field in request_payload}
                if canonical_hash(prior_request) != canonical_hash(request_payload):
                    raise IdempotencyConflict(f"idempotency key payload changed: {key}")
                return _project(store.events())
            raise CampaignExists(f"campaign already exists: {campaign_id}")
        payload = dict(request_payload)
        payload["created_at"] = _now()
        return self._append(campaign_id, "campaign.created", payload, idempotency_key=key, expected_revision=0)

    def attach_child(
        self,
        campaign_id: str,
        *,
        title: str,
        role: str = "Worker",
        child_id: str | None = None,
        thread_id: str = "",
        task_id: str = "",
        objective: str = "",
        summary: str = "",
        tags: Sequence[str] | None = None,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        projection = self.read(campaign_id)
        child_id = _child_id(child_id)
        key = _text(idempotency_key or f"child-attach:{campaign_id}:{child_id}", label="idempotency_key", required=True, max_length=256)
        child_instance_id = _derived_child_instance_id(campaign_id, child_id, key)
        payload = {
            "schema": CAMPAIGN_EVENT_SCHEMA,
            "id": child_id,
            "child_id": child_id,
            "child_instance_id": child_instance_id,
            "title": _text(title, label="title", required=True, max_length=512),
            "role": _text(role, label="role", required=True, max_length=128),
            "thread_id": _text(thread_id, label="thread_id", max_length=256),
            "task_id": _text(task_id, label="task_id", max_length=128),
            "objective": _text(objective, label="objective", max_length=2_000),
            "summary": _text(summary, label="summary", max_length=2_000),
            "tags": _tags(tags),
            "status": "planned",
            "created_at": _now(),
            "updated_at": _now(),
            "archived_at": None,
            "reopened_at": None,
        }
        replay = self._replay_if_idempotent(campaign_id, "child.attached", key, payload)
        if replay is not None:
            return replay
        if any(str(item.get("id")) == child_id for item in projection.get("children", [])):
            raise CampaignExists(f"child already exists: {child_id}")
        if thread_id and any(str(item.get("thread_id")) == thread_id for item in projection.get("children", []) if item.get("thread_id")):
            raise CampaignExists(f"thread already attached to campaign: {thread_id}")
        if projection["child_count"] >= MAX_CHILDREN:
            raise ValueError(f"campaign child limit exceeded: {MAX_CHILDREN}")
        return self._append(campaign_id, "child.attached", payload, idempotency_key=key, expected_revision=projection["revision"] if expected_revision is None else expected_revision)

    def set_child_status(self, campaign_id: str, child_id: str, status: str, *, reason: str = "", summary: str = "", receipt_id: str = "", expected_revision: int | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        child_id = _identifier(child_id, label="child_id")
        status = _text(status, label="status", required=True, max_length=64).lower()
        if status not in CHILD_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(CHILD_STATUSES))}")
        projection = self.read(campaign_id)
        key = _text(idempotency_key or f"child-status:{campaign_id}:{child_id}:{status}", label="idempotency_key", required=True, max_length=256)
        payload = {
            "schema": CAMPAIGN_EVENT_SCHEMA,
            "child_id": child_id,
            "status": status,
            "reason": _text(reason, label="reason", max_length=2_000),
            "summary": _text(summary, label="summary", max_length=2_000),
            "receipt_id": _text(receipt_id, label="receipt_id", max_length=512),
        }
        replay = self._replay_if_idempotent(campaign_id, "child.status_changed", key, payload)
        if replay is not None:
            return replay
        if status == "archived":
            raise ValueError("use archive_child for archival; reopen creates a fresh child incarnation")
        child = next((item for item in projection.get("children", []) if item.get("id") == child_id), None)
        if child is None:
            raise CampaignNotFound(f"child not found: {child_id}")
        prior_status = str(child.get("status", "planned"))
        if prior_status == "archived" and status != "archived":
            raise ValueError(f"child {child_id} is archived; use reopen_child for a fresh incarnation")
        if status != prior_status and status not in ALLOWED_CHILD_TRANSITIONS.get(prior_status, set()):
            raise ValueError(f"cannot transition child {child_id} from {prior_status} to {status}")
        return self._append(campaign_id, "child.status_changed", payload, idempotency_key=key, expected_revision=projection["revision"] if expected_revision is None else expected_revision)

    def archive_child(self, campaign_id: str, child_id: str, *, reason: str = "completed child archived", expected_revision: int | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        child_id = _identifier(child_id, label="child_id")
        projection = self.read(campaign_id)
        key = _text(idempotency_key or f"child-archive:{campaign_id}:{child_id}", label="idempotency_key", required=True, max_length=256)
        payload = {
            "schema": CAMPAIGN_EVENT_SCHEMA,
            "child_id": child_id,
            "status": "archived",
            "reason": _text(reason, label="reason", max_length=2_000),
        }
        replay = self._replay_if_idempotent(campaign_id, "child.archived", key, payload)
        if replay is not None:
            return replay
        child = next((item for item in projection.get("children", []) if item.get("id") == child_id), None)
        if child is None:
            raise CampaignNotFound(f"child not found: {child_id}")
        if child.get("status") == "archived":
            return projection
        if str(child.get("status", "planned")) not in {"completed", "failed", "canceled", "abandoned"}:
            raise ValueError(f"cannot archive child {child_id} from {child.get('status')}")
        return self._append(campaign_id, "child.archived", payload, idempotency_key=key, expected_revision=projection["revision"] if expected_revision is None else expected_revision)

    def reopen_child(self, campaign_id: str, child_id: str, *, reason: str = "reopened from campaign fleet", thread_id: str = "", task_id: str = "", expected_revision: int | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        child_id = _identifier(child_id, label="child_id")
        projection = self.read(campaign_id)
        child = next((item for item in projection.get("children", []) if item.get("id") == child_id), None)
        if child is None:
            raise CampaignNotFound(f"child not found: {child_id}")
        prior_status = str(child.get("status", "planned"))
        key_seed = str(
            child.get("reopened_from_instance_id")
            if prior_status == "active" and child.get("reopened_from_instance_id")
            else child.get("child_instance_id")
            or child_id
        )
        key = _text(idempotency_key or f"child-reopen:{campaign_id}:{child_id}:{key_seed}", label="idempotency_key", required=True, max_length=256)
        new_instance_id = _derived_child_instance_id(campaign_id, child_id, key)
        reopened_from = key_seed
        payload = {
            "schema": CAMPAIGN_EVENT_SCHEMA,
            "child_id": child_id,
            "child_instance_id": new_instance_id,
            "status": "active",
            "thread_id": _text(thread_id, label="thread_id", max_length=256),
            "task_id": _text(task_id, label="task_id", max_length=128),
            "reopened_from_instance_id": reopened_from,
            "reason": _text(reason, label="reason", max_length=2_000),
        }
        replay = self._replay_if_idempotent(campaign_id, "child.reopened", key, payload)
        if replay is not None:
            return replay
        if prior_status not in {"archived", "abandoned", "completed", "failed", "canceled"}:
            raise ValueError(f"child {child_id} is not reopenable from {child.get('status')}")
        return self._append(campaign_id, "child.reopened", payload, idempotency_key=key, expected_revision=projection["revision"] if expected_revision is not None else projection["revision"])

    def set_campaign_status(self, campaign_id: str, status: str, *, reason: str = "", expected_revision: int | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        campaign_id = _identifier(campaign_id, label="campaign_id")
        status = _text(status, label="status", required=True, max_length=64).lower()
        if status not in CAMPAIGN_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(CAMPAIGN_STATUSES))}")
        projection = self.read(campaign_id)
        key = _text(idempotency_key or f"campaign-status:{campaign_id}:{status}", label="idempotency_key", required=True, max_length=256)
        payload = {"schema": CAMPAIGN_EVENT_SCHEMA, "status": status, "reason": _text(reason, label="reason", max_length=2_000)}
        event_type = "campaign.completed" if status == "completed" else "campaign.archived" if status == "archived" else "campaign.status_changed"
        replay = self._replay_if_idempotent(campaign_id, event_type, key, payload)
        if replay is not None:
            return replay
        if projection["status"] == status:
            return projection
        if status not in CAMPAIGN_TRANSITIONS.get(str(projection["status"]), set()):
            raise ValueError(f"cannot transition campaign {campaign_id} from {projection['status']} to {status}")
        if status in {"completed", "archived"}:
            open_children = [item for item in projection.get("children", []) if item.get("status") in OPEN_CHILD_STATUSES]
            if open_children:
                raise ValueError(f"campaign has open children: {', '.join(str(item.get('id')) for item in open_children[:8])}")
        return self._append(campaign_id, event_type, payload, idempotency_key=key, expected_revision=projection["revision"] if expected_revision is None else expected_revision)

    def list(self, *, query: str = "", status: str = "", include_archived: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        query = _text(query, label="query", max_length=512).lower()
        status = _text(status, label="status", max_length=64).lower()
        if status and status not in CAMPAIGN_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(CAMPAIGN_STATUSES))}")
        limit = max(0, min(MAX_SEARCH_LIMIT, int(limit)))
        if not self.root.exists():
            return []
        matches: list[dict[str, Any]] = []
        for directory in sorted((item for item in self.root.iterdir() if item.is_dir()), key=lambda item: item.name):
            if not (directory / "head.json").is_file():
                continue
            try:
                projection = self.read(directory.name, include_archived=True)
            except (CampaignFleetError, EventIntegrityError, OSError, ValueError):
                continue
            if not include_archived and projection.get("status") == "archived":
                continue
            if status and projection.get("status") != status:
                continue
            haystack = " ".join(
                [
                    str(projection.get("campaign_id", "")),
                    str(projection.get("objective", "")),
                    str(projection.get("parent_thread_id", "")),
                    str(projection.get("runtime_run_id", "")),
                    " ".join(str(tag) for tag in projection.get("tags", [])),
                    " ".join(
                        " ".join(
                            [
                                f"{child.get('id', '')} {child.get('title', '')} {child.get('thread_id', '')} {child.get('role', '')}",
                                " ".join(
                                    f"{incarnation.get('child_instance_id', '')} {incarnation.get('thread_id', '')} {incarnation.get('task_id', '')}"
                                    for incarnation in child.get('incarnations', [])
                                    if isinstance(incarnation, Mapping)
                                ),
                            ]
                        )
                        for child in projection.get("children", [])
                    ),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            matches.append(_summary(projection))
        matches.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("campaign_id", ""))), reverse=True)
        return matches[:limit]

    def search(self, query: str, *, include_archived: bool = True, limit: int = 50) -> list[dict[str, Any]]:
        return self.list(query=query, include_archived=include_archived, limit=limit)


def campaign_markdown(projection: Mapping[str, Any], *, title: str = "SIPS Campaign Fleet") -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- **campaign** `{projection.get('campaign_id', '')}`")
    lines.append(f"- **status** `{projection.get('status', 'unknown')}`")
    lines.append(f"- **objective** `{projection.get('objective', '')}`")
    lines.append(f"- **children** `{projection.get('visible_child_count', 0)}/{projection.get('child_count', 0)}` visible")
    lines.append(f"- **archived** `{projection.get('archived_child_count', 0)}`")
    foreground_id = projection.get("foreground_child_id")
    children = projection.get("children", []) if isinstance(projection.get("children"), list) else []
    foreground = next((item for item in children if isinstance(item, Mapping) and item.get("id") == foreground_id), None)
    lines.extend(["", "## Foreground child", ""])
    lines.append(
        f"- `{foreground.get('id')}` {foreground.get('title', '')} — `{foreground.get('status', 'unknown')}`"
        if foreground
        else "- None — no active child is selected."
    )
    if children:
        lines.extend(["", "## Child fleet", ""])
        for child in children[:12]:
            if not isinstance(child, Mapping):
                continue
            thread = f" · thread `{child.get('thread_id')}`" if child.get("thread_id") else ""
            lines.append(f"- `{child.get('id')}` {child.get('title', '')} — `{child.get('status', 'unknown')}`{thread}")
    activity = projection.get("activity", []) if isinstance(projection.get("activity"), list) else []
    if activity:
        lines.extend(["", "## Recent activity", ""])
        for item in activity[-8:]:
            if isinstance(item, Mapping):
                lines.append(f"- rev `{item.get('revision')}` `{item.get('event_type')}` {item.get('child_id') or ''} {item.get('status') or ''}".rstrip())
    if projection.get("archive_summary"):
        lines.extend(["", f"> {projection['archive_summary'].get('claim_boundary', '')}"])
    return "\n".join(lines)[:12_000]


__all__ = [
    "CAMPAIGN_SCHEMA",
    "FLEET_SCHEMA",
    "CampaignFleet",
    "CampaignFleetError",
    "CampaignNotFound",
    "CampaignExists",
    "campaign_markdown",
    "fleet_root",
]
