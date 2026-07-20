from __future__ import annotations
from collections import Counter
from typing import Any

from memory_fabric_contradiction_audit import contradiction_report
from memory_fabric_search_filters import trust_status


CLAIM_BOUNDARY = "Brief readiness guides task handoff; verify source records before acting."


def brief_readiness(
    records: list[dict[str, Any]],
    universe_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    trusts = [trust_status(record)["status"] for record in records]
    conflicts = contradiction_report(records, universe_records)
    return {
        "ok": all([not next_checks(records, trusts, conflicts), conflicts["ok"]]),
        "claim_boundary": CLAIM_BOUNDARY,
        "record_count": len(records),
        "trust_counts": dict(sorted(Counter(trusts).items())),
        "verify_before_use_count": sum(bool(record.get("verify_before_use")) for record in records),
        "active_superseded_count": conflicts["active_superseded_count"],
        "active_contradiction_count": conflicts["active_contradiction_count"],
        "active_superseded_records": conflicts["active_superseded_records"],
        "active_contradictions": conflicts["active_contradictions"],
        "resolution_plan": conflicts["resolution_plan"],
        "recommended_next_checks": next_checks(records, trusts, conflicts),
    }


def next_checks(
    records: list[dict[str, Any]],
    trusts: list[str],
    conflicts: dict[str, Any],
) -> list[str]:
    checks = []
    if conflicts["active_contradiction_count"] or conflicts["active_superseded_count"]:
        checks.append("resolve_conflicts_or_supersede_records")
    if any(record.get("verify_before_use") for record in records):
        checks.append("verify_records_marked_verify_before_use")
    if "context_only" in trusts:
        checks.append("upgrade_context_only_records_before_strong_claims")
    return checks
