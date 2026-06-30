from __future__ import annotations
from typing import Any


CORE_FIELDS = [
    "id",
    "tier",
    "title",
    "body",
    "scope",
    "provenance",
    "confidence",
    "verify_before_use",
    "status",
    "created_at",
]


def required_violations(record: dict[str, Any]) -> list[str]:
    return [f"{field}_missing" for field in CORE_FIELDS if missing(record, field)]


def missing(record: dict[str, Any], field: str) -> bool:
    if field not in record:
        return True
    value = record.get(field)
    return value is None or value == ""
