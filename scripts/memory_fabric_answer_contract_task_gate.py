from __future__ import annotations
from typing import Any


def task_gate_summary(brief: dict[str, Any]) -> dict[str, Any]:
    pricing = pricing_gate(brief)
    if not pricing:
        return no_task_gate()
    blocked_by = pricing.get("blocked_by", [])
    return {
        "status": pricing.get("status", ""),
        "ok": bool(pricing.get("ok", False)),
        "blocked_by": blocked_by,
        "blocked_actions": blocked_actions(blocked_by),
        "claim_boundary": "Task gates constrain answer actions; they do not prove the task result.",
    }


def pricing_gate(brief: dict[str, Any]) -> dict[str, Any]:
    task_profile = brief.get("task_profile", {})
    ledger = task_profile.get("cue_ledger", {}) if isinstance(task_profile, dict) else {}
    return ledger.get("pricing_gate", {}) if isinstance(ledger, dict) else {}


def no_task_gate() -> dict[str, Any]:
    return {
        "status": "no_task_gate",
        "ok": True,
        "blocked_by": [],
        "blocked_actions": [],
    }


def blocked_actions(blocked_by: list[str]) -> list[str]:
    if not blocked_by:
        return []
    return ["do_not_price_before_candidate_match_and_visual_comparison"]
