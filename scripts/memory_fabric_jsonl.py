from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from memory_fabric_time import utc_now


DEFAULT_STORE = Path.home() / ".codex" / "memory-fabric" / "memory.jsonl"


def store_path(path: str | Path | None = None) -> Path:
    raw = path or os.environ.get("CODEX_MEMORY_FABRIC_STORE") or DEFAULT_STORE
    return Path(raw).expanduser().resolve()


def append_record(record: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    target = store_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {"ok": True, "store": str(target), "record": record}


def invalid_record(target: Path, line_no: int, exc: json.JSONDecodeError) -> dict[str, Any]:
    return {
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
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                records.append(invalid_record(target, line_no, exc))
    return records
