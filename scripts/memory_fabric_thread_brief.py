from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_brief_readiness import brief_readiness
from memory_fabric_decision_context import decision_context
from memory_fabric_graph import reasoning_paths
from memory_fabric_graph_edges import build_edges, edge_type_counts
from memory_fabric_jsonl import load_records, store_path
from memory_fabric_search_filters import apply_record_filters, confidence_value
from memory_fabric_search_filters import created_at_timestamp, provenance_value, verify_value
from memory_fabric_schema import normalize_status
from memory_fabric_semantic import query_profile
from memory_fabric_task_profile import task_profile
from memory_fabric_thread_brief_format import match_score, section_records, terms, trim_brief
from memory_fabric_time import utc_now


CLAIM_BOUNDARY = (
    "Bounded handoff from the append-only store; not source receipts."
)

TIER_LABELS = {
    "work": "active_projects_current_decisions_open_tasks",
    "knowledge": "domain_expertise_research_frameworks",
    "learning": "patterns_mistakes_what_works",
}


def thread_brief(
    scope: str = "",
    query: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    per_tier: int = 4,
    max_body_chars: int = 360,
    max_total_chars: int = 6000,
    path: str | Path | None = None,
) -> dict[str, Any]:
    records = filtered_records(
        scope=scope,
        status=status,
        confidence=confidence,
        provenance_type=provenance_type,
        verify_before_use=verify_before_use,
        path=path,
    )
    query_terms = terms(query)
    sections = brief_sections(records, query_terms, per_tier, max_body_chars)
    selected = selected_records(records, sections)
    brief = assemble_brief(
        scope=scope,
        query=query,
        status=status,
        path=path,
        per_tier=per_tier,
        max_body_chars=max_body_chars,
        max_total_chars=max_total_chars,
        sections=sections,
        query_terms=query_terms,
        selected=selected,
        records=records,
    )
    brief["truncated"] = trim_brief(brief, max_total_chars)
    return brief


def brief_sections(
    records: list[dict[str, Any]],
    query_terms: list[str],
    per_tier: int,
    max_body_chars: int,
) -> dict[str, list[dict[str, Any]]]:
    grouped = grouped_matches(records, query_terms)
    return {
        tier: section_records(
            items,
            per_tier=per_tier,
            max_body_chars=max_body_chars,
            query_terms=query_terms,
        )
        for tier, items in grouped.items()
    }


def grouped_matches(
    records: list[dict[str, Any]],
    query_terms: list[str],
) -> dict[str, list[tuple[int, dict[str, Any]]]]:
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {tier: [] for tier in TIER_LABELS}
    for record in records:
        add_grouped_match(grouped, record, query_terms)
    return grouped


def add_grouped_match(
    grouped: dict[str, list[tuple[int, dict[str, Any]]]],
    record: dict[str, Any],
    query_terms: list[str],
) -> None:
    tier = str(record.get("tier", ""))
    if tier not in grouped:
        return
    score = match_score(record, query_terms)
    if query_terms and score == 0:
        return
    grouped[tier].append((score, record))


def assemble_brief(
    *,
    scope: str,
    query: str,
    status: str,
    path: str | Path | None,
    per_tier: int,
    max_body_chars: int,
    max_total_chars: int,
    sections: dict[str, list[dict[str, Any]]],
    query_terms: list[str],
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": utc_now(),
        "scope": scope or None,
        "query": query or None,
        "status": status or None,
        "store": str(store_path(path)),
        "source_of_truth": "append-only memory fabric store",
        "claim_boundary": CLAIM_BOUNDARY,
        "limits": {
            "per_tier": per_tier,
            "max_body_chars": max_body_chars,
            "max_total_chars": max_total_chars,
        },
        "sections": sections,
        "counts": {tier: len(items) for tier, items in sections.items()},
        "labels": TIER_LABELS,
        "semantic_query": query_profile(query_terms),
        "task_profile": task_profile(query_terms, selected),
        "graph": handoff_graph(selected),
        "readiness": brief_readiness(selected, records),
    }


def filtered_records(
    scope: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    path: str | Path | None,
) -> list[dict[str, Any]]:
    status_filter = normalize_status(status) if status.strip() else ""
    records = apply_record_filters(
        load_records(path),
        scope=scope,
        status_filter=status_filter,
        provenance_filter=provenance_value(provenance_type),
        confidence_filter=confidence_value(confidence),
        verify_filter=verify_value(verify_before_use),
    )
    records.sort(key=lambda item: (-created_at_timestamp(item), str(item.get("id", ""))))
    return records


def selected_records(records: list[dict[str, Any]], sections: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    ids = {record["id"] for section in sections.values() for record in section}
    return [record for record in records if record.get("id") in ids]


def handoff_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    edges, truncated = build_edges(records, max_edges=24)
    paths = reasoning_paths(records, edges, max_paths=6)
    return {
        "source_of_truth": "append-only memory fabric store",
        "node_count": len(records),
        "edge_count": len(edges),
        "edge_type_counts": edge_type_counts(edges),
        "decision_context": decision_context(edges),
        "reasoning_path_count": len(paths),
        "reasoning_paths": paths,
        "truncated_edges": truncated,
        "claim_boundary": "Brief graph links are context, not proof.",
    }
