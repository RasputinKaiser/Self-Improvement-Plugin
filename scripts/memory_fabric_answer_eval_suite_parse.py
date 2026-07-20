from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any


def suite_cases(value: str) -> list[dict[str, Any]]:
    if not value:
        return []
    data = json.loads(raw_json_text(value))
    if isinstance(data, dict):
        data = data.get("cases", [])
    if not isinstance(data, list):
        raise ValueError("cases_json must be a JSON array or object with a cases array")
    return [case for case in data if isinstance(case, dict)]


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
