from __future__ import annotations
from typing import Any, Callable

from memory_fabric_schema import normalize_confidence, normalize_provenance_type, normalize_status, normalize_tier
from memory_fabric_search_filters import record_confidence


LEGACY_PROVENANCE_TYPES = {
    "command_output": "verified_command",
    "verified_commands": "verified_command",
    "live_tool_surface_check": "source_backed_agent_run",
    "current_goal_work": "user_instruction",
}


def enum_violations(record: dict[str, Any]) -> list[str]:
    checks = [
        ("tier_invalid", normalize_tier, record.get("tier")),
        ("status_invalid", normalize_status, record.get("status")),
    ]
    violations = [code for code, normalizer, value in checks if invalid(normalizer, value)]
    if provenance_invalid(provenance_type(record)):
        violations.append("provenance_type_invalid")
    return violations


def invalid(normalizer: Callable[[str], str], value: Any) -> bool:
    try:
        normalizer(str(value or ""))
        return False
    except ValueError:
        return True


def confidence_warnings(record: dict[str, Any]) -> list[str]:
    raw = str(record.get("confidence", "")).strip().lower()
    if not raw:
        return []
    try:
        normalize_confidence(raw)
        return []
    except ValueError:
        return [f"confidence_normalized_to_{record_confidence(record)}"]


def provenance_warnings(record: dict[str, Any]) -> list[str]:
    raw = provenance_type(record)
    normalized = LEGACY_PROVENANCE_TYPES.get(raw)
    return [f"provenance_type_normalized_to_{normalized}"] if normalized else []


def provenance_invalid(raw: str) -> bool:
    if raw in LEGACY_PROVENANCE_TYPES:
        return False
    return invalid(normalize_provenance_type, raw)


def provenance_type(record: dict[str, Any]) -> str:
    provenance = record.get("provenance")
    if isinstance(provenance, dict):
        return str(provenance.get("type", ""))
    return ""
