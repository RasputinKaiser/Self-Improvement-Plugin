from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_graph import memory_graph, select_records
from memory_fabric_graph_expand import expansion_plan
from memory_fabric_graph_audit_refs import reference_report, scoped_ids
from memory_fabric_graph_audit_report import isolated_report, warning_report
from memory_fabric_contradiction_audit import contradiction_report
from memory_fabric_jsonl import store_path
from memory_fabric_schema import runtime_contract
from memory_fabric_time import utc_now


CLAIM_BOUNDARY = "Graph audit checks link hygiene only; graph edges are context, not proof."
GRAPH_AUDIT_CONTRACT_VERSION = "graph_audit.v5"
GRAPH_AUDIT_BEHAVIOR_FEATURES = [
    "typed_explicit_reference_counts",
    "decision_context_summary",
    "active_superseded_warnings",
    "active_contradiction_warnings",
    "append_only_resolution_plan",
    "scoped_conflicts_outside_query_selection",
    "path_use_ledger",
]


def graph_audit_contract() -> dict[str, Any]:
    return runtime_contract(
        "graph_audit",
        behavior_contract_version=GRAPH_AUDIT_CONTRACT_VERSION,
        behavior_features=GRAPH_AUDIT_BEHAVIOR_FEATURES,
        conflict_resolution_plan=True,
        detects_scoped_conflicts_outside_query_selection=True,
        resolution_plan_claim_boundary="append_only_guidance_not_memory_rewrite",
    )


def graph_audit(
    scope: str = "",
    query: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    max_nodes: int = 24,
    max_edges: int = 80,
    max_isolated_ratio: float = 0.75,
    path: str | Path | None = None,
) -> dict[str, Any]:
    graph = graph_view(
        scope,
        query,
        status,
        confidence,
        provenance_type,
        verify_before_use,
        max_nodes,
        max_edges,
        path,
    )
    records = selected(scope, query, status, confidence, provenance_type, verify_before_use, max_nodes, path)
    ids = scoped_ids(scope, status, confidence, provenance_type, verify_before_use, path)
    explicit = reference_report(records, ids)
    conflicts = contradiction_report(
        records,
        selected_all(scope, status, confidence, provenance_type, verify_before_use, path),
    )
    isolated = isolated_report(graph)
    warnings = warning_report(graph, explicit, isolated, max_isolated_ratio, conflicts)
    return {
        "ok": not warnings,
        "status": "graph_healthy" if not warnings else "graph_warnings",
        "generated_at": utc_now(),
        "scope": scope or None,
        "query": query or None,
        "store": str(store_path(path)),
        "source_of_truth": "append-only memory fabric store",
        "claim_boundary": CLAIM_BOUNDARY,
        "runtime_contract": graph_audit_contract(),
        "limits": {**graph["limits"], "max_isolated_ratio": max_isolated_ratio},
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "edge_type_counts": graph["edge_type_counts"],
        "decision_context": graph["decision_context"],
        "path_use_ledger": graph["path_use_ledger"],
        "truncated_edges": graph["truncated_edges"],
        "isolated_node_count": isolated["isolated_node_count"],
        "isolated_ratio": isolated["isolated_ratio"],
        "dangling_reference_count": explicit["dangling_reference_count"],
        "outside_selection_reference_count": explicit["outside_selection_reference_count"],
        "explicit_reference_count": explicit["explicit_reference_count"],
        "explicit_conflict_reference_count": conflicts["explicit_conflict_reference_count"],
        "active_superseded_count": conflicts["active_superseded_count"],
        "active_contradiction_count": conflicts["active_contradiction_count"],
        "warnings": warnings,
        "dangling_references": explicit["dangling_references"],
        "outside_selection_references": explicit["outside_selection_references"],
        "isolated_nodes": isolated["isolated_nodes"],
        "active_superseded_records": conflicts["active_superseded_records"],
        "active_contradictions": conflicts["active_contradictions"],
        "resolution_plan": conflicts["resolution_plan"],
        "conflict_claim_boundary": conflicts["claim_boundary"],
        "expansion_plan": expansion_plan(graph),
    }


def graph_view(
    scope: str,
    query: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    max_nodes: int,
    max_edges: int,
    path: str | Path | None,
) -> dict[str, Any]:
    return memory_graph(
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


def selected(
    scope: str,
    query: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    max_nodes: int,
    path: str | Path | None,
) -> list[dict[str, Any]]:
    return select_records(scope, query, status, confidence, provenance_type, verify_before_use, max_nodes, path)


def selected_all(
    scope: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    path: str | Path | None,
) -> list[dict[str, Any]]:
    return select_records(scope, "", status, confidence, provenance_type, verify_before_use, 10000, path)
