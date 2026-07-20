from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_evidence_audit import evidence_audit
from memory_fabric_evidence_repair_actions import repair_action


def evidence_repair(
    path: str | Path | None = None,
    scope: str = "",
    receipt_path: str = "",
    allowed_root: str = "",
    create_indexes: bool = False,
    sample_limit: int = 20,
) -> dict[str, Any]:
    audit = evidence_audit(path=path, scope=scope, strict=False, sample_limit=sample_limit)
    receipt = Path(receipt_path).expanduser() if receipt_path else None
    root = Path(allowed_root).expanduser() if allowed_root else None
    actions = [
        repair_action(warning, receipt=receipt, allowed_root=root, create_indexes=create_indexes)
        for warning in audit["warnings"]
    ]
    created = [action for action in actions if action["action"] == "created_receipt_index"]
    blocked = [action for action in actions if action["action"].startswith("blocked_")]
    return {
        "ok": not blocked,
        "status": repair_status(actions, created, blocked),
        "store": audit["store"],
        "scope": scope,
        "audit_status": audit["status"],
        "warning_count": audit["warning_count"],
        "action_count": len(actions),
        "created_count": len(created),
        "blocked_count": len(blocked),
        "actions": actions[:sample_limit],
        "memory_record_suggestion": memory_record_suggestion(receipt),
        "claim_boundary": "Creates receipt indexes only; does not rewrite memory records.",
    }


def memory_record_suggestion(receipt: Path | None) -> dict[str, str]:
    evidence = str(receipt) if receipt else "<receipt path>"
    return {
        "tier": "learning",
        "title": "Repair stale evidence paths with receipt indexes",
        "provenance_type": "verified_command",
        "evidence_path": evidence,
    }


def repair_status(
    actions: list[dict[str, Any]],
    created: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> str:
    if blocked:
        return "evidence_repair_blocked"
    if created:
        return "evidence_repair_indexes_created"
    if actions:
        return "evidence_repair_plan"
    return "evidence_repair_not_needed"
