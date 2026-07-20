"""Read-only adapters for legacy fan-out and goal-state payloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


MODES = ("legacy", "shadow", "dual", "runtime")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _load(source: Any) -> tuple[Any, str, bytes]:
    if isinstance(source, (str, Path)):
        path = Path(source).expanduser()
        raw = path.read_bytes()
        try:
            return json.loads(raw.decode("utf-8")), str(path.resolve()), raw
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"legacy payload is not JSON: {exc}") from exc
    return source, "inline", _canonical(source).encode("utf-8")


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, Mapping):
        values = payload.get("records", payload.get("slices", payload.get("subtasks", [])))
        if not values and any(key in payload for key in ("objective", "parent", "id", "status")):
            values = [payload]
    else:
        values = []
    result: list[dict[str, Any]] = []
    for index, value in enumerate(values if isinstance(values, list) else []):
        if isinstance(value, Mapping):
            item = dict(value)
        else:
            item = {"value": value}
        item.setdefault("legacy_id", str(item.get("id", f"legacy-{index + 1}")))
        item.setdefault("source", "legacy")
        result.append(item)
    return result


def import_legacy(source: Any, *, mode: str = "legacy", namespace: str = "sips") -> dict[str, Any]:
    """Normalize a legacy payload without writing or mutating its source."""
    mode = str(mode).strip().lower()
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    payload, source_name, raw_bytes = _load(source)
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    migration_id = f"{namespace}-migration-{raw_hash[:16]}"
    records = _records(payload)
    return {
        "ok": True,
        "mode": mode,
        "source": source_name,
        "raw": payload,
        "raw_hash": raw_hash,
        "migration_id": migration_id,
        "records": records,
        "record_count": len(records),
        "read_only": True,
        "write_performed": False,
        "writes": [],
    }


def adapt_legacy(source: Any, *, mode: str = "legacy", namespace: str = "sips") -> dict[str, Any]:
    return import_legacy(source, mode=mode, namespace=namespace)


class LegacyAdapter:
    """Small object wrapper convenient for API/controller injection."""

    def __init__(self, *, mode: str = "legacy", namespace: str = "sips") -> None:
        mode = str(mode).strip().lower()
        if mode not in MODES:
            raise ValueError(f"mode must be one of: {', '.join(MODES)}")
        self.mode = mode
        self.namespace = namespace

    def read(self, source: Any) -> dict[str, Any]:
        return import_legacy(source, mode=self.mode, namespace=self.namespace)


legacy_import = import_legacy

__all__ = ["MODES", "LegacyAdapter", "import_legacy", "adapt_legacy", "legacy_import"]
