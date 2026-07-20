"""Durable append-only, hash-chained event storage."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .canonical import canonical_bytes, canonical_json, canonical_hash
from .contracts import Event, EVENT_VERSION, validate_safe_identifier

try:  # pragma: no cover - fcntl is present on supported Unix hosts
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class EventStoreError(RuntimeError):
    pass


class RevisionConflict(EventStoreError):
    pass


class EventIntegrityError(EventStoreError):
    pass


class IdempotencyConflict(EventStoreError):
    pass


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# Public alias for controller transactions that must hold one per-run mutex
# across read/validate/append, not merely around the final append call.
transition_lock = _file_lock


class EventStore:
    """One run's event stream and durable revision head."""

    def __init__(self, run_dir: str | os.PathLike[str]) -> None:
        self.run_dir = Path(run_dir).expanduser().resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.head_path = self.run_dir / "head.json"
        self.lock_path = self.run_dir / ".events.lock"
        if not self.head_path.exists():
            # A constructor may race an append performed by an already-open
            # store.  The quick check above is only an optimization: the
            # authoritative check and rev0 write must share the event lock so
            # a late constructor cannot overwrite a head written by append.
            with _file_lock(self.lock_path):
                if self.head_path.exists():
                    return
                if self.events_path.exists():
                    try:
                        existing_events = self.events_path.read_bytes()
                    except OSError as exc:
                        raise EventIntegrityError(
                            f"cannot inspect event stream before head initialization: {exc}"
                        ) from exc
                    if existing_events.strip():
                        raise EventIntegrityError(
                            "event stream exists but revision head is missing"
                        )
                atomic_write_json(
                    self.head_path,
                    {
                        "schema": "sips.runtime.head.v1",
                        "schema_version": 1,
                        "seq": 0,
                        "event_digest": "",
                        "revision": 0,
                        "hash": "",
                    },
                )

    def _read_events_unlocked(self) -> list[Event]:
        if not self.events_path.exists():
            return []
        events: list[Event] = []
        try:
            with self.events_path.open("rb") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    raw = json.loads(line.decode("utf-8"))
                    if not isinstance(raw, dict):
                        raise EventIntegrityError(f"event is not an object at line {line_number}")
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
                    if missing:
                        raise EventIntegrityError(
                            f"event missing required fields at line {line_number}: "
                            + ", ".join(missing)
                        )
                    if any(
                        type(raw[field]) is not int
                        for field in ("schema_version", "revision", "seq")
                    ):
                        raise EventIntegrityError(
                            f"event integer fields must be exact integers at line {line_number}"
                        )
                    payload = raw.get("payload", {})
                    aliases_valid = (
                        raw.get("schema") == EVENT_VERSION
                        and raw.get("schema_version") == 1
                        and int(raw.get("seq", -1)) == int(raw.get("revision", -2))
                        and str(raw.get("prev_digest", "")) == str(raw.get("prev_hash", ""))
                        and str(raw.get("event_digest", "")) == str(raw.get("event_hash", ""))
                        and str(raw.get("payload_digest", "")) == canonical_hash(payload)
                    )
                    if not aliases_valid:
                        raise EventIntegrityError(f"event aliases or payload digest disagree at line {line_number}")
                    event = Event.from_dict(raw)
                    expected_prev = events[-1].event_hash if events else ""
                    if event.event_type == "run.created" and events:
                        raise EventIntegrityError(
                            "run.created must appear exactly once at revision 1"
                        )
                    if events and event.run_id != events[0].run_id:
                        raise EventIntegrityError(f"run identity changed at line {line_number}")
                    if event.revision != len(events) + 1 or not event.verify(expected_prev):
                        raise EventIntegrityError(f"invalid event chain at line {line_number}")
                    events.append(event)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            if isinstance(exc, EventIntegrityError):
                raise
            raise EventIntegrityError(f"cannot read event stream: {exc}") from exc
        head = self._read_head_unlocked()
        expected_hash = events[-1].event_hash if events else ""
        if head["revision"] != len(events) or head["hash"] != expected_hash:
            raise EventIntegrityError("event stream and revision head disagree")
        return events

    def _read_head_unlocked(self) -> dict[str, Any]:
        try:
            value = json.loads(self.head_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise EventIntegrityError("revision head must be an object")
            required = {
                "schema",
                "schema_version",
                "seq",
                "event_digest",
                "revision",
                "hash",
            }
            missing = sorted(required - set(value))
            extra = sorted(set(value) - required)
            if missing:
                raise EventIntegrityError(
                    "revision head missing required fields: " + ", ".join(missing)
                )
            if extra:
                raise EventIntegrityError(
                    "revision head has unexpected fields: " + ", ".join(extra)
                )
            if any(
                type(value[field]) is not int
                for field in ("schema_version", "revision", "seq")
            ):
                raise EventIntegrityError("revision head integer fields must be exact integers")
            if any(
                type(value[field]) is not str
                for field in ("schema", "hash", "event_digest")
            ):
                raise EventIntegrityError(
                    "revision head schema and digests must be strings"
                )
            revision = value["revision"]
            digest = value["hash"]
            if (
                value["schema"] != "sips.runtime.head.v1"
                or value["schema_version"] != 1
                or value["seq"] != revision
                or value["event_digest"] != digest
            ):
                raise EventIntegrityError("revision head aliases disagree")
            if revision < 0:
                raise EventIntegrityError("revision head cannot be negative")
            if revision == 0 and digest:
                raise EventIntegrityError("revision zero head must have an empty digest")
            if revision > 0 and (
                len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise EventIntegrityError(
                    "revision head digest must be lower-case SHA-256"
                )
            return {
                "revision": revision,
                "hash": digest,
            }
        except EventIntegrityError:
            raise
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise EventIntegrityError(f"invalid revision head: {exc}") from exc

    @property
    def revision(self) -> int:
        with _file_lock(self.lock_path):
            return self._read_head_unlocked()["revision"]

    @property
    def head_hash(self) -> str:
        with _file_lock(self.lock_path):
            return self._read_head_unlocked()["hash"]

    def events(self) -> tuple[Event, ...]:
        with _file_lock(self.lock_path):
            return tuple(self._read_events_unlocked())

    @contextmanager
    def event_snapshot(self) -> Iterator[tuple[Event, ...]]:
        """Yield one verified event/head snapshot while blocking appends."""

        with _file_lock(self.lock_path):
            yield tuple(self._read_events_unlocked())

    def append(
        self,
        event_type: str,
        run_id: str,
        payload: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        expected_revision: int | None = None,
        timestamp: str | None = None,
    ) -> Event:
        if (
            not isinstance(event_type, str)
            or not event_type.strip()
            or event_type != event_type.strip()
        ):
            raise ValueError("event_type must be a non-empty trimmed string")
        validate_safe_identifier(run_id, label="run_id")
        if payload is not None and not isinstance(payload, Mapping):
            raise TypeError("event payload must be an object or null")
        normalized_payload = dict(payload) if payload is not None else {}
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str)
            or not idempotency_key.strip()
            or idempotency_key != idempotency_key.strip()
        ):
            raise ValueError(
                "idempotency_key must be a non-empty trimmed string or null"
            )
        if expected_revision is not None and (
            not isinstance(expected_revision, int)
            or isinstance(expected_revision, bool)
            or expected_revision < 0
        ):
            raise ValueError(
                "expected_revision must be an exact non-negative integer or null"
            )
        if timestamp is not None and (
            not isinstance(timestamp, str)
            or not timestamp.strip()
            or timestamp != timestamp.strip()
        ):
            raise ValueError("timestamp must be a non-empty trimmed string or null")
        with _file_lock(self.lock_path):
            events = self._read_events_unlocked()
            if idempotency_key is not None:
                for prior in events:
                    if prior.idempotency_key == idempotency_key:
                        if (
                            prior.run_id != run_id
                            or prior.event_type != event_type
                            # Python mapping equality collapses JSON-distinct
                            # values (for example ``True == 1`` and
                            # ``1.0 == 1``).  Idempotency is a wire-contract
                            # boundary, so compare the canonical bytes that
                            # are hashed into the event instead.
                            or canonical_bytes(prior.payload)
                            != canonical_bytes(normalized_payload)
                        ):
                            raise IdempotencyConflict(f"idempotency key already used: {idempotency_key}")
                        return prior
            if event_type == "run.created" and events:
                raise EventIntegrityError(
                    "run.created must appear exactly once at revision 1"
                )
            if events and events[0].run_id != run_id:
                raise EventIntegrityError(
                    f"run identity changed: {events[0].run_id} -> {run_id}"
                )
            revision = len(events)
            if expected_revision is not None and expected_revision != revision:
                raise RevisionConflict(f"expected revision {expected_revision}, current {revision}")
            event = Event(
                event_type=event_type,
                run_id=run_id,
                revision=revision + 1,
                payload=normalized_payload,
                prev_hash=events[-1].event_hash if events else "",
                idempotency_key=idempotency_key,
                timestamp=timestamp or Event(event_type, run_id, 0).timestamp,
            ).seal()
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("ab") as handle:
                handle.write(canonical_json(event.to_dict()).encode("utf-8") + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            atomic_write_json(
                self.head_path,
                {
                    "schema": "sips.runtime.head.v1",
                    "schema_version": 1,
                    "seq": event.revision,
                    "event_digest": event.event_hash,
                    "revision": event.revision,
                    "hash": event.event_hash,
                },
            )
            return event

    def append_event(
        self,
        event: Event | Mapping[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> Event:
        item = event if isinstance(event, Event) else Event.from_dict(event)
        return self.append(
            item.event_type,
            item.run_id,
            item.payload,
            idempotency_key=item.idempotency_key,
            expected_revision=expected_revision,
            timestamp=item.timestamp,
        )

    def verify(self) -> bool:
        with _file_lock(self.lock_path):
            self._read_events_unlocked()
            return True

    def replay(
        self,
        reducer: Callable[[Any, Event], Any] | None = None,
        initial: Any = None,
    ) -> Any:
        events = self.events()
        if reducer is None:
            return list(events)
        state = initial
        for event in events:
            state = reducer(state, event)
        return state

    def find_idempotency(self, key: str) -> Event | None:
        return next((event for event in self.events() if event.idempotency_key == key), None)
