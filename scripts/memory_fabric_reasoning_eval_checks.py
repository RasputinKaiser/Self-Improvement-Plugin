from __future__ import annotations
from typing import Any


def next_checks(
    brief: dict[str, Any],
    evaluation: dict[str, Any],
    evidence: dict[str, Any],
    causal_policy: dict[str, Any],
    contract_compliance: dict[str, Any],
    attribution: dict[str, Any],
) -> list[str]:
    checks = []
    checks.extend(brief_checks(brief))
    checks.extend(evaluation_checks(evaluation))
    checks.extend(evidence_checks(evidence))
    checks.extend(causal_checks(causal_policy))
    checks.extend(contract_checks(contract_compliance))
    checks.extend(attribution_checks(attribution))
    return dedupe(checks)


def brief_checks(brief: dict[str, Any]) -> list[str]:
    if brief.get("ready_for_answer"):
        return []
    return ["fix_reasoning_brief_readiness_before_answer_eval", *brief.get("recommended_next_checks", [])]


def evaluation_checks(evaluation: dict[str, Any]) -> list[str]:
    checks = []
    if not evaluation.get("ok"):
        checks.append("improve_memory_answer_or_required_terms_before_claiming_better")
    if not evaluation.get("memory", {}).get("proof_boundary_present"):
        checks.append("include_proof_boundary_language_in_memory_answer")
    if not evaluation.get("proof_boundary_status", {}).get("ok", True):
        checks.extend(evaluation.get("proof_boundary_status", {}).get("reasons", []))
    return checks


def evidence_checks(evidence: dict[str, Any]) -> list[str]:
    return ["cite_all_reasoning_brief_selected_evidence_paths"] if evidence.get("missing_evidence_paths") else []


def causal_checks(causal_policy: dict[str, Any]) -> list[str]:
    return [] if causal_policy.get("ok", True) else causal_policy.get("reasons", [])


def contract_checks(contract_compliance: dict[str, Any]) -> list[str]:
    return [] if contract_compliance.get("ok", True) else contract_compliance.get("recommended_next_checks", [])


def attribution_checks(attribution: dict[str, Any]) -> list[str]:
    return [] if attribution.get("ok", True) else attribution.get("recommended_next_checks", [])


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
