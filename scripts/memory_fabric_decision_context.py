from __future__ import annotations
from collections import Counter
from typing import Any


DECISION_EDGE_TYPES = {
    "alternative_to",
    "chosen_over",
    "decision_for",
    "rejected_for",
    "tradeoff_with",
}

CLAIM_BOUNDARY = (
    "Decision edges are explicit memory markers for reasoning context; "
    "they do not prove the selected option is correct."
)


def decision_context(edges: list[dict[str, Any]]) -> dict[str, Any]:
    decision_edges = [edge for edge in edges if str(edge.get("type", "")) in DECISION_EDGE_TYPES]
    counts = Counter(str(edge.get("type", "")) for edge in decision_edges)
    return {
        "ok": True,
        "status": "decision_context_present" if decision_edges else "no_decision_context",
        "edge_count": len(decision_edges),
        "edge_type_counts": dict(sorted(counts.items())),
        "has_selected_option": bool(counts.get("chosen_over") or counts.get("decision_for")),
        "has_alternatives": bool(counts.get("alternative_to") or counts.get("tradeoff_with")),
        "recommended_next_checks": recommended_next_checks(counts),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def recommended_next_checks(counts: Counter[str]) -> list[str]:
    checks: list[str] = []
    if counts and not (counts.get("chosen_over") or counts.get("decision_for")):
        checks.append("record_selected_decision_or_current_default")
    if counts and not (counts.get("alternative_to") or counts.get("tradeoff_with")):
        checks.append("record_considered_alternatives_or_tradeoffs")
    return checks
