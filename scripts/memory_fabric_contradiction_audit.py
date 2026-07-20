from __future__ import annotations
from typing import Any

from memory_fabric_conflict_refs import selected_conflict_ref
from memory_fabric_conflict_strength import both_active, stronger_record
from memory_fabric_graph_explicit import explicit_references
from memory_fabric_conflict_resolution import resolution_plan
from memory_fabric_search_filters import trust_status


CLAIM_BOUNDARY = "Conflict audit surfaces typed memory tensions; it does not rewrite records."


def contradiction_report(
    records: list[dict[str, Any]],
    universe_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    universe = universe_records or records
    by_id = records_by_id(universe)
    refs = selected_conflict_refs(universe, selected_record_ids(records), by_id)
    active_superseded = active_superseded_items(refs, by_id)
    active_contradictions = active_contradiction_items(refs, by_id)
    return contradiction_summary(refs, active_superseded, active_contradictions)


def selected_record_ids(records: list[dict[str, Any]]) -> set[str]:
    return {str(record.get("id", "")) for record in records if record.get("id")}


def records_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("id", "")): record for record in records}


def selected_conflict_refs(
    records: list[dict[str, Any]],
    selected_ids: set[str],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    refs = []
    for record in records:
        refs.extend(selected_refs_for_record(record, selected_ids, by_id))
    return refs


def selected_refs_for_record(
    record: dict[str, Any],
    selected_ids: set[str],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        ref
        for ref in explicit_references(record)
        if selected_conflict_ref(ref, selected_ids, by_id)
    ]


def active_superseded_items(
    refs: list[dict[str, str]],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        item
        for item in [superseded_item(ref, by_id) for ref in refs if ref["type"] == "supersedes"]
        if item["target_status"] == "active"
    ]


def active_contradiction_items(
    refs: list[dict[str, str]],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        item
        for item in [contradiction_item(ref, by_id) for ref in refs if ref["type"] == "contradicts"]
        if item["both_active"]
    ]


def contradiction_summary(
    refs: list[dict[str, str]],
    active_superseded: list[dict[str, Any]],
    active_contradictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": not active_superseded and not active_contradictions,
        "claim_boundary": CLAIM_BOUNDARY,
        "explicit_conflict_reference_count": len(refs),
        "active_superseded_count": len(active_superseded),
        "active_contradiction_count": len(active_contradictions),
        "active_superseded_records": active_superseded,
        "active_contradictions": active_contradictions,
        "resolution_plan": resolution_plan(
            {
                "active_superseded_records": active_superseded,
                "active_contradictions": active_contradictions,
            }
        ),
    }


def superseded_item(ref: dict[str, str], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = by_id[ref["source"]]
    target = by_id[ref["target"]]
    return {
        **base_item(ref, source, target),
        "target_status": str(target.get("status", "")),
        "recommendation": "mark_target_superseded_or_explain_why_active",
    }


def contradiction_item(ref: dict[str, str], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = by_id[ref["source"]]
    target = by_id[ref["target"]]
    stronger = stronger_record(source, target)
    return {
        **base_item(ref, source, target),
        "both_active": both_active(source, target),
        "stronger_record": stronger,
        "recommendation": "verify_conflict_and_supersede_or_downgrade_weaker_record",
    }


def base_item(ref: dict[str, str], source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": ref["type"],
        "source": ref["source"],
        "target": ref["target"],
        "source_title": source.get("title", ""),
        "target_title": target.get("title", ""),
        "source_trust": trust_status(source)["status"],
        "target_trust": trust_status(target)["status"],
    }
