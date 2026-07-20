from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_answer_eval import answer_eval
from memory_fabric_answer_contract_compliance import answer_contract_compliance
from memory_fabric_causal_answer_policy import causal_answer_policy
from memory_fabric_reasoning_attribution import memory_attribution
from memory_fabric_reasoning_brief import reasoning_brief
from memory_fabric_reasoning_eval_checks import next_checks
from memory_fabric_reasoning_eval_evidence import reasoning_evidence_grounding
from memory_fabric_reasoning_eval_summary import (
    answer_eval_summary,
    memory_attribution_summary,
    reasoning_summary,
)


CLAIM_BOUNDARY = (
    "Reasoning eval checks deterministic answer improvement against a reasoning brief; "
    "it does not prove model reasoning or external truth."
)


def reasoning_eval(
    *,
    claims_json: str = "",
    scope: str = "",
    query: str = "",
    baseline_answer: str = "",
    memory_answer: str = "",
    required_terms: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    per_tier: int = 3,
    max_body_chars: int = 280,
    max_total_chars: int = 5000,
    max_nodes: int = 24,
    max_edges: int = 80,
    path: str | Path | None = None,
) -> dict[str, Any]:
    brief = reasoning_brief(
        claims_json=claims_json,
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        per_tier=per_tier,
        max_body_chars=max_body_chars,
        max_total_chars=max_total_chars,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    evaluation = answer_eval(
        scope=scope,
        query=query,
        baseline_answer=baseline_answer,
        memory_answer=memory_answer,
        required_terms=required_terms,
        per_tier=per_tier,
        path=path,
    )
    evidence = reasoning_evidence_grounding(memory_answer, brief)
    causal_policy = causal_answer_policy(memory_answer, brief)
    contract_compliance = answer_contract_compliance(memory_answer, brief)
    attribution = memory_attribution(evaluation, evidence, causal_policy, brief)
    checks = next_checks(brief, evaluation, evidence, causal_policy, contract_compliance, attribution)
    ok = not checks
    return {
        "ok": ok,
        "status": reasoning_eval_status(ok),
        "claim_boundary": CLAIM_BOUNDARY,
        "scope": scope or None,
        "query": query or None,
        "ready_for_answer": brief["ready_for_answer"],
        "reasoning_status": brief["status"],
        "answer_eval_status": evaluation["status"],
        "reasoning_evidence": evidence,
        "answer_contract_compliance": contract_compliance,
        "proof_boundary_status": evaluation["proof_boundary_status"],
        "causal_answer_policy": causal_policy,
        "memory_attribution": attribution,
        "improvement": evaluation["improvement"],
        "memory": evaluation["memory"],
        "baseline": evaluation["baseline"],
        "reasoning_brief": reasoning_summary(brief),
        "answer_eval": answer_eval_summary(evaluation),
        "memory_attribution_summary": memory_attribution_summary(attribution),
        "recommended_next_checks": checks,
    }


def reasoning_eval_status(ok: bool) -> str:
    return ["reasoning_answer_not_proven", "reasoning_answer_improved"][bool(ok)]
