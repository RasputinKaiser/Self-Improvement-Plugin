from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any


def read_event_json(value: str) -> dict[str, Any]:
    event = read_json_object(value)
    if not event:
        raise ValueError("hook event JSON must be an object")
    return event


def read_json_object(value: str) -> dict[str, Any]:
    if not value:
        return {}
    raw = raw_json_text(value)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON value must be an object")
    return data


def raw_json_text(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    if value.lstrip().startswith(("{", "[")):
        return value
    candidate = Path(value).expanduser()
    try:
        return candidate.read_text(encoding="utf-8") if candidate.exists() else value
    except OSError:
        return value
