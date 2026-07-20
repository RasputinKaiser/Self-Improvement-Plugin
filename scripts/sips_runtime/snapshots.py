"""Atomic snapshots and rebuild helpers for an event-sourced run."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .canonical import canonical_hash
from .contracts import Event
from .events import EventStore, EventIntegrityError, atomic_write_json


class SnapshotMismatch(RuntimeError):
    pass


class SnapshotStore:
    def __init__(self, run_dir: str | os.PathLike[str]) -> None:
        self.run_dir = Path(run_dir).expanduser().resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "snapshot.json"

    def save(self, revision: int, head_hash: str, state: Mapping[str, Any]) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": "sips.runtime.state.v1",
            "schema_version": 1,
            "runtime_version": "0.4.0",
            "revision": int(revision),
            "event_head": str(head_hash),
            "head_hash": str(head_hash),
            "state_digest": canonical_hash(state),
            "state_hash": canonical_hash(state),
            "state": dict(state),
        }
        atomic_write_json(self.path, document)
        return document

    def load(
        self,
        *,
        expected_revision: int | None = None,
        expected_hash: str | None = None,
    ) -> dict[str, Any]:
        if not self.path.exists():
            raise SnapshotMismatch("snapshot does not exist")
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            state = document["state"]
            state_hash = canonical_hash(state)
            if (
                document.get("schema") != "sips.runtime.state.v1"
                or type(document.get("schema_version")) is not int
                or document.get("schema_version") != 1
                or document.get("runtime_version") != "0.4.0"
            ):
                raise SnapshotMismatch("snapshot schema or version mismatch")
            revision = document.get("revision")
            if type(revision) is not int or revision < 0:
                raise SnapshotMismatch("snapshot revision type mismatch")
            if (
                document.get("state_hash") != state_hash
                or document.get("state_digest") != state_hash
            ):
                raise SnapshotMismatch("snapshot state hash mismatch")
            if str(document.get("event_head", "")) != str(
                document.get("head_hash", "")
            ):
                raise SnapshotMismatch("snapshot head aliases disagree")
            if expected_revision is not None and revision != expected_revision:
                raise SnapshotMismatch("snapshot revision mismatch")
            if expected_hash is not None and str(document.get("head_hash", "")) != expected_hash:
                raise SnapshotMismatch("snapshot head hash mismatch")
            return document
        except SnapshotMismatch:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SnapshotMismatch(f"invalid snapshot: {exc}") from exc

    def rebuild(
        self,
        event_store: EventStore,
        reducer: Callable[[Any, Event], Any],
        initial: Any,
    ) -> dict[str, Any]:
        state = event_store.replay(reducer, initial)
        if not isinstance(state, Mapping):
            raise TypeError("snapshot state must be a mapping")
        return self.save(event_store.revision, event_store.head_hash, state)

    def validate_against(self, event_store: EventStore) -> dict[str, Any]:
        return self.load(expected_revision=event_store.revision, expected_hash=event_store.head_hash)


def rebuild_snapshot(
    event_store: EventStore,
    snapshot_store: SnapshotStore,
    reducer: Callable[[Any, Event], Any],
    initial: Any,
) -> dict[str, Any]:
    return snapshot_store.rebuild(event_store, reducer, initial)
