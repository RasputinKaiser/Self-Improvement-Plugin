from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_causal_audit import READY_STATUS
from memory_fabric_causal_hypothesis_groups import target_groups
from memory_fabric_causal_hypothesis_paths import causal_path_hypotheses
from memory_fabric_graph import memory_graph


CLAIM_BOUNDARY = (
    "Causal hypothesis audits compare deterministic graph paths; they do not prove causality."
)


def causal_hypotheses(
    scope: str = "",
    query: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    max_nodes: int = 24,
    max_edges: int = 80,
    path: str | Path | None = None,
) -> dict[str, Any]:
    graph = memory_graph(
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
    hypotheses = causal_path_hypotheses(graph)
    groups = target_groups(hypotheses)
    non_ready = [item for item in hypotheses if item["status"] != READY_STATUS]
    competing = [group for group in groups if group["hypothesis_count"] > 1]
    return {
        "ok": bool(hypotheses) and not non_ready and not competing,
        "status": audit_status(hypotheses, non_ready, competing),
        "scope": graph["scope"],
        "query": graph["query"],
        "store": graph["store"],
        "source_of_truth": graph["source_of_truth"],
        "claim_boundary": CLAIM_BOUNDARY,
        "hypothesis_count": len(hypotheses),
        "ready_hypothesis_count": len([item for item in hypotheses if item["status"] == READY_STATUS]),
        "needs_verification_count": len(non_ready),
        "competing_target_count": len(competing),
        "recommended_next_checks": next_checks(hypotheses, non_ready, competing),
        "target_groups": groups,
    }


def audit_status(
    hypotheses: list[dict[str, Any]],
    non_ready: list[dict[str, Any]],
    competing: list[dict[str, Any]],
) -> str:
    if not hypotheses:
        return "no_causal_hypotheses"
    if competing:
        return "causal_hypotheses_need_disambiguation"
    if non_ready:
        return "causal_hypotheses_need_verification"
    return "causal_hypotheses_ready"


def next_checks(
    hypotheses: list[dict[str, Any]],
    non_ready: list[dict[str, Any]],
    competing: list[dict[str, Any]],
) -> list[str]:
    checks = []
    if not hypotheses:
        checks.append("add_explicit_causal_edges_before_causal_claims")
    if non_ready:
        checks.append("verify_or_downgrade_non_ready_causal_hypotheses")
    if competing:
        checks.append("gather_discriminating_evidence_for_competing_causes")
    if any(not item["evidence_paths"] for item in non_ready):
        checks.append("attach_source_evidence_to_causal_hypotheses")
    return checks

