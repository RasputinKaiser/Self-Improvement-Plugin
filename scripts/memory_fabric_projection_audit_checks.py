from __future__ import annotations
from typing import Any

from memory_fabric_projection_body_scan import body_paths


SOURCE_OF_TRUTH = "append-only memory fabric store"
REQUIRED_KEYS = [
    "counts",
    "status_counts",
    "confidence_counts",
    "provenance_counts",
    "verify_before_use_counts",
]


def projection_violations(
    projection: dict[str, Any],
    byte_count: int,
    max_bytes: int,
    max_recent: int,
) -> list[str]:
    return (
        size_violations(byte_count, max_bytes)
        + metadata_violations(projection)
        + recent_violations(projection.get("recent"), max_recent)
        + required_key_violations(projection)
    )


def size_violations(byte_count: int, max_bytes: int) -> list[str]:
    return ["projection_too_large"] if byte_count > max_bytes else []


def metadata_violations(projection: dict[str, Any]) -> list[str]:
    violations = []
    if projection.get("source_of_truth") != SOURCE_OF_TRUTH:
        violations.append("source_of_truth_marker_missing")
    if not projection.get("memory_fabric_store"):
        violations.append("memory_fabric_store_missing")
    return violations


def recent_violations(recent: Any, max_recent: int) -> list[str]:
    if not isinstance(recent, list):
        return ["recent_not_list"]
    violations = ["recent_exceeds_limit"] if len(recent) > max_recent else []
    if body_paths(recent):
        violations.append("body_fields_present")
    return violations


def required_key_violations(projection: dict[str, Any]) -> list[str]:
    return [f"{key}_missing" for key in REQUIRED_KEYS if key not in projection]


def recent_count(projection: dict[str, Any]) -> int:
    recent = projection.get("recent")
    return len(recent) if isinstance(recent, list) else 0
