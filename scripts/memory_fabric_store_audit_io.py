from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_jsonl import store_path, validate_json_contract


def store_entries(path: str | Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
    target = store_path(path)
    if not target.exists():
        return target, []
    entries = []
    with target.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if line.strip():
                entries.append(parse_line(line, line_no))
    return target, entries


def parse_line(line: str, line_no: int) -> dict[str, Any]:
    try:
        record = json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
        validate_json_contract(record)
        return {
            "line": line_no,
            "record": record,
            "error": "",
        }
    except (json.JSONDecodeError, ValueError) as exc:
        return {"line": line_no, "record": {}, "error": str(exc)}
