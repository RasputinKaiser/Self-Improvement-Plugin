from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_graph_explicit import explicit_references
from memory_fabric_jsonl import load_records
from memory_fabric_search_filters import apply_record_filters, provenance_value
from memory_fabric_search_filters import confidence_value, verify_value
from memory_fabric_schema import normalize_status


def scoped_ids(
    scope: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    path: str | Path | None,
) -> set[str]:
    records = apply_record_filters(
        load_records(path),
        scope=scope,
        status_filter=normalize_status(status) if status.strip() else "",
        provenance_filter=provenance_value(provenance_type),
        confidence_filter=confidence_value(confidence),
        verify_filter=verify_value(verify_before_use),
    )
    return {str(record.get("id", "")) for record in records if record.get("id")}


def reference_report(records: list[dict[str, Any]], all_ids: set[str]) -> dict[str, Any]:
    selected_ids = {str(record.get("id", "")) for record in records if record.get("id")}
    refs = [ref for record in records for ref in explicit_references(record)]
    dangling = [ref for ref in refs if ref["target"] not in all_ids]
    outside = outside_selection(refs, selected_ids, all_ids)
    return {
        "explicit_reference_count": len(refs),
        "dangling_reference_count": len(dangling),
        "outside_selection_reference_count": len(outside),
        "dangling_references": sorted(dangling, key=ref_key),
        "outside_selection_references": sorted(outside, key=ref_key),
    }


def outside_selection(
    refs: list[dict[str, str]],
    selected_ids: set[str],
    all_ids: set[str],
) -> list[dict[str, str]]:
    return [ref for ref in refs if ref["target"] in all_ids and ref["target"] not in selected_ids]


def ref_key(ref: dict[str, str]) -> tuple[str, str, str]:
    return (ref["type"], ref["source"], ref["target"])
