from __future__ import annotations
from typing import Any

from memory_fabric_search_filters import created_at_timestamp, record_confidence, trust_status


CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
TRUST_RANK = {
    "not_current": 0,
    "verify_before_use": 1,
    "context_only": 2,
    "usable": 3,
    "ready": 4,
}


def stronger_record(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_strength = record_strength(left)
    right_strength = record_strength(right)
    if left_strength == right_strength:
        return ""
    stronger = left if left_strength > right_strength else right
    return str(stronger.get("id", ""))


def record_strength(record: dict[str, Any]) -> tuple[int, int, float]:
    return (
        TRUST_RANK.get(trust_status(record)["status"], 0),
        CONFIDENCE_RANK.get(record_confidence(record), 0),
        created_at_timestamp(record),
    )


def both_active(left: dict[str, Any], right: dict[str, Any]) -> bool:
    statuses = [str(item.get("status", "")).lower() for item in [left, right]]
    return statuses == ["active", "active"]
