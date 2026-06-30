from __future__ import annotations
from typing import Any

from memory_fabric_answer_contract_actions import blocked_action_violations
from memory_fabric_answer_contract_uncertainty import uncertainty_ok
from memory_fabric_answer_grounding import cited_evidence_paths


CLAIM_BOUNDARY = (
    "Answer-contract compliance checks answer text against the reasoning brief contract; "
    "it does not prove external truth or model reasoning."
)


def answer_contract_compliance(answer: str, brief: dict[str, Any]) -> dict[str, Any]:
    contract = brief.get("answer_contract", {})
    citations = citation_status(answer, contract)
    blocked = blocked_action_violations(answer, contract.get("blocked_actions", []))
    uncertainty_required = bool(contract.get("unverified_claims") or contract.get("blocked_claims"))
    missing_uncertainty = not uncertainty_ok(answer, uncertainty_required)
    checks = next_checks(citations["missing_required_citations"], blocked, missing_uncertainty)
    return {
        "ok": not checks,
        "status": "answer_contract_compliant" if not checks else "answer_contract_violation",
        "claim_boundary": CLAIM_BOUNDARY,
        "contract_status": contract.get("status", ""),
        "required_citations": citations["required_citations"],
        "cited_required_citations": citations["cited_required_citations"],
        "missing_required_citations": citations["missing_required_citations"],
        "blocked_actions": contract.get("blocked_actions", []),
        "blocked_action_violations": blocked,
        "unverified_claim_count": len(contract.get("unverified_claims", [])),
        "blocked_claim_count": len(contract.get("blocked_claims", [])),
        "uncertainty_required": uncertainty_required,
        "uncertainty_language_present": not missing_uncertainty,
        "recommended_next_checks": checks,
    }


def citation_status(answer: str, contract: dict[str, Any]) -> dict[str, list[str]]:
    required = list(contract.get("required_citations", []))
    cited = cited_evidence_paths(answer, required)
    return {
        "required_citations": required,
        "cited_required_citations": cited,
        "missing_required_citations": [path for path in required if path not in cited],
    }


def next_checks(
    missing_citations: list[str],
    blocked_actions: list[dict[str, str]],
    missing_uncertainty: bool,
) -> list[str]:
    checks = []
    if missing_citations:
        checks.append("cite_all_answer_contract_required_citations")
    if blocked_actions:
        checks.append("remove_answer_contract_blocked_actions")
    if missing_uncertainty:
        checks.append("mark_unverified_or_blocked_contract_claims_uncertain")
    return checks
