from __future__ import annotations
from typing import Any

from memory_fabric_store_audit_enums import confidence_warnings, enum_violations, provenance_warnings
from memory_fabric_store_audit_policy import policy_warnings
from memory_fabric_store_audit_required import required_violations


def audit_record(record: Any, max_body_chars: int) -> tuple[list[str], list[str]]:
    if not isinstance(record, dict):
        return ["record_not_object"], []
    violations = required_violations(record) + enum_violations(record)
    warnings = confidence_warnings(record) + provenance_warnings(record) + policy_warnings(record)
    return violations + body_violations(record, max_body_chars), warnings


def body_violations(record: dict[str, Any], max_body_chars: int) -> list[str]:
    body = str(record.get("body", ""))
    return ["body_too_large"] if len(body) > max_body_chars else []
