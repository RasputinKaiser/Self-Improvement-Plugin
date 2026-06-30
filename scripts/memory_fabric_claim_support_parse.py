from __future__ import annotations
import json
import sys
from pathlib import Path


def audit_claims(claims_json: str, query: str) -> list[str]:
    if claims_json:
        return claims_from_json(claims_json)
    return [query.strip()] if query.strip() else []


def claims_from_json(value: str) -> list[str]:
    data = json.loads(raw_json_text(value))
    if isinstance(data, dict):
        data = data.get("claims", [])
    if not isinstance(data, list):
        raise ValueError("claims_json must be a JSON array or object with a claims array")
    return [str(item).strip() for item in data if str(item).strip()]


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
