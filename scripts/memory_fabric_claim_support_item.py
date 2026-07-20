from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_causal_audit import causal_audit
from memory_fabric_claim_support_text import dedupe, is_causal_claim, support_candidates
from memory_fabric_contradiction_audit import contradiction_report
from memory_fabric_retrieval_gate import retrieval_gate
from memory_fabric_search import search_records
from memory_fabric_thread_brief import filtered_records


def claim_item(
    claim: str,
    *,
    scope: str,
    status: str,
    provenance_type: str,
    confidence: str,
    verify_before_use: str,
    limit: int,
    max_nodes: int,
    max_edges: int,
    path: str | Path | None,
) -> dict[str, Any]:
    search = search_records(
        query=claim,
        scope=scope,
        status=status,
        provenance_type=provenance_type,
        confidence=confidence,
        verify_before_use=verify_before_use,
        limit=limit,
        path=path,
    )
    candidates = search.get("records", [])
    records = support_candidates(claim, candidates)
    support_gate = retrieval_gate(records)
    conflicts = contradiction_report(
        records,
        filtered_records(
            scope=scope,
            status=status,
            confidence=confidence,
            provenance_type=provenance_type,
            verify_before_use=verify_before_use,
            path=path,
        ),
    )
    causal = causal_summary(
        claim,
        scope=scope,
        status=status,
        provenance_type=provenance_type,
        confidence=confidence,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    support = support_status(records, support_gate, conflicts, causal)
    return {
        "claim": claim,
        "status": support,
        "claim_kind": "causal" if is_causal_claim(claim) else "descriptive",
        "candidate_record_count": len(candidates),
        "support_record_count": len(records),
        "selected_records": support_records(records),
        "candidate_retrieval_gate": search.get("retrieval_gate", {}),
        "retrieval_gate": support_gate,
        "conflict": conflict_summary(conflicts),
        "causal": causal,
        "recommended_next_checks": claim_next_checks(support, records, support_gate, conflicts, causal),
    }


def support_status(
    records: list[dict[str, Any]],
    support_gate: dict[str, Any],
    conflicts: dict[str, Any],
    causal: dict[str, Any],
) -> str:
    if not records:
        return "unsupported"
    if not support_gate.get("strong_claim_ready"):
        return "needs_verification"
    if not conflicts.get("ok"):
        return "needs_verification"
    if causal.get("required") and not causal.get("ok"):
        return "needs_verification"
    return "supported"


def support_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.get("id"),
            "title": record.get("title"),
            "tier": record.get("tier"),
            "trust": record.get("trust", {}),
            "retrieval": record.get("retrieval", {}),
            "claim_match_coverage": record.get("claim_match_coverage", {}),
            "evidence_path": record.get("provenance", {}).get("evidence_path", ""),
            "provenance_type": record.get("provenance", {}).get("type", ""),
            "score": record.get("_score", 0),
        }
        for record in records
    ]


def conflict_summary(conflicts: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": conflicts["ok"],
        "active_superseded_count": conflicts["active_superseded_count"],
        "active_contradiction_count": conflicts["active_contradiction_count"],
        "resolution_plan": conflicts["resolution_plan"],
        "claim_boundary": conflicts["claim_boundary"],
    }


def causal_summary(
    claim: str,
    *,
    scope: str,
    status: str,
    provenance_type: str,
    confidence: str,
    verify_before_use: str,
    max_nodes: int,
    max_edges: int,
    path: str | Path | None,
) -> dict[str, Any]:
    if not is_causal_claim(claim):
        return {
            "required": False,
            "ok": True,
            "status": "not_causal_claim",
            "claim_boundary": "Causal audit only gates claims with causal language.",
        }
    result = causal_audit(
        scope=scope,
        query=claim,
        status=status,
        provenance_type=provenance_type,
        confidence=confidence,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    return {
        "required": True,
        "ok": result["ok"],
        "status": result["status"],
        "causal_path_count": result["causal_path_count"],
        "needs_verification_count": result["needs_verification_count"],
        "missing_evidence_node_count": result["missing_evidence_node_count"],
        "required_citation_paths": result["required_citation_paths"],
        "recommended_next_checks": result["recommended_next_checks"],
        "causal_paths": result["causal_paths"],
        "claim_boundary": result["claim_boundary"],
    }


def claim_next_checks(
    status_value: str,
    records: list[dict[str, Any]],
    support_gate: dict[str, Any],
    conflicts: dict[str, Any],
    causal: dict[str, Any],
) -> list[str]:
    checks = []
    if status_value == "unsupported":
        checks.append("record_source_backed_memory_or_downgrade_claim")
    checks.extend(support_gate.get("recommended_next_checks", []))
    if not conflicts.get("ok"):
        checks.append("resolve_conflicts_or_supersede_records")
    if causal.get("required") and not causal.get("ok"):
        checks.extend(causal.get("recommended_next_checks", []))
    if records and status_value != "supported":
        checks.append("cite_only_ready_evidence_or_mark_claim_as_unverified")
    return dedupe(checks)
