from __future__ import annotations
from typing import Any


def selected_records(brief: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for tier, items in brief.get("sections", {}).items():
        records.extend(selected_tier_records(tier, items))
    return records


def selected_tier_records(tier: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "tier": tier,
            "title": item.get("title"),
            "trust": item.get("trust", {}),
            "evidence_path": item.get("evidence_path", ""),
            "provenance_type": item.get("provenance_type", ""),
            "score": item.get("score", 0),
        }
        for item in items
    ]
