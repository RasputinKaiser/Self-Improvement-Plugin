from __future__ import annotations
from typing import Any

from memory_fabric_answer_use_policy_reasons import dedupe


def record_policy(
    record: dict[str, Any],
    blocked: set[str],
    global_reasons: list[str],
) -> dict[str, Any]:
    record_id = str(record.get("id", ""))
    trust = record.get("trust", {}).get("status", "")
    evidence_path = record.get("evidence_path", "")
    reasons = record_reasons(record, blocked, global_reasons)
    return {
        "id": record_id,
        "tier": record.get("tier", ""),
        "title": record.get("title", ""),
        "trust_status": trust,
        "provenance_type": record.get("provenance_type", ""),
        "evidence_path": evidence_path,
        "answer_use": record_answer_use(record_id, trust, evidence_path, blocked, reasons),
        "reasons": reasons,
    }


def record_reasons(
    record: dict[str, Any],
    blocked: set[str],
    global_reasons: list[str],
) -> list[str]:
    reasons = []
    reasons.extend(conflict_reasons(str(record.get("id", "")), blocked))
    reasons.extend(trust_reasons(record))
    reasons.extend(evidence_reasons(record))
    reasons.extend(global_reasons)
    return dedupe(reasons)


def conflict_reasons(record_id: str, blocked: set[str]) -> list[str]:
    return ["unresolved_conflict_or_supersession"] if record_id in blocked else []


def trust_reasons(record: dict[str, Any]) -> list[str]:
    return [] if record.get("trust", {}).get("status") == "ready" else ["record_trust_not_ready"]


def evidence_reasons(record: dict[str, Any]) -> list[str]:
    return [] if record.get("evidence_path") else ["missing_evidence_path"]


def record_answer_use(
    record_id: str,
    trust: str,
    evidence_path: str,
    blocked: set[str],
    reasons: list[str],
) -> str:
    if record_id in blocked:
        return "do_not_cite"
    if trust == "ready" and evidence_path and not reasons:
        return "cite"
    return "verify_before_citing"
