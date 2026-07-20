from __future__ import annotations
import json
import math
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import fcntl

from memory_fabric_schema import record_schema_version
from memory_fabric_time import utc_now


DEFAULT_STORE = Path.home() / ".codex" / "memory-fabric" / "memory.jsonl"

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized.setdefault("schema_version", record_schema_version())
    return normalized


def validate_json_contract(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"JSON object key at {path} must be a string")
            validate_json_contract(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_json_contract(item, f"{path}[{index}]")


def store_path(path: str | Path | None = None) -> Path:
    raw = path or os.environ.get("CODEX_MEMORY_FABRIC_STORE") or DEFAULT_STORE
    return Path(raw).expanduser().resolve()


def _process_lock(path: Path) -> threading.Lock:
    key = str(path.expanduser().resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.Lock())


@contextmanager
def _writer_lock(target: Path):
    """Serialize appenders in this process and across cooperating processes."""

    lock_path = Path(f"{target}.lock")
    process_lock = _process_lock(lock_path)
    with process_lock:
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _fsync_parent_directory(parent: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def append_record(record: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    target = store_path(path)
    normalized = normalize_record(record)
    validate_json_contract(normalized)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with _writer_lock(target):
        # A non-empty JSONL file must end at a record boundary.  Appending to
        # an unterminated tail would concatenate the new object with the
        # damaged bytes, making the original record unrecoverable while
        # falsely reporting a successful write.  Inspect under the same
        # writer lock and fail before opening the file for append.
        if target.exists():
            with target.open("rb") as existing:
                existing.seek(0, os.SEEK_END)
                size = existing.tell()
                if size:
                    existing.seek(-1, os.SEEK_END)
                    if existing.read(1) != b"\n":
                        raise ValueError(
                            "cannot append to JSONL store with an unterminated tail"
                        )
        with target.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_parent_directory(target.parent)
    return {"ok": True, "store": str(target), "record": normalized}


def invalid_record(target: Path, line_no: int, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": record_schema_version(),
        "id": f"invalid_line_{line_no}",
        "tier": "learning",
        "title": "Invalid memory record",
        "body": str(exc),
        "scope": str(target),
        "tags": ["invalid-jsonl"],
        "provenance": {"type": "store_parse_error", "detail": str(target), "evidence_path": ""},
        "confidence": "high",
        "verify_before_use": True,
        "status": "invalid",
        "created_at": utc_now(),
    }


def load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    target = store_path(path)
    if not target.exists():
        return []
    records = []
    with target.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(
                    line,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(f"non-finite JSON constant: {value}")
                    ),
                )
                validate_json_contract(record)
                records.append(normalize_record(record) if isinstance(record, dict) else record)
            except (json.JSONDecodeError, ValueError) as exc:
                records.append(invalid_record(target, line_no, exc))
    return records
