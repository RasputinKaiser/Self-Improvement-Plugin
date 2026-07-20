"""Canonical serialization and path-set helpers for the SIPS runtime.

The runtime uses canonical JSON as a content-addressed boundary.  Values are
serialized with stable key ordering and separators, and non-finite numbers are
rejected rather than silently converted to non-standard JSON tokens.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the runtime JSON contract."""


def _reject_non_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise CanonicalizationError(f"non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"JSON object key at {path} must be a string"
                )
            _reject_non_finite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_non_finite(item, f"{path}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for *value*.

    ``allow_nan=False`` is retained in addition to the explicit recursive
    check so that custom numeric values cannot leak ``NaN``/``Infinity`` into
    the event log.
    """
    _reject_non_finite(value)
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc
    return text.encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


def canonical_hash(value: Any) -> str:
    """SHA-256 hash of canonical JSON, represented as lower-case hex."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_path(path: str | os.PathLike[str]) -> Path:
    """Resolve a path without requiring it to exist.

    ``Path.resolve(strict=False)`` normalizes ``..`` and follows existing
    symlinks, giving the scheduler one identity for a path regardless of how
    a worker spelled it.
    """
    return Path(path).expanduser().resolve(strict=False)


def canonical_paths(paths: Iterable[str | os.PathLike[str]]) -> frozenset[Path]:
    return frozenset(canonical_path(path) for path in paths)


def paths_overlap(left: str | os.PathLike[str], right: str | os.PathLike[str]) -> bool:
    """Whether two canonical paths name the same file or nested paths."""
    a, b = canonical_path(left), canonical_path(right)
    try:
        b.relative_to(a)
        return True
    except ValueError:
        try:
            a.relative_to(b)
            return True
        except ValueError:
            return False


def path_sets_overlap(
    left: Iterable[str | os.PathLike[str]], right: Iterable[str | os.PathLike[str]]
) -> bool:
    return any(paths_overlap(a, b) for a in left for b in right)


def read_write_conflict(
    read_set: Iterable[str | os.PathLike[str]], write_set: Iterable[str | os.PathLike[str]]
) -> bool:
    """A read conflicts with a write when either path contains the other."""
    return path_sets_overlap(read_set, write_set)


def task_sets_compatible(
    left_read: Iterable[str | os.PathLike[str]],
    left_write: Iterable[str | os.PathLike[str]],
    right_read: Iterable[str | os.PathLike[str]],
    right_write: Iterable[str | os.PathLike[str]],
) -> bool:
    """Return whether two tasks can execute concurrently.

    Read/read overlap is harmless.  Every write/write or read/write overlap is
    serialized; parent/child paths count as overlap just like equal paths.
    """
    if path_sets_overlap(left_write, right_write):
        return False
    if read_write_conflict(left_write, right_read):
        return False
    if read_write_conflict(right_write, left_read):
        return False
    return True


# Friendly aliases used by older callers.
hash_canonical = canonical_hash
normalize_path = canonical_path
