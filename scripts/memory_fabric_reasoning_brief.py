from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_causal_audit import causal_audit
from memory_fabric_causal_hypotheses import causal_hypotheses
from memory_fabric_claim_support import claim_support_audit
from memory_fabric_graph_audit import graph_audit
from memory_fabric_answer_use_policy import answer_use_policy
from memory_fabric_answer_contract import answer_contract
from memory_fabric_reasoning_brief_checks import next_checks, status_value
from memory_fabric_reasoning_brief_selection import selected_records
from memory_fabric_reasoning_brief_summaries import (
    causal_evidence_summary,
    claim_support_summary,
    graph_summary,
    hypothesis_summary,
)
from memory_fabric_thread_brief import thread_brief


CLAIM_BOUNDARY = (
    "Reasoning briefs assemble bounded memory context; they do not prove external truth or model reasoning."
)

def reasoning_brief(
    *,
    claims_json: str = "",
    scope: str = "",
    query: str = "",
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
    brief = thread_brief(
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        per_tier=per_tier,
        max_body_chars=max_body_chars,
        max_total_chars=max_total_chars,
        path=path,
    )
    graph = graph_audit(
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    hypotheses = causal_hypotheses(
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    causal_evidence = causal_audit(
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        max_edges=max_edges,
        path=path,
    )
    claims = claim_support(claims_json, scope, query, status, provenance_type, confidence, verify_before_use, path)
    selected = selected_records(brief)
    causal_trace = causal_evidence_summary(causal_evidence)
    checks = next_checks(brief, graph, hypotheses, causal_trace, claims, selected, query)
    answer_policy = answer_use_policy(selected, brief, graph, hypotheses, claims, checks)
    checks = [*checks, *answer_policy_checks(answer_policy)]
    ready = bool(selected) and not checks and answer_policy["ok"]
    contract = answer_contract(brief, claims, answer_policy, checks)
    return {
        "ok": ready,
        "status": status_value(selected, checks),
        "ready_for_answer": ready,
        "scope": brief["scope"],
        "query": brief["query"],
        "store": brief["store"],
        "source_of_truth": "append-only memory fabric store",
        "claim_boundary": CLAIM_BOUNDARY,
        "answer_contract": contract,
        "selected_record_count": len(selected),
        "selected_records": selected,
        "section_counts": brief["counts"],
        "semantic_query": brief["semantic_query"],
        "task_profile": brief["task_profile"],
        "readiness": brief["readiness"],
        "graph": graph_summary(graph),
        "causal_hypotheses": hypothesis_summary(hypotheses),
        "causal_evidence": causal_trace,
        "claim_support": claim_support_summary(claims),
        "answer_use_policy": answer_policy,
        "recommended_next_checks": checks,
    }


def claim_support(
    claims_json: str,
    scope: str,
    query: str,
    status: str,
    provenance_type: str,
    confidence: str,
    verify_before_use: str,
    path: str | Path | None,
) -> dict[str, Any]:
    if not claims_json.strip():
        return {
            "ok": True,
            "status": "no_claims_requested",
            "claim_count": 0,
            "status_counts": {},
            "recommended_next_checks": [],
            "claims": [],
            "claim_boundary": "No explicit claims were supplied for claim-support audit.",
        }
    return claim_support_audit(
        claims_json=claims_json,
        scope=scope,
        query=query,
        status=status,
        provenance_type=provenance_type,
        confidence=confidence,
        verify_before_use=verify_before_use,
        path=path,
    )


def answer_policy_checks(answer_policy: dict[str, Any]) -> list[str]:
    if answer_policy.get("ok"):
        return []
    if answer_policy.get("blocked_record_ids"):
        return ["resolve_conflicts_or_supersede_records"]
    if answer_policy.get("verify_record_ids"):
        return ["verify_selected_records_before_citing"]
    return ["verify_answer_use_policy_before_answering"]


def claims_json(claims: list[str]) -> str:
    return json.dumps({"claims": claims})
