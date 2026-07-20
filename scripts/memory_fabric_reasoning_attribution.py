from __future__ import annotations
from typing import Any


CLAIM_BOUNDARY = (
    "Memory attribution is a deterministic receipt over answer deltas, citations, proof boundaries, "
    "and causal evidence readiness; it does not prove external truth or model reasoning."
)


def memory_attribution(
    evaluation: dict[str, Any],
    evidence: dict[str, Any],
    causal_policy: dict[str, Any],
    brief: dict[str, Any],
) -> dict[str, Any]:
    improvement = evaluation.get("improvement", {})
    proof = evaluation.get("proof_boundary_status", {})
    causal = brief.get("causal_evidence", {})
    status = attribution_status(improvement, evidence, proof, causal_policy, causal)
    return {
        "ok": status in {"ready_causal_memory_attribution", "ready_descriptive_memory_attribution"},
        "status": status,
        "attribution_kind": attribution_kind(status),
        "score_delta": int(improvement.get("score_delta", 0)),
        "cited_evidence_delta": int(improvement.get("cited_evidence_delta", 0)),
        "selected_evidence_count": int(evidence.get("selected_evidence_count", 0)),
        "cited_evidence_count": int(evidence.get("cited_evidence_count", 0)),
        "missing_evidence_count": len(evidence.get("missing_evidence_paths", [])),
        "causal_answer_status": causal_policy.get("status", ""),
        "answer_contains_causal_claim": bool(causal_policy.get("answer_contains_causal_claim")),
        "causal_evidence_status": causal.get("status", ""),
        "causal_evidence_path_count": len(causal.get("paths", [])),
        "causal_evidence_missing_node_count": int(causal.get("missing_evidence_node_count", 0)),
        "proof_boundary_status": proof.get("status", ""),
        "recommended_next_checks": attribution_checks(status),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def attribution_status(
    improvement: dict[str, Any],
    evidence: dict[str, Any],
    proof: dict[str, Any],
    causal_policy: dict[str, Any],
    causal: dict[str, Any],
) -> str:
    if int(improvement.get("score_delta", 0)) <= 0:
        return "no_answer_improvement"
    if not proof.get("ok", True):
        return "proof_boundary_blocked"
    if evidence.get("missing_evidence_paths"):
        return "missing_evidence_citations"
    if int(evidence.get("cited_evidence_count", 0)) <= 0:
        return "no_cited_memory_evidence"
    if not causal_policy.get("ok", True):
        return "causal_claim_not_attributed"
    if causal.get("status") == "causal_paths_ready" and causal.get("paths"):
        return "ready_causal_memory_attribution"
    return "ready_descriptive_memory_attribution"


def attribution_kind(status: str) -> str:
    if status == "ready_causal_memory_attribution":
        return "causal"
    if status == "ready_descriptive_memory_attribution":
        return "descriptive"
    return "blocked"


def attribution_checks(status: str) -> list[str]:
    return {
        "no_answer_improvement": ["improve_memory_answer_before_claiming_memory_lift"],
        "proof_boundary_blocked": ["fix_proof_boundary_before_claiming_memory_attribution"],
        "missing_evidence_citations": ["cite_all_memory_evidence_before_claiming_attribution"],
        "no_cited_memory_evidence": ["cite_memory_evidence_before_claiming_attribution"],
        "causal_claim_not_attributed": ["require_ready_causal_paths_before_claiming_causal_attribution"],
    }.get(status, [])
