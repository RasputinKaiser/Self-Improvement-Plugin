from __future__ import annotations
from typing import Any


def reasoning_summary(brief: dict[str, Any]) -> dict[str, Any]:
    readiness = brief.get("readiness", {})
    return {
        "status": brief.get("status"),
        "ready_for_answer": brief.get("ready_for_answer"),
        "selected_record_count": brief.get("selected_record_count", 0),
        "recommended_next_checks": brief.get("recommended_next_checks", []),
        "active_superseded_count": readiness.get("active_superseded_count", 0),
        "active_contradiction_count": readiness.get("active_contradiction_count", 0),
        "claim_support_status": brief.get("claim_support", {}).get("status"),
        "answer_contract_status": brief.get("answer_contract", {}).get("status"),
        "answer_contract_blocked_actions": brief.get("answer_contract", {}).get("blocked_actions", []),
        "graph_status": brief.get("graph", {}).get("status"),
        "causal_hypotheses_status": brief.get("causal_hypotheses", {}).get("status"),
        "causal_evidence_status": brief.get("causal_evidence", {}).get("status"),
        "causal_evidence_path_count": len(brief.get("causal_evidence", {}).get("paths", [])),
        "causal_evidence_missing_node_count": brief.get("causal_evidence", {}).get(
            "missing_evidence_node_count",
            0,
        ),
        "causal_evidence_required_citation_count": len(
            brief.get("causal_evidence", {}).get("required_citation_paths", []),
        ),
        "claim_boundary": brief.get("claim_boundary", ""),
    }


def answer_eval_summary(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": evaluation.get("status"),
        "ok": evaluation.get("ok"),
        "required_terms": evaluation.get("required_terms", []),
        "score_delta": evaluation.get("improvement", {}).get("score_delta", 0),
        "cited_evidence_delta": evaluation.get("improvement", {}).get("cited_evidence_delta", 0),
        "proof_boundary_status": evaluation.get("proof_boundary_status", {}).get("status", ""),
        "claim_boundary": evaluation.get("claim_boundary", ""),
    }


def memory_attribution_summary(attribution: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": attribution.get("status", ""),
        "ok": attribution.get("ok"),
        "attribution_kind": attribution.get("attribution_kind", ""),
        "score_delta": attribution.get("score_delta", 0),
        "cited_evidence_count": attribution.get("cited_evidence_count", 0),
        "causal_evidence_path_count": attribution.get("causal_evidence_path_count", 0),
        "claim_boundary": attribution.get("claim_boundary", ""),
    }
