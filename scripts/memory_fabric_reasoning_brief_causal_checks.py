from __future__ import annotations
from typing import Any

from memory_fabric_claim_support import is_causal_claim


def causal_checks(causal_status: str, query: str) -> list[str]:
    if causal_status == "causal_hypotheses_need_disambiguation":
        return ["gather_discriminating_evidence_for_competing_causes"]
    if causal_status == "causal_hypotheses_need_verification":
        return ["verify_or_downgrade_non_ready_causal_hypotheses"]
    if causal_status == "no_causal_hypotheses" and is_causal_claim(query):
        return ["add_explicit_causal_edges_before_causal_answer"]
    return []


def causal_evidence_checks(causal_evidence: dict[str, Any], query: str) -> list[str]:
    if not is_causal_claim(query):
        return []
    if causal_evidence.get("ok"):
        return []
    checks = list(causal_evidence.get("recommended_next_checks", []))
    if causal_evidence.get("missing_evidence_node_count", 0):
        checks.append("cite_or_attach_evidence_for_causal_trace_nodes")
    if causal_evidence.get("causal_path_count", 0) and causal_evidence.get("needs_verification_count", 0):
        checks.append("verify_causal_trace_before_answering")
    return checks
