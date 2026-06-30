from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_answer_grounding import answer_grounding
from memory_fabric_answer_score import answer_score
from memory_fabric_answer_terms import expected_terms
from memory_fabric_proof_boundary import proof_boundary_status
from memory_fabric_thread_brief import thread_brief


CLAIM_BOUNDARY = "Deterministic lexical answer eval; it does not prove model reasoning."


def answer_eval(
    *,
    scope: str = "",
    query: str = "",
    baseline_answer: str = "",
    memory_answer: str = "",
    required_terms: str = "",
    per_tier: int = 3,
    path: str | Path | None = None,
) -> dict[str, Any]:
    brief = thread_brief(scope=scope, query=query, per_tier=per_tier, path=path)
    terms = expected_terms(required_terms, brief)
    baseline = answer_score(baseline_answer, terms)
    memory = answer_score(memory_answer, terms)
    baseline_grounding = answer_grounding(baseline_answer, brief)
    memory_grounding = answer_grounding(memory_answer, brief)
    boundary_status = proof_boundary_status(memory_answer, brief)
    delta = memory["score"] - baseline["score"]
    ok = all(
        [
            bool(terms),
            delta > 0,
            not memory["missing_terms"],
            memory["proof_boundary_present"],
            boundary_status["ok"],
            memory["evidence_reference_count"] > baseline["evidence_reference_count"],
            grounding_improved(baseline_grounding, memory_grounding),
        ]
    )
    return {
        "ok": ok,
        "status": "memory_answer_improved" if ok else "memory_answer_not_proven_better",
        "claim_boundary": CLAIM_BOUNDARY,
        "scope": scope or None,
        "query": query or None,
        "required_terms": terms,
        "baseline": baseline,
        "memory": memory,
        "baseline_grounding": baseline_grounding,
        "memory_grounding": memory_grounding,
        "proof_boundary_status": boundary_status,
        "improvement": {
            "score_delta": delta,
            "covered_term_delta": len(memory["covered_terms"]) - len(baseline["covered_terms"]),
            "evidence_reference_delta": memory["evidence_reference_count"] - baseline["evidence_reference_count"],
            "cited_evidence_delta": (
                memory_grounding["cited_evidence_count"] - baseline_grounding["cited_evidence_count"]
            ),
        },
        "brief": brief_summary(brief),
    }


def grounding_improved(baseline: dict[str, Any], memory: dict[str, Any]) -> bool:
    if not memory["selected_evidence_paths"]:
        return False
    return memory["cited_evidence_count"] > baseline["cited_evidence_count"]


def brief_summary(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_of_truth": brief.get("source_of_truth", ""),
        "counts": brief.get("counts", {}),
        "readiness": brief.get("readiness", {}),
        "graph": {
            "reasoning_path_count": brief.get("graph", {}).get("reasoning_path_count", 0),
            "claim_boundary": brief.get("graph", {}).get("claim_boundary", ""),
        },
    }
