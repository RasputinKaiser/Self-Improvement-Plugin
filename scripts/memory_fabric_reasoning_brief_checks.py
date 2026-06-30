from __future__ import annotations
from typing import Any

from memory_fabric_reasoning_brief_causal_checks import causal_checks, causal_evidence_checks


def next_checks(
    brief: dict[str, Any],
    graph: dict[str, Any],
    hypotheses: dict[str, Any],
    causal_evidence: dict[str, Any],
    claims: dict[str, Any],
    selected: list[dict[str, Any]],
    query: str,
) -> list[str]:
    checks = []
    if not selected:
        checks.append("record_or_select_memory_before_answering")
    checks.extend(brief.get("readiness", {}).get("recommended_next_checks", []))
    checks.extend(task_profile_checks(brief))
    checks.extend(graph_checks(graph))
    checks.extend(causal_checks(hypotheses.get("status"), query))
    checks.extend(causal_evidence_checks(causal_evidence, query))
    if not claims.get("ok"):
        checks.append("answer_only_supported_claims_or_mark_unverified")
        checks.extend(claims.get("recommended_next_checks", []))
    return dedupe(checks)


def graph_checks(graph: dict[str, Any]) -> list[str]:
    if graph.get("ok"):
        return []
    return ["resolve_graph_warnings_before_strong_answer", *graph.get("warnings", [])]


def task_profile_checks(brief: dict[str, Any]) -> list[str]:
    task_profile = brief.get("task_profile", {})
    if not isinstance(task_profile, dict):
        return []
    ledger = task_profile.get("cue_ledger", {})
    if not isinstance(ledger, dict):
        return []
    checks = list(ledger.get("missing_next_checks", []))
    pricing_gate = ledger.get("pricing_gate", {})
    if isinstance(pricing_gate, dict) and not pricing_gate.get("ok", True):
        checks.append("complete_candidate_match_and_visual_comparison_before_pricing")
    return checks


def status_value(selected: list[dict[str, Any]], checks: list[str]) -> str:
    if not selected:
        return "reasoning_brief_no_memory_context"
    if checks:
        return "reasoning_brief_needs_verification"
    return "reasoning_brief_ready"


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
