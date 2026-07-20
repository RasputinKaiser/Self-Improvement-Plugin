from __future__ import annotations
from typing import Any

from memory_fabric_schema import STRONG_PROVENANCE
from memory_fabric_search_filters import record_confidence
from memory_fabric_store_audit_enums import provenance_type


LEARNING_MARKERS = ["symptom", "fix", "proof"]


def policy_warnings(record: dict[str, Any]) -> list[str]:
    return (
        weak_knowledge_warnings(record)
        + confidence_policy_warnings(record)
        + learning_marker_warnings(record)
    )


def weak_knowledge_warnings(record: dict[str, Any]) -> list[str]:
    if record.get("tier") != "knowledge" or record.get("status") != "active":
        return []
    provenance = provenance_type(record)
    evidence = str(record.get("provenance", {}).get("evidence_path", "")).strip()
    if provenance in STRONG_PROVENANCE and evidence:
        return []
    return ["active_knowledge_without_source_evidence"]


def confidence_policy_warnings(record: dict[str, Any]) -> list[str]:
    confidence = record_confidence(record)
    if confidence in {"low", "unknown"} and not bool(record.get("verify_before_use")):
        return ["low_confidence_without_verify_before_use"]
    return []


def learning_marker_warnings(record: dict[str, Any]) -> list[str]:
    if record.get("tier") != "learning" or record.get("status") != "active":
        return []
    body = str(record.get("body", "")).lower()
    missing_markers = [marker for marker in LEARNING_MARKERS if marker not in body]
    return [f"learning_missing_{marker}" for marker in missing_markers]
