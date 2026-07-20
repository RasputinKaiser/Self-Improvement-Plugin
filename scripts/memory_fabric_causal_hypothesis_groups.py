from __future__ import annotations
from typing import Any

from memory_fabric_causal_audit import READY_STATUS


def target_groups(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for hypothesis in hypotheses:
        grouped.setdefault(hypothesis["target"], []).append(hypothesis)
    return [
        {
            "target": target,
            "target_title": items[0].get("target_title", ""),
            "hypothesis_count": len(items),
            "ready_count": ready_count(items),
            "needs_verification_count": needs_verification_count(items),
            "status": group_status(items),
            "hypotheses": items,
        }
        for target, items in sorted(grouped.items())
    ]


def ready_count(items: list[dict[str, Any]]) -> int:
    return len([item for item in items if item["status"] == READY_STATUS])


def needs_verification_count(items: list[dict[str, Any]]) -> int:
    return len([item for item in items if item["status"] != READY_STATUS])


def group_status(items: list[dict[str, Any]]) -> str:
    if len(items) > 1:
        return "competing_hypotheses"
    if items and items[0]["status"] == READY_STATUS:
        return "single_ready_hypothesis"
    return "hypothesis_needs_verification"
