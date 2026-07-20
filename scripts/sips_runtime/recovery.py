"""Fail-closed audit and recovery for damaged runtime event streams.

Recovery treats a run's ``events.jsonl`` and ``head.json`` as evidence.  The
source directory is never opened through :class:`EventStore` (its constructor
may create a missing head), and this module never truncates or rewrites the
source files.  A recovered run is a fresh event stream containing the verified
creation plan followed by one provenance event linking it to the source.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_hash
from .budget import BudgetLedger, TRANCHE_PERCENTAGES
from .contracts import (
    EVENT_VERSION,
    Event,
    TaskSpec,
    uuid7_str,
    validate_safe_identifier,
)
from .controller import RuntimeController
from .dag import compile_dag
from .events import (
    EventIntegrityError,
    EventStore,
    IdempotencyConflict,
    transition_lock,
)


RECOVERY_EVENT_TYPE = "run.recovered"


class RecoveryError(RuntimeError):
    """Raised when a source cannot be recovered without guessing."""


@dataclass(frozen=True)
class RecoveryAudit:
    """Read-only evidence collected while auditing one run.

    ``verified_events`` is the contiguous prefix whose event hashes, sequence
    numbers, run identity, and previous hashes were verified.  The raw bytes
    are retained so callers can prove that an audit did not repair the source.
    """

    run_id: str
    run_dir: Path
    events_path: Path
    head_path: Path
    verified_events: tuple[Event, ...]
    verified_prefix_revision: int
    verified_prefix_hash: str
    valid: bool
    reason: str
    reason_detail: str = ""
    failure_line: int | None = None
    creation_event: Event | None = None
    raw_events: bytes = b""
    raw_head: bytes = b""
    head: Mapping[str, Any] | None = None

    @property
    def writable(self) -> bool:
        """Whether the source is a complete, self-consistent event stream."""

        return self.valid

    @property
    def can_write(self) -> bool:
        return self.writable

    @property
    def write_allowed(self) -> bool:
        return self.writable

    @property
    def events(self) -> tuple[Event, ...]:
        """Compatibility alias for the verified prefix."""

        return self.verified_events

    @property
    def prefix(self) -> tuple[Event, ...]:
        return self.verified_events

    @property
    def verified_prefix(self) -> tuple[Event, ...]:
        return self.verified_events

    @property
    def is_valid(self) -> bool:
        return self.valid

    @property
    def is_writable(self) -> bool:
        return self.writable

    @property
    def reason_code(self) -> str:
        return self.reason

    @property
    def head_revision(self) -> int | None:
        return int(self.head["revision"]) if self.head is not None else None

    @property
    def head_hash(self) -> str | None:
        return str(self.head["hash"]) if self.head is not None else None

    @property
    def last_valid_sequence(self) -> int:
        return self.verified_prefix_revision

    @property
    def last_valid_digest(self) -> str:
        return self.verified_prefix_hash

    @property
    def source_path(self) -> str:
        return str(self.events_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "events_path": str(self.events_path),
            "head_path": str(self.head_path),
            "verified_prefix_revision": self.verified_prefix_revision,
            "verified_prefix_hash": self.verified_prefix_hash,
            "last_valid_sequence": self.last_valid_sequence,
            "last_valid_digest": self.last_valid_digest,
            "valid": self.valid,
            "writable": self.writable,
            "reason": self.reason,
            "reason_detail": self.reason_detail,
            "failure_line": self.failure_line,
            "creation_event_digest": self.creation_event.event_hash if self.creation_event else "",
            "head": dict(self.head or {}),
            "verified_events": [event.to_dict() for event in self.verified_events],
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


@dataclass(frozen=True)
class RecoveryResult:
    """Result of forking a new run from an audited source."""

    audit: RecoveryAudit
    source_run_id: str
    run_id: str
    run_dir: Path
    provenance_event: Event
    state: Mapping[str, Any]

    @property
    def forked_run_id(self) -> str:
        return self.run_id

    @property
    def new_run_id(self) -> str:
        return self.run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_run_id": self.source_run_id,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "provenance_event": self.provenance_event.to_dict(),
            "audit": self.audit.to_dict(),
            "state": dict(self.state),
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


def _validate_budget_configuration(payload: Mapping[str, Any]) -> None:
    """Reject budget profiles that recovery cannot reproduce faithfully.

    RuntimeController currently owns one tranche profile (30/35/35).  A
    source event advertising another profile must not be silently rewritten to
    that default during recovery.  Resource limits and the released tranche
    count are retained by copying the complete creation payload below.
    """

    if "budgets" not in payload:
        return
    raw = payload.get("budgets")
    if not isinstance(raw, Mapping):
        raise RecoveryError("verified run.created event has invalid budget configuration")
    budgets = dict(raw)
    try:
        soft_limit = budgets.get("soft_limit", 60_000)
        hard_limit = budgets.get("hard_limit", 120_000)
        resource_limits = budgets.get("resource_limits", {})
        released_tranches = budgets.get("released_tranches", 1)
        ledger = BudgetLedger(
            soft_limit,
            hard_limit,
            resource_limits,
            released_tranches=released_tranches,
        )
    except (TypeError, ValueError) as exc:
        raise RecoveryError(f"verified budget configuration is invalid: {exc}") from exc

    supplied_percentages = budgets.get("tranche_percentages")
    if supplied_percentages is not None:
        try:
            percentages = list(supplied_percentages)
        except (TypeError, ValueError) as exc:
            raise RecoveryError("verified tranche percentages are invalid") from exc
        if percentages != list(TRANCHE_PERCENTAGES):
            raise RecoveryError("recovery does not support nonstandard tranche percentages")
    supplied_limits = budgets.get("tranche_limits")
    if supplied_limits is not None:
        try:
            tranche_limits = list(supplied_limits)
        except (TypeError, ValueError) as exc:
            raise RecoveryError("verified tranche limits are invalid") from exc
        if tranche_limits != list(ledger.tranche_limits):
            raise RecoveryError("recovery does not support nonstandard tranche limits")
    if "released_token_limit" in budgets:
        released_token_limit = budgets["released_token_limit"]
        if not isinstance(released_token_limit, int) or isinstance(
            released_token_limit, bool
        ):
            raise RecoveryError("verified released_token_limit is invalid")
        if released_token_limit != ledger.released_token_limit:
            raise RecoveryError("verified budget released_token_limit does not match tranche configuration")


def _source_dir(
    source: str | os.PathLike[str] | RuntimeController,
    run_id: str | None,
) -> tuple[Path, str]:
    if isinstance(source, RuntimeController):
        if not run_id:
            raise ValueError("run_id is required when auditing a RuntimeController")
        # _run_dir performs the controller's path-component validation, while
        # avoiding EventStore's constructor and its missing-head write.
        return source._run_dir(run_id), run_id  # type: ignore[attr-defined]
    path = Path(source).expanduser().resolve()
    resolved_id = run_id or path.name
    if not resolved_id:
        raise ValueError("run_id is required when source has no run directory name")
    resolved_id = validate_safe_identifier(resolved_id, label="run_id")
    # Accept either a run directory (``.../runs/<id>``) or a runs root plus an
    # explicit ID (``.../runs``, ``id``).  The latter is useful to callers that
    # only have a root path and keeps the audit read-only in both forms.
    child = path / resolved_id
    if run_id and child.is_dir() and not (path / "events.jsonl").exists():
        path = child
    return path, resolved_id


def _head_value(raw: bytes, path: Path) -> tuple[dict[str, Any] | None, str, str]:
    if not raw:
        return None, "missing_head", f"revision head is missing: {path}"
    try:
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("revision head must be an object")
        required = {
            "schema",
            "schema_version",
            "revision",
            "seq",
            "hash",
            "event_digest",
        }
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        if missing:
            raise ValueError(
                "revision head missing required fields: " + ", ".join(missing)
            )
        if extra:
            raise ValueError(
                "revision head has unexpected fields: " + ", ".join(extra)
            )
        if value["schema"] != "sips.runtime.head.v1":
            raise ValueError("unsupported revision head schema")
        if any(
            type(value[field]) is not int
            for field in ("schema_version", "revision", "seq")
        ):
            raise ValueError("revision head integer fields must be exact integers")
        if value["schema_version"] != 1:
            raise ValueError("unsupported revision head schema version")
        if any(
            type(value[field]) is not str
            for field in ("schema", "hash", "event_digest")
        ):
            raise ValueError("revision head schema and digests must be strings")
        if value["revision"] != value["seq"]:
            raise ValueError("head seq alias disagrees with revision")
        if value["hash"] != value["event_digest"]:
            raise ValueError("head digest alias disagrees with hash")
        revision = value["revision"]
        digest = value["hash"]
        if revision < 0:
            raise ValueError("revision must be non-negative")
        if revision == 0 and digest:
            raise ValueError("revision zero head must have an empty digest")
        if revision > 0 and (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("revision head digest must be lower-case SHA-256")
        return {"revision": revision, "hash": digest}, "", ""
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, "invalid_head", f"cannot parse revision head {path}: {exc}"


def audit_run(
    source: str | os.PathLike[str] | RuntimeController,
    run_id: str | None = None,
) -> RecoveryAudit:
    """Audit a run without mutating it.

    The audit stops at the first malformed, forged, out-of-order, or
    wrong-run event and reports the verified prefix.  A valid event stream with
    a missing or mismatched head is also non-writable.  All source bytes are
    read once and retained in the returned result for byte-preservation tests.
    """

    run_dir, resolved_id = _source_dir(source, run_id)
    events_path = run_dir / "events.jsonl"
    head_path = run_dir / "head.json"
    try:
        raw_events = events_path.read_bytes() if events_path.exists() else b""
    except OSError as exc:
        raw_events = b""
        events_error = f"cannot read event stream {events_path}: {exc}"
    else:
        events_error = ""
    try:
        raw_head = head_path.read_bytes() if head_path.exists() else b""
    except OSError as exc:
        raw_head = b""
        head_error = f"cannot read revision head {head_path}: {exc}"
    else:
        head_error = ""

    verified: list[Event] = []
    reason = ""
    detail = ""
    failure_line: int | None = None
    if events_error:
        reason, detail = "events_unreadable", events_error
    else:
        for line_number, line in enumerate(raw_events.splitlines(), 1):
            if not line.strip():
                continue
            try:
                decoded = json.loads(line.decode("utf-8"))
                if not isinstance(decoded, Mapping):
                    raise ValueError("event must be an object")
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
                missing = sorted(required - set(decoded))
                if missing:
                    raise EventIntegrityError(
                        "event missing required fields: " + ", ".join(missing)
                    )
                if any(
                    type(decoded[field]) is not int
                    for field in ("schema_version", "revision", "seq")
                ):
                    raise EventIntegrityError(
                        "event integer fields must be exact integers"
                    )
                if decoded["schema"] != EVENT_VERSION or decoded["schema_version"] != 1:
                    raise EventIntegrityError("event schema or version is invalid")
                event = Event.from_dict(decoded)
                if event.event_type == "run.created" and verified:
                    raise EventIntegrityError(
                        "run.created must appear exactly once at revision 1"
                    )
                # Event.from_dict enforces the complete canonical wire shape.
                # Recovery repeats the digest relationships below so failures
                # remain explicit in the audit receipt.
                if (
                    "payload_digest" in decoded
                    and str(decoded["payload_digest"]) != canonical_hash(event.payload)
                ):
                    raise EventIntegrityError("event payload digest is invalid")
                if "event_digest" in decoded and str(decoded["event_digest"]) != event.event_hash:
                    raise EventIntegrityError("event digest alias disagrees with event hash")
                if "seq" in decoded and int(decoded["seq"]) != event.revision:
                    raise EventIntegrityError("event seq alias disagrees with revision")
                if "prev_digest" in decoded and str(decoded["prev_digest"]) != event.prev_hash:
                    raise EventIntegrityError(
                        "event previous-digest alias disagrees with prev_hash"
                    )
                expected_revision = len(verified) + 1
                expected_prev = verified[-1].event_hash if verified else ""
                if event.run_id != resolved_id:
                    raise EventIntegrityError(
                        f"event run_id {event.run_id!r} does not match {resolved_id!r}"
                    )
                if event.revision != expected_revision:
                    raise EventIntegrityError(
                        f"event revision {event.revision} does not follow {expected_revision - 1}"
                    )
                if not event.verify(expected_prev):
                    raise EventIntegrityError("event hash or previous hash is invalid")
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
                KeyError,
                EventIntegrityError,
            ) as exc:
                failure_line = line_number
                reason = (
                    "truncated_event"
                    if line_number == len(raw_events.splitlines())
                    else "corrupt_event"
                )
                detail = f"invalid event at line {line_number}: {exc}"
                break
            verified.append(event)

    parsed_head, head_reason, head_detail = _head_value(raw_head, head_path)
    if head_error:
        head_reason, head_detail = "head_unreadable", head_error
    if not reason and head_reason:
        reason, detail = head_reason, head_detail
    elif reason and head_reason:
        detail = f"{detail}; {head_detail}"

    expected_revision = len(verified)
    expected_hash = verified[-1].event_hash if verified else ""
    if not reason and parsed_head is not None:
        if parsed_head["revision"] != expected_revision or parsed_head["hash"] != expected_hash:
            reason = "head_mismatch"
            detail = (
                f"head revision/hash ({parsed_head['revision']}, {parsed_head['hash']!r}) "
                f"does not match verified prefix ({expected_revision}, {expected_hash!r})"
            )
    # ``run.created`` is the root of a run's state machine.  A later creation
    # event may still be perfectly hash-chained, but it is not a recoverable
    # creation plan: accepting it would silently ignore the earlier event(s)
    # and fork a run from an ambiguous state.
    first_event = verified[0] if verified else None
    creation = first_event if first_event and first_event.event_type == "run.created" else None
    if (
        not reason
        and first_event is not None
        and creation is None
        and any(event.event_type == "run.created" for event in verified[1:])
    ):
        reason = "creation_not_first"
        detail = "run.created must be the first event at revision 1"
    if not reason and not verified:
        # A zero-event directory is not a runnable run.  Keep an explicitly
        # missing event stream distinguishable from an empty, headed stream.
        reason = "missing_events" if not raw_events else "empty_events"
        detail = f"no run.created event found in {events_path}"
    if not reason and creation is None:
        reason = "missing_creation"
        detail = "verified event stream has no run.created event"

    return RecoveryAudit(
        run_id=resolved_id,
        run_dir=run_dir,
        events_path=events_path,
        head_path=head_path,
        verified_events=tuple(verified),
        verified_prefix_revision=expected_revision,
        verified_prefix_hash=expected_hash,
        valid=not reason,
        reason=reason or "ok",
        reason_detail=detail,
        failure_line=failure_line,
        creation_event=creation,
        raw_events=raw_events,
        raw_head=raw_head,
        head=parsed_head,
    )


def _controller_for(
    source: str | os.PathLike[str] | RuntimeController,
    run_id: str,
    source_dir: Path,
) -> RuntimeController:
    if isinstance(source, RuntimeController):
        return source
    path = Path(source).expanduser().resolve()
    # RuntimeController normally derives ``root/runtime/v1/runs``.  Recovery
    # also accepts a direct run directory/runs root, so bind its root to the
    # already-audited parent rather than accidentally creating a sibling tree.
    if source_dir == path / run_id:
        root = path
    elif source_dir == path:
        root = path.parent
    else:
        root = source_dir.parent
    controller = RuntimeController(root.parent if root.name == "runs" else root)
    controller.root = root
    root.mkdir(parents=True, exist_ok=True)
    return controller


def recover_run(
    source: str | os.PathLike[str] | RuntimeController,
    run_id: str | None = None,
    *,
    new_run_id: str | None = None,
    recovery_id: str | None = None,
) -> RecoveryResult:
    """Fork a fresh linked run from the source's verified creation event.

    Recovery refuses an unidentifiable source, a missing creation plan, or a
    destination with mismatched history.  An exact creation-only or completed
    destination is resumed idempotently.  It never appends to the source
    stream, even when the source audit is valid.
    """

    audit = audit_run(source, run_id)
    creation = audit.creation_event
    if creation is None:
        raise RecoveryError(f"cannot recover {audit.run_id}: {audit.reason}: {audit.reason_detail}")
    payload = dict(creation.payload)
    _validate_budget_configuration(payload)
    tasks = payload.get("tasks", payload.get("plan"))
    if isinstance(tasks, Mapping):
        tasks = list(tasks.values())
    if not isinstance(tasks, list):
        raise RecoveryError("verified run.created event has no task plan")
    try:
        specs = [TaskSpec.from_dict(item) for item in tasks]
        compile_dag(specs)
    except (TypeError, ValueError, KeyError) as exc:
        raise RecoveryError(f"verified creation plan is invalid: {exc}") from exc

    controller = _controller_for(source, audit.run_id, audit.run_dir)
    destination_id = validate_safe_identifier(
        uuid7_str() if new_run_id is None else new_run_id,
        label="new_run_id",
    )
    default_recovery_id = (
        uuid7_str()
        if new_run_id is None
        else "recovery-"
        + canonical_hash(
            {
                "source_run_id": audit.run_id,
                "destination_run_id": destination_id,
                "source_creation_event_digest": creation.event_hash,
            }
        )[:24]
    )
    resolved_recovery_id = validate_safe_identifier(
        default_recovery_id if recovery_id is None else recovery_id,
        label="recovery_id",
    )
    destination_dir = controller._run_dir(destination_id)  # type: ignore[attr-defined]
    # Preserve the source creation payload instead of reconstructing a subset
    # of it through ``RuntimeController.create``.  In particular, the
    # controller's request surface historically defaulted resource limits and
    # tranche fields, which made a recovered run differ from its source even
    # when the source event was valid.  The plan was already validated above;
    # normalize only the task representation so replay sees the same compiled
    # task specs while retaining every other creation field byte-for-byte in
    # its decoded form (including the complete budget configuration).
    creation_payload = dict(payload)
    creation_payload["tasks"] = [spec.to_dict() for spec in specs]
    provenance_payload = {
        "source_run_id": audit.run_id,
        "source_run_dir": str(audit.run_dir),
        "source_events_path": str(audit.events_path),
        "source_head_path": str(audit.head_path),
        "source_path": str(audit.events_path),
        "source_valid": audit.valid,
        "source_reason": audit.reason,
        "source_reason_detail": audit.reason_detail,
        "verified_prefix_revision": audit.verified_prefix_revision,
        "verified_prefix_hash": audit.verified_prefix_hash,
        "source_last_valid_sequence": audit.last_valid_sequence,
        "source_last_valid_digest": audit.last_valid_digest,
        "recovery_reason": audit.reason,
        "source_creation_event_digest": creation.event_hash,
        "source_event_count": len(audit.verified_events),
        "recovery_id": resolved_recovery_id,
    }
    create_key = f"recovery-create:{audit.run_id}:{destination_id}"
    provenance_key = f"recovery-provenance:{audit.run_id}:{destination_id}"
    try:
        with transition_lock(destination_dir / ".transition.lock"):
            destination_store = EventStore(destination_dir)
            allowed_entries = {
                ".events.lock",
                ".transition.lock",
                "events.jsonl",
                "head.json",
                "receipts",
                "slices",
                "snapshot.json",
            }
            unexpected_entries = sorted(
                item.name
                for item in destination_dir.iterdir()
                if item.name not in allowed_entries
            )
            if unexpected_entries:
                raise RecoveryError(
                    "recovery destination has unexpected material: "
                    + ", ".join(unexpected_entries)
                )
            existing = destination_store.events()
            if len(existing) > 2:
                raise RecoveryError(
                    f"recovery destination has unexpected extra events: {destination_id}"
                )
            if existing:
                first = existing[0]
                if (
                    first.event_type != "run.created"
                    or first.run_id != destination_id
                    or first.idempotency_key != create_key
                    or canonical_hash(first.payload)
                    != canonical_hash(creation_payload)
                ):
                    raise RecoveryError(
                        f"recovery destination creation does not match: {destination_id}"
                    )
            if len(existing) == 2:
                second = existing[1]
                if (
                    second.event_type != RECOVERY_EVENT_TYPE
                    or second.run_id != destination_id
                    or second.idempotency_key != provenance_key
                    or canonical_hash(second.payload)
                    != canonical_hash(provenance_payload)
                ):
                    raise RecoveryError(
                        f"recovery destination provenance does not match: {destination_id}"
                    )
            destination_store.append(
                "run.created",
                destination_id,
                creation_payload,
                idempotency_key=create_key,
                expected_revision=0,
            )
            provenance = destination_store.append(
                RECOVERY_EVENT_TYPE,
                destination_id,
                provenance_payload,
                idempotency_key=provenance_key,
                expected_revision=1,
            )
    except RecoveryError:
        raise
    except (EventIntegrityError, IdempotencyConflict, OSError, ValueError) as exc:
        raise RecoveryError(
            f"recovery destination is not resumable: {destination_id}: {exc}"
        ) from exc
    (destination_dir / "receipts").mkdir(parents=True, exist_ok=True)
    (destination_dir / "slices").mkdir(parents=True, exist_ok=True)
    state = controller.read_status(destination_id)
    return RecoveryResult(
        audit=audit,
        source_run_id=audit.run_id,
        run_id=destination_id,
        run_dir=destination_dir,
        provenance_event=provenance,
        state=state,
    )


# Explicit aliases make the operation discoverable without multiplying
# implementations or weakening the single fail-closed code path.
fork_recovery = recover_run
recover = recover_run
audit = audit_run
recover_from_corruption = recover_run
fork_recovered_run = recover_run
fork_run = recover_run
RunAudit = RecoveryAudit
RecoveryReport = RecoveryResult


__all__ = [
    "RECOVERY_EVENT_TYPE",
    "RecoveryAudit",
    "RecoveryError",
    "RecoveryResult",
    "RunAudit",
    "RecoveryReport",
    "audit_run",
    "audit",
    "recover_run",
    "fork_recovery",
    "recover",
    "recover_from_corruption",
    "fork_recovered_run",
    "fork_run",
]
