from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

from memory_fabric_behavior_receipts import split_paths


def probe_behavior_receipt(
    behavior: str,
    live_output_json: str,
    required_fields: str = "",
    output: str = "",
    expected_values_json: str = "",
    source_json: str = "",
    source_fields: str = "",
) -> dict[str, Any]:
    data = payload(live_output_json)
    missing = missing_required_fields(data, required_fields)
    expected = expected_values(expected_values_json)
    expected.update(source_values(source_json, source_fields))
    mismatches = mismatched_fields(data, expected)
    ok = all([not missing, not mismatches])
    receipt = {
        "ok": ok,
        "status": ("current_live_behavior_stale", "current_live_behavior_ready")[ok],
        "behavior": behavior,
        "missing_current_live_fields": missing,
        "mismatched_current_live_fields": mismatches,
        "checked_fields": split_paths(required_fields),
        "claim_boundary": "Supplied-output check only.",
    }
    if output:
        Path(output).expanduser().write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return receipt


def missing_required_fields(data: dict[str, Any], required_fields: str) -> list[str]:
    return list(filter(lambda field: not has_path(data, field), split_paths(required_fields)))


def mismatched_fields(data: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    return list(filter(lambda field: value_at(data, field) != expected[field], expected))


def source_values(source_json: str, source_fields: str) -> dict[str, Any]:
    source = payload(source_json) if source_json else {}
    return {field: value_at(source, field) for field in split_paths(source_fields)}


def expected_values(value: str) -> dict[str, Any]:
    if not value:
        return {}
    data = json.loads(input_text(value))
    return data if isinstance(data, dict) else {}


def payload(value: str) -> dict[str, Any]:
    data = json.loads(input_text(value))
    if isinstance(data, dict) and isinstance(data.get("result"), str):
        return json.loads(data["result"])
    return data if isinstance(data, dict) else {}


def input_text(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    path = Path(value).expanduser()
    try:
        return path.read_text()
    except OSError:
        return value


def has_path(data: dict[str, Any], dotted: str) -> bool:
    return value_at(data, dotted) is not MISSING


MISSING = object()


def value_at(data: dict[str, Any], dotted: str) -> Any:
    item: Any = data
    for part in dotted.split("."):
        item = child_value(item, part)
        if item is MISSING:
            return MISSING
    return item


def child_value(item: Any, part: str) -> Any:
    if isinstance(item, dict):
        return item.get(part, MISSING)
    if isinstance(item, list):
        if part.isdigit():
            index = int(part)
            return item[index] if index < len(item) else MISSING
    return MISSING
