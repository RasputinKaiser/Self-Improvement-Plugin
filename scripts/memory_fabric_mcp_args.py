from __future__ import annotations
import json


def optional(value: str) -> str | None:
    return value if value else None


def optional_paths(value: str) -> list[str]:
    return list(filter(None, [value]))


def csv_items(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def optional_json_object(value: str) -> dict[str, object] | None:
    if not value:
        return None
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data
