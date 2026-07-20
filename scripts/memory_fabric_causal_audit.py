from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_causal_evidence import CONTRACT_VERSION as CAUSAL_EVIDENCE_CONTRACT
from memory_fabric_causal_evidence import causal_evidence_ledger
from memory_fabric_graph import memory_graph


CLAIM_BOUNDARY = (
    "Causal audit summarizes deterministic graph path readiness; it does not prove causal truth."
)
READY_STATUS = "ready_causal_context"


def causal_audit(
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
    paths = causal_paths(graph)
    ready = [item for item in paths if item["status"] == READY_STATUS]
    needs_verification = [item for item in paths if item["status"] != READY_STATUS]
    return {
        "ok": bool(paths) and not needs_verification,
        "status": audit_status(paths, needs_verification),
        "scope": graph["scope"],
        "query": graph["query"],
        "store": graph["store"],
        "source_of_truth": graph["source_of_truth"],
        "claim_boundary": CLAIM_BOUNDARY,
        "evidence_contract_version": CAUSAL_EVIDENCE_CONTRACT,
        "causal_path_count": len(paths),
        "ready_causal_path_count": len(ready),
        "needs_verification_count": len(needs_verification),
        "required_citation_paths": required_citation_paths(paths),
        "missing_evidence_node_count": missing_evidence_node_count(paths),
        "truncated_edges": graph["truncated_edges"],
        "recommended_next_checks": next_checks(paths, needs_verification),
        "causal_paths": paths,
    }


def causal_paths(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        causal_path_item(item)
        for item in graph.get("reasoning_paths", [])
        if item.get("explanation", {}).get("causal_edge")
    ]


def causal_path_item(path: dict[str, Any]) -> dict[str, Any]:
    explanation = path.get("explanation", {})
    evidence = causal_evidence_ledger(path)
    return {
        "nodes": path.get("nodes", []),
        "edges": path.get("edges", []),
        "status": explanation.get("status", ""),
        "node_trusts": explanation.get("node_trusts", []),
        "trust_reasons": explanation.get("trust_reasons", {}),
        "evidence_paths": explanation.get("evidence_paths", []),
        "evidence_ledger": evidence,
        "required_citation_paths": evidence["required_citation_paths"],
        "missing_evidence_nodes": evidence["missing_evidence_nodes"],
        "score": path.get("score", 0),
        "claim_boundary": explanation.get("claim_boundary", ""),
    }


def audit_status(paths: list[dict[str, Any]], needs_verification: list[dict[str, Any]]) -> str:
    if not paths:
        return "no_causal_paths"
    if needs_verification:
        return "causal_paths_need_verification"
    return "causal_paths_ready"


def next_checks(paths: list[dict[str, Any]], needs_verification: list[dict[str, Any]]) -> list[str]:
    checks: list[str] = []
    if not paths:
        checks.append("add_explicit_causal_edges_before_causal_claims")
    if needs_verification:
        checks.append("verify_or_downgrade_non_ready_causal_paths")
    if any(item["missing_evidence_nodes"] for item in paths):
        checks.append("attach_source_evidence_to_causal_records")
    return checks


def required_citation_paths(paths: list[dict[str, Any]]) -> list[str]:
    citations = [
        path
        for item in paths
        for path in item.get("required_citation_paths", [])
    ]
    return list(dict.fromkeys(citations))


def missing_evidence_node_count(paths: list[dict[str, Any]]) -> int:
    return sum(len(item.get("missing_evidence_nodes", [])) for item in paths)
