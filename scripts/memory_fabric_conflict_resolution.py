from __future__ import annotations
from typing import Any


CLAIM_BOUNDARY = "Resolution plans are append-only guidance; they do not rewrite memory records."


def resolution_plan(conflicts: dict[str, Any]) -> dict[str, Any]:
    actions = [
        *[superseded_action(item) for item in conflicts["active_superseded_records"]],
        *[contradiction_action(item) for item in conflicts["active_contradictions"]],
    ]
    return {
        "ok": not actions,
        "status": "no_conflicts" if not actions else "resolution_actions_needed",
        "action_count": len(actions),
        "actions": actions,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def superseded_action(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "mark_superseded",
        "record": item["target"],
        "because_of": item["source"],
        "reason": "active_record_is_explicitly_superseded",
        "suggested_append_only_note": f"Superseded by: {item['source']}",
        "proof_needed": "verify_superseding_record_evidence_before_status_change",
    }


def contradiction_action(item: dict[str, Any]) -> dict[str, Any]:
    weaker = weaker_record(item)
    action_type = "supersede_weaker_record" if item.get("stronger_record") else "manual_review"
    return {
        "type": action_type,
        "record": weaker,
        "because_of": item.get("stronger_record", ""),
        "reason": "active_records_explicitly_contradict",
        "suggested_append_only_note": suggested_note(item, weaker),
        "proof_needed": "verify_conflict_against_source_evidence_before_status_change",
        "source_trust": item["source_trust"],
        "target_trust": item["target_trust"],
    }


def weaker_record(item: dict[str, Any]) -> str:
    stronger = item.get("stronger_record")
    if not stronger:
        return ""
    return item["target"] if stronger == item["source"] else item["source"]


def suggested_note(item: dict[str, Any], weaker: str) -> str:
    if not weaker:
        return "Contradiction requires manual source review."
    return f"Superseded after contradiction review by: {item['stronger_record']}"
