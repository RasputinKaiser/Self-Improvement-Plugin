"""Versioned data contracts shared by the graph runtime and adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import secrets
import time
from typing import Any, Mapping
from uuid import UUID

from .canonical import canonical_hash


TASK_SPEC_VERSION = "sips.runtime.task.v1"
SLICE_RESULT_VERSION = "sips.runtime.slice.v1"
EVENT_VERSION = "sips.runtime.event.v1"
STATE_VERSION = "sips.runtime.state.v1"
TASK_ID_MAX_LENGTH = 128
_TASK_ID_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
_TASK_ID_START_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


def validate_safe_identifier(value: Any, *, label: str = "identifier") -> str:
    """Return an exact bounded identifier safe for durable IDs and paths."""

    if (
        not isinstance(value, str)
        or not value
        or len(value) > TASK_ID_MAX_LENGTH
        or value[0] not in _TASK_ID_START_CHARS
        or any(character not in _TASK_ID_ALLOWED_CHARS for character in value)
    ):
        raise ValueError(f"{label} must be a safe single path component")
    return value


def uuid7_str() -> str:
    """Return a standards-shaped, time-ordered UUIDv7 without a new dependency."""
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        (timestamp_ms << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return str(UUID(int=value))


def _tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    return tuple(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise ValueError(f"value is not representable as canonical JSON: {type(value).__name__}")


@dataclass(frozen=True)
class TaskSpec:
    id: str
    objective: str = ""
    description: str = ""
    depends_on: tuple[str, ...] = ()
    acceptance: tuple[Any, ...] = ()
    risk: str = "normal"
    risk_tags: tuple[str, ...] = ()
    priority: float = 0.0
    expected_value: float = 1.0
    estimated_tokens: int | None = None
    resource_estimates: Mapping[str, int] = field(default_factory=dict)
    required_sources: tuple[Any, ...] = ()
    context_query: str | None = None
    merge_contract: Mapping[str, Any] = field(default_factory=lambda: {"strategy": "deterministic"})
    required: bool = True
    retry_limit: int = 1
    insertion_ordinal: int = 0
    read_set: tuple[str, ...] = ()
    write_set: tuple[str, ...] = ()
    cost_cap: int | None = None
    weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = TASK_SPEC_VERSION

    def __post_init__(self) -> None:
        validate_safe_identifier(self.id, label="task id")
        for value in (
            self.acceptance,
            self.resource_estimates,
            self.required_sources,
            self.merge_contract,
            self.metadata,
        ):
            _jsonable(value)
        if self.cost_cap is not None and (
            not isinstance(self.cost_cap, int)
            or isinstance(self.cost_cap, bool)
            or self.cost_cap < 0
        ):
            raise ValueError("cost_cap must be a non-negative integer or None")
        if type(self.required) is not bool:
            raise ValueError("required must be a boolean")
        if self.estimated_tokens is not None and (
            not isinstance(self.estimated_tokens, int)
            or isinstance(self.estimated_tokens, bool)
            or self.estimated_tokens <= 0
        ):
            raise ValueError("estimated_tokens must be a positive integer or None")
        if (
            self.cost_cap is not None
            and self.estimated_tokens is not None
            and self.estimated_tokens > self.cost_cap
        ):
            raise ValueError("estimated_tokens exceeds cost_cap")
        if not isinstance(self.resource_estimates, Mapping):
            raise ValueError("resource estimates must be an object")
        from .budget import RESOURCE_DIMENSIONS

        if any(type(key) is not str for key in self.resource_estimates):
            raise ValueError("resource estimate keys must be strings")
        unknown_resources = sorted(
            set(self.resource_estimates) - set(RESOURCE_DIMENSIONS)
        )
        if unknown_resources:
            raise ValueError(
                "unknown resource dimensions: " + ", ".join(unknown_resources)
            )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in self.resource_estimates.values()
        ):
            raise ValueError("resource estimates must be non-negative integers")
        if "model_tokens" in self.resource_estimates and (
            self.estimated_tokens is None
            or self.resource_estimates["model_tokens"] != self.estimated_tokens
        ):
            raise ValueError(
                "model_tokens resource estimate must match estimated_tokens"
            )
        if (
            self.cost_cap is not None
            and self.resource_estimates.get("model_tokens", 0) > self.cost_cap
        ):
            raise ValueError("model token resource estimate exceeds cost_cap")
        if (
            not isinstance(self.retry_limit, int)
            or isinstance(self.retry_limit, bool)
            or self.retry_limit < 0
        ):
            raise ValueError("retry_limit must be a non-negative integer")
        if (
            not isinstance(self.insertion_ordinal, int)
            or isinstance(self.insertion_ordinal, bool)
            or self.insertion_ordinal < 0
        ):
            raise ValueError("insertion_ordinal must be a non-negative integer")
        for name, value in (
            ("priority", self.priority),
            ("expected_value", self.expected_value),
            ("weight", self.weight),
        ):
            try:
                finite = math.isfinite(float(value))
            except (TypeError, ValueError):
                finite = False
            if not finite:
                raise ValueError(f"{name} must be finite")
        if self.weight < 0:
            raise ValueError("task weight must be non-negative")

    @property
    def task_id(self) -> str:
        return self.id

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskSpec":
        raw = dict(value)
        version = raw.pop("schema_version", TASK_SPEC_VERSION)
        if version not in (TASK_SPEC_VERSION, 1, "1"):
            raise ValueError(f"unsupported TaskSpec schema version: {version}")
        depends = raw.pop("depends_on", raw.pop("dependencies", ()))
        task_id = raw.pop("id", raw.pop("task_id", None))
        required = raw.pop("required", True)
        return cls(
            id=task_id,
            objective=str(raw.pop("objective", "")),
            description=str(raw.pop("description", "")),
            depends_on=tuple(str(x) for x in _tuple(depends)),
            acceptance=_tuple(raw.pop("acceptance", ())),
            risk=str(raw.pop("risk", "normal")),
            risk_tags=tuple(str(x) for x in _tuple(raw.pop("risk_tags", ()))),
            priority=float(raw.pop("priority", 0.0)),
            expected_value=float(raw.pop("expected_value", 1.0)),
            estimated_tokens=raw.pop("estimated_tokens", None),
            resource_estimates=raw.pop("resource_estimates", raw.pop("estimated_resources", {})),
            required_sources=_tuple(raw.pop("required_sources", ())),
            context_query=raw.pop("context_query", None),
            merge_contract=raw.pop("merge_contract", {"strategy": "deterministic"}),
            required=required,
            retry_limit=raw.pop("retry_limit", 1),
            insertion_ordinal=raw.pop("insertion_ordinal", 0),
            read_set=tuple(str(x) for x in _tuple(raw.pop("read_set", ()))),
            write_set=tuple(str(x) for x in _tuple(raw.pop("write_set", ()))),
            cost_cap=raw.pop("cost_cap", None),
            weight=float(raw.pop("weight", 1.0)),
            metadata=raw.pop("metadata", raw),
            schema_version=TASK_SPEC_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "objective": self.objective,
            "description": self.description,
            "depends_on": list(self.depends_on),
            "acceptance": _jsonable(list(self.acceptance)),
            "risk": self.risk,
            "risk_tags": list(self.risk_tags),
            "priority": self.priority,
            "expected_value": self.expected_value,
            "estimated_tokens": self.estimated_tokens,
            "resource_estimates": _jsonable(dict(self.resource_estimates)),
            "required_sources": _jsonable(list(self.required_sources)),
            "context_query": self.context_query,
            "merge_contract": _jsonable(dict(self.merge_contract)),
            "required": self.required,
            "retry_limit": self.retry_limit,
            "insertion_ordinal": self.insertion_ordinal,
            "read_set": list(self.read_set),
            "write_set": list(self.write_set),
            "cost_cap": self.cost_cap,
            "weight": self.weight,
            "metadata": _jsonable(dict(self.metadata)),
        }

    def content_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class SliceResult:
    slice_id: str
    status: str
    run_id: str = ""
    attempt_id: str = ""
    lease_id: str = ""
    lease: Mapping[str, Any] = field(default_factory=dict)
    owner: str = ""
    fencing_token: int | None = None
    plan_digest: str = ""
    context_digest: str = ""
    summary: str = ""
    claims: tuple[Any, ...] = ()
    artifacts: tuple[Any, ...] = ()
    evidence: tuple[Any, ...] = ()
    changed_paths: tuple[str, ...] = ()
    blockers: tuple[Any, ...] = ()
    usage: Mapping[str, Any] = field(default_factory=dict)
    gates: Mapping[str, Any] = field(default_factory=dict)
    reviewer: Mapping[str, Any] = field(default_factory=dict)
    acceptance_results: tuple[Any, ...] = ()
    receipt_ref: str | None = None
    blocker: Any = None
    lesson_candidate: Any = None
    task_id: str | None = None
    cost_tokens: int | None = None
    result_hash: str = ""
    schema_version: str = SLICE_RESULT_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.lease,
            self.claims,
            self.artifacts,
            self.evidence,
            self.blockers,
            self.usage,
            self.gates,
            self.reviewer,
            self.acceptance_results,
            self.blocker,
            self.lesson_candidate,
        ):
            _jsonable(value)

    @property
    def id(self) -> str:
        return self.slice_id

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SliceResult":
        raw = dict(value)
        version = raw.pop("schema_version", SLICE_RESULT_VERSION)
        if version not in (SLICE_RESULT_VERSION, 1, "1"):
            raise ValueError(f"unsupported SliceResult schema version: {version}")
        return cls(
            slice_id=str(raw.pop("slice_id", raw.pop("id", ""))),
            status=str(raw.pop("status", "blocked")),
            run_id=str(raw.pop("run_id", "")),
            attempt_id=str(raw.pop("attempt_id", "")),
            lease_id=str(raw.pop("lease_id", "")),
            lease=raw.pop("lease", {}),
            owner=str(raw.pop("owner", "")),
            fencing_token=raw.pop("fencing_token", None),
            plan_digest=str(raw.pop("plan_digest", "")),
            context_digest=str(raw.pop("context_digest", "")),
            summary=str(raw.pop("summary", "")),
            claims=_tuple(raw.pop("claims", ())),
            artifacts=_tuple(raw.pop("artifacts", ())),
            evidence=_tuple(raw.pop("evidence", ())),
            changed_paths=tuple(str(x) for x in _tuple(raw.pop("changed_paths", ()))),
            blockers=_tuple(raw.pop("blockers", ())),
            usage=raw.pop("usage", {}),
            gates=raw.pop("gates", {}),
            reviewer=raw.pop("reviewer", {}),
            acceptance_results=_tuple(raw.pop("acceptance_results", ())),
            receipt_ref=raw.pop("receipt_ref", None),
            blocker=raw.pop("blocker", None),
            lesson_candidate=raw.pop("lesson_candidate", None),
            task_id=raw.pop("task_id", None),
            cost_tokens=raw.pop("cost_tokens", raw.pop("tokens", None)),
            result_hash=str(raw.pop("result_hash", "")),
            schema_version=SLICE_RESULT_VERSION,
        )

    def _base_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "slice_id": self.slice_id,
            "task_id": self.task_id,
            "status": self.status,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "lease_id": self.lease_id,
            "lease": _jsonable(dict(self.lease)),
            "owner": self.owner,
            "fencing_token": self.fencing_token,
            "plan_digest": self.plan_digest,
            "context_digest": self.context_digest,
            "summary": self.summary,
            "claims": _jsonable(list(self.claims)),
            "artifacts": _jsonable(list(self.artifacts)),
            "evidence": _jsonable(list(self.evidence)),
            "changed_paths": list(self.changed_paths),
            "blockers": _jsonable(list(self.blockers)),
            "usage": _jsonable(dict(self.usage)),
            "gates": _jsonable(dict(self.gates)),
            "reviewer": _jsonable(dict(self.reviewer)),
            "acceptance_results": _jsonable(list(self.acceptance_results)),
            "receipt_ref": self.receipt_ref,
            "blocker": _jsonable(self.blocker),
            "lesson_candidate": _jsonable(self.lesson_candidate),
            "cost_tokens": self.cost_tokens,
        }

    def to_dict(self) -> dict[str, Any]:
        value = self._base_dict()
        value["result_hash"] = self.result_hash or canonical_hash(value)
        return value

    def content_hash(self) -> str:
        return canonical_hash(self._base_dict())


@dataclass(frozen=True)
class Event:
    event_type: str
    run_id: str
    revision: int
    payload: Mapping[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    event_hash: str = ""
    event_id: str = field(default_factory=uuid7_str)
    idempotency_key: str | None = None
    actor: str = "runtime"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = 1

    @property
    def hash(self) -> str:
        return self.event_hash

    @property
    def schema(self) -> str:
        return EVENT_VERSION

    @property
    def seq(self) -> int:
        return self.revision

    @property
    def prev_digest(self) -> str:
        return self.prev_hash

    @property
    def event_digest(self) -> str:
        return self.event_hash

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "schema": EVENT_VERSION,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "revision": self.revision,
            "timestamp": self.timestamp,
            "idempotency_key": self.idempotency_key,
            "actor": self.actor,
            "prev_hash": self.prev_hash,
            "prev_digest": self.prev_hash,
            "seq": self.revision,
            "payload_digest": canonical_hash(self.payload),
            "payload": _jsonable(dict(self.payload)),
        }

    def seal(self) -> "Event":
        return Event(**{**self.__dict__, "event_hash": canonical_hash(self.unsigned_dict())})

    def to_dict(self) -> dict[str, Any]:
        value = self.unsigned_dict()
        value["event_hash"] = self.event_hash or canonical_hash(value)
        value["event_digest"] = value["event_hash"]
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Event":
        raw = dict(value)
        required = {
            "schema",
            "schema_version",
            "event_id",
            "event_type",
            "run_id",
            "revision",
            "seq",
            "timestamp",
            "idempotency_key",
            "actor",
            "prev_hash",
            "prev_digest",
            "payload_digest",
            "payload",
            "event_hash",
            "event_digest",
        }
        missing = sorted(required - set(raw))
        extra = sorted(set(raw) - required)
        if missing:
            raise ValueError("event missing required fields: " + ", ".join(missing))
        if extra:
            raise ValueError("event has unexpected fields: " + ", ".join(extra))
        if raw["schema"] != EVENT_VERSION or type(raw["schema"]) is not str:
            raise ValueError("event schema is invalid")
        if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
            raise ValueError("event schema version must be exact integer 1")
        if any(type(raw[field]) is not int for field in ("revision", "seq")):
            raise ValueError("event revision and seq must be exact integers")
        if raw["revision"] < 1 or raw["seq"] != raw["revision"]:
            raise ValueError("event revision and seq are invalid")
        for field in (
            "event_id",
            "event_type",
            "run_id",
            "timestamp",
            "actor",
            "prev_hash",
            "prev_digest",
            "payload_digest",
            "event_hash",
            "event_digest",
        ):
            if type(raw[field]) is not str:
                raise ValueError(f"event {field} must be a string")
        if not raw["event_type"] or not raw["timestamp"] or not raw["actor"]:
            raise ValueError("event type, timestamp, and actor are required")
        try:
            event_uuid = UUID(raw["event_id"])
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("event_id must be a canonical UUIDv7") from exc
        if event_uuid.version != 7 or str(event_uuid) != raw["event_id"]:
            raise ValueError("event_id must be a canonical UUIDv7")
        validate_safe_identifier(raw["run_id"], label="run_id")
        if raw["idempotency_key"] is not None and type(raw["idempotency_key"]) is not str:
            raise ValueError("event idempotency_key must be a string or null")
        if type(raw["payload"]) is not dict:
            raise ValueError("event payload must be an object")
        if raw["prev_digest"] != raw["prev_hash"]:
            raise ValueError("event previous-digest alias disagrees")
        if raw["event_digest"] != raw["event_hash"]:
            raise ValueError("event digest alias disagrees")
        if raw["payload_digest"] != canonical_hash(raw["payload"]):
            raise ValueError("event payload digest is invalid")
        hex_chars = frozenset("0123456789abcdef")
        for field in ("payload_digest", "event_hash", "event_digest"):
            if len(raw[field]) != 64 or any(char not in hex_chars for char in raw[field]):
                raise ValueError(f"event {field} must be a lower-case SHA-256 digest")
        for field in ("prev_hash", "prev_digest"):
            if raw[field] and (
                len(raw[field]) != 64
                or any(char not in hex_chars for char in raw[field])
            ):
                raise ValueError(f"event {field} must be empty or a lower-case SHA-256 digest")
        return cls(
            event_type=raw["event_type"],
            run_id=raw["run_id"],
            revision=raw["revision"],
            payload=raw["payload"],
            prev_hash=raw["prev_hash"],
            event_hash=raw["event_hash"],
            event_id=raw["event_id"],
            idempotency_key=raw["idempotency_key"],
            actor=raw["actor"],
            timestamp=raw["timestamp"],
            schema_version=1,
        )

    def verify(self, expected_prev_hash: str | None = None) -> bool:
        if expected_prev_hash is not None and self.prev_hash != expected_prev_hash:
            return False
        return bool(self.event_hash) and self.event_hash == canonical_hash(self.unsigned_dict())
