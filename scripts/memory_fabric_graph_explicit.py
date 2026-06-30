from __future__ import annotations
import re
from typing import Any


EXPLICIT_EDGE_LABELS = {
    "alternative to": "alternative_to",
    "blocks": "blocks",
    "blocked by": "blocked_by",
    "caused by": "caused_by",
    "chosen over": "chosen_over",
    "contradicts": "contradicts",
    "decision for": "decision_for",
    "depends on": "depends_on",
    "evidence for": "evidence_for",
    "fixes": "fixes",
    "proved by": "proved_by",
    "rejected for": "rejected_for",
    "same pattern as": "same_pattern_as",
    "supersedes": "supersedes",
    "tradeoff with": "tradeoff_with",
}

EXPLICIT_PATTERN = re.compile(
    r"\b("
    r"alternative to|blocked by|caused by|chosen over|decision for|"
    r"same pattern as|tradeoff with|rejected for|proved by|blocks|"
    r"contradicts|depends on|evidence for|fixes|supersedes"
    r")\s*:\s*"
    r"((?:mem_[0-9a-f]{16})(?:\s*,\s*mem_[0-9a-f]{16})*)",
    re.IGNORECASE,
)


def explicit_edges(record: dict[str, Any], id_set: set[str]) -> list[dict[str, Any]]:
    edges = []
    for reference in explicit_references(record):
        edges.extend(marker_edges(reference["source"], reference["type"], reference["target"], id_set))
    return edges


def explicit_references(record: dict[str, Any]) -> list[dict[str, str]]:
    source = str(record.get("id", ""))
    body = str(record.get("body", ""))
    references = []
    for match in EXPLICIT_PATTERN.finditer(body):
        edge_type = EXPLICIT_EDGE_LABELS[match.group(1).lower()]
        references.extend(reference_items(source, edge_type, match.group(2)))
    return references


def reference_items(source: str, edge_type: str, value: str) -> list[dict[str, str]]:
    return [
        {"source": source, "target": target, "type": edge_type}
        for target in referenced_ids(value)
        if target != source
    ]


def marker_edges(source: str, edge_type: str, value: str, id_set: set[str]) -> list[dict[str, Any]]:
    return [
        make_edge(source, target, edge_type, 10, "explicit_marker", "")
        for target in referenced_ids(value)
        if target in id_set and target != source
    ]


def referenced_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def make_edge(
    source: str,
    target: str,
    edge_type: str,
    weight: int,
    reason: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "type": edge_type,
        "weight": weight,
        "reason": reason,
        "evidence": evidence,
    }
