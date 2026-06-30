from __future__ import annotations
from typing import Any

from memory_fabric_answer_contract_citations import required_citation_groups
from memory_fabric_answer_contract_claims import claim_buckets, dedupe
from memory_fabric_answer_contract_task_gate import task_gate_summary


CLAIM_BOUNDARY = (
    "Answer contracts convert a reasoning brief into bounded answer instructions; "
    "they do not prove external truth or authorize uncited claims."
)
BASE_POLICIES = {
    "ready_policy": "answer_only_when_selected_memory_is_ready_and_claims_are_supported",
    "citation_policy": "cite selected evidence paths when making memory-backed claims",
    "uncertainty_policy": "mark claims unverified when readiness, graph, causal, claim, or task gates fail",
}


def answer_contract(
    brief: dict[str, Any],
    claims: dict[str, Any],
    answer_policy: dict[str, Any],
    checks: list[str],
) -> dict[str, Any]:
    checks = dedupe(checks)
    claim_items = claims.get("claims", [])
    citation_requirements = required_citation_groups(answer_policy)
    task_gate = task_gate_summary(brief)
    blocked_actions = blocked_task_actions(task_gate)
    status = contract_status(brief, answer_policy, checks, blocked_actions)
    buckets = claim_buckets(claim_items, answer_policy, checks, blocked_actions)
    return {
        **BASE_POLICIES,
        "behavior_contract_version": "answer_contract.v1",
        "status": status,
        "ready": status == "answer_contract_ready",
        "claim_boundary": CLAIM_BOUNDARY,
        "claim_count": len(claim_items),
        **buckets,
        "citation_requirements": citation_requirements,
        "required_citations": [item["evidence_path"] for item in citation_requirements],
        "blocked_record_ids": answer_policy.get("blocked_record_ids", []),
        "verify_record_ids": answer_policy.get("verify_record_ids", []),
        "task_gate": task_gate,
        "blocked_actions": blocked_actions,
        "recommended_next_checks": checks,
        "answer_use_status": answer_policy.get("status", ""),
    }


def contract_status(
    brief: dict[str, Any],
    answer_policy: dict[str, Any],
    checks: list[str],
    blocked_actions: list[str],
) -> str:
    if not answer_policy.get("record_count"):
        return "answer_contract_no_memory_context"
    if checks or blocked_actions or not answer_policy.get("ok"):
        return "answer_contract_needs_verification"
    return "answer_contract_ready"


def blocked_task_actions(task_gate: dict[str, Any]) -> list[str]:
    return list(task_gate.get("blocked_actions", []))
