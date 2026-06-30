from __future__ import annotations
from typing import Any

from memory_fabric_task_cue_match import matching_record_ids
from memory_fabric_task_cue_pricing import pricing_gate


def cue_ledger(profile: dict[str, Any], query_terms: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    groups = profile.get("cue_groups", [])
    if not groups:
        return empty_ledger()
    rows = [cue_group_row(group, query_terms, records) for group in groups]
    missing = [row for row in rows if row["status"] == "missing"]
    return {
        "ok": not missing,
        "status": "cue_ledger_complete" if not missing else "cue_ledger_incomplete",
        "covered_count": len(rows) - len(missing),
        "missing_count": len(missing),
        "groups": rows,
        "missing_next_checks": [row["next_check"] for row in missing if row.get("next_check")],
        "pricing_gate": pricing_gate(rows),
        "claim_boundary": "Cue coverage is a memory/query routing aid; it does not prove identity, match, or price.",
    }


def empty_ledger() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "cue_ledger_not_applicable",
        "covered_count": 0,
        "missing_count": 0,
        "groups": [],
        "missing_next_checks": [],
        "pricing_gate": {"ok": True, "status": "not_applicable", "blocked_by": []},
        "claim_boundary": "No task-specific cue ledger applies to this profile.",
    }


def cue_group_row(group: dict[str, Any], query_terms: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    keywords = set(group.get("keywords", []))
    query_matches = sorted(set(query_terms) & keywords)
    record_matches = matching_record_ids(records, keywords)
    present = bool(query_matches or record_matches)
    return {
        "id": group["id"],
        "label": group.get("label", group["id"]),
        "status": "covered" if present else "missing",
        "matched_terms": query_matches,
        "selected_record_ids": record_matches,
        "next_check": group.get("next_check", ""),
    }
