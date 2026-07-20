from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_decision_context import decision_context
from memory_fabric_graph_edges import EDGE_TYPE_PRIORITY, build_edges, edge_type_counts
from memory_fabric_jsonl import load_records, store_path
from memory_fabric_path_explain import path_explanation
from memory_fabric_path_use import path_use_ledger
from memory_fabric_search import match_score
from memory_fabric_search_filters import apply_record_filters, confidence_value
from memory_fabric_search_filters import created_at_timestamp, provenance_value, record_confidence
from memory_fabric_search_filters import trust_status, verify_value
from memory_fabric_schema import normalize_status
from memory_fabric_time import utc_now


CLAIM_BOUNDARY = (
    "Memory graph edges are deterministic context links from record metadata, shared evidence, "
    "and explicit body markers. They help reasoning but do not prove the linked claims."
)


def memory_graph(
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
    records = select_records(
        scope=scope,
        query=query,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        max_nodes=max_nodes,
        path=path,
    )
    edges, truncated_edges = build_edges(records, max_edges=max_edges)
    paths = reasoning_paths(records, edges)
    ledger = path_use_ledger(paths)
    return {
        "ok": True,
        "generated_at": utc_now(),
        "scope": scope or None,
        "query": query or None,
        "status": status or None,
        "store": str(store_path(path)),
        "source_of_truth": "append-only memory fabric store",
        "claim_boundary": CLAIM_BOUNDARY,
        "limits": {"max_nodes": max_nodes, "max_edges": max_edges},
        "node_count": len(records),
        "edge_count": len(edges),
        "edge_type_counts": edge_type_counts(edges),
        "decision_context": decision_context(edges),
        "path_use_ledger": ledger,
        "truncated_edges": truncated_edges,
        "reasoning_path_count": len(paths),
        "reasoning_paths": paths,
        "nodes": [graph_node(record) for record in records],
        "edges": edges,
    }


def select_records(
    scope: str,
    query: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    max_nodes: int,
    path: str | Path | None,
) -> list[dict[str, Any]]:
    records = apply_record_filters(
        load_records(path),
        scope=scope,
        status_filter=normalize_status(status) if status.strip() else "",
        provenance_filter=provenance_value(provenance_type),
        confidence_filter=confidence_value(confidence),
        verify_filter=verify_value(verify_before_use),
    )
    scored = scored_records(records, query)
    scored.sort(key=lambda item: (-int(item.get("_score", 0)), -created_at_timestamp(item), str(item.get("id", ""))))
    return scored[: max(1, int(max_nodes))]


def scored_records(records: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    scored = []
    for record in records:
        score = match_score(record, query)
        if query and score <= 0:
            continue
        scored.append({**record, "_score": score or 1})
    return scored


def graph_node(record: dict[str, Any]) -> dict[str, Any]:
    provenance = record.get("provenance", {})
    return {
        "id": record.get("id"),
        "tier": record.get("tier"),
        "title": record.get("title"),
        "status": record.get("status"),
        "confidence": record_confidence(record),
        "scope": record.get("scope"),
        "tags": record.get("tags", []),
        "provenance_type": provenance.get("type"),
        "evidence_path": provenance.get("evidence_path", ""),
        "verify_before_use": record.get("verify_before_use"),
        "trust": trust_status(record),
        "created_at": record.get("created_at"),
        "score": record.get("_score", 0),
    }


def reasoning_paths(records, edges, max_paths=8):
    tiers = {str(record.get("id", "")): str(record.get("tier", "")) for record in records}
    records_by_id = {str(record.get("id", "")): record for record in records}
    return [path_item(tiers, records_by_id, edge) for edge in sorted(edges, key=edge_rank)[:max_paths]]


def path_item(tiers, records_by_id, edge):
    ids = [str(edge["source"]), str(edge["target"])]
    return {
        "nodes": ids,
        "tiers": [tiers.get(item, "") for item in ids],
        "edges": [str(edge["type"])],
        "explanation": path_explanation(records_by_id, edge),
        "score": int(edge.get("weight", 0)) + len({tiers.get(item, "") for item in ids}),
    }


def edge_rank(edge):
    return (
        EDGE_TYPE_PRIORITY.get(str(edge.get("type", "")), 9),
        -int(edge.get("weight", 0)),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
    )
