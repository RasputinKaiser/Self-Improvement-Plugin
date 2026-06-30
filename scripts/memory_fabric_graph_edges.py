from __future__ import annotations
from collections import Counter
from itertools import combinations
from typing import Any

from memory_fabric_graph_explicit import explicit_edges
from memory_fabric_graph_pair import pair_edges


EDGE_TYPE_PRIORITY = {
    "alternative_to": 0,
    "blocked_by": 0,
    "blocks": 0,
    "caused_by": 0,
    "chosen_over": 0,
    "contradicts": 0,
    "decision_for": 0,
    "depends_on": 0,
    "evidence_for": 0,
    "fixes": 0,
    "proved_by": 0,
    "rejected_for": 0,
    "same_pattern_as": 0,
    "supersedes": 0,
    "tradeoff_with": 0,
    "shares_evidence": 1,
    "shares_tag": 2,
    "same_scope": 3,
}


def build_edges(records: list[dict[str, Any]], max_edges: int) -> tuple[list[dict[str, Any]], bool]:
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    id_set = {str(record.get("id", "")) for record in records}
    for record in records:
        merge_edges(edges, explicit_edges(record, id_set))
    for left, right in combinations(records, 2):
        merge_edges(edges, pair_edges(left, right))
    ordered = sorted(edges.values(), key=edge_sort_key)
    limit = max(1, int(max_edges))
    return ordered[:limit], len(ordered) > limit


def merge_edges(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> None:
    for candidate in candidates:
        key = edge_key(candidate)
        current = edges.get(key)
        if not current or int(candidate["weight"]) > int(current["weight"]):
            edges[key] = candidate


def edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    return (str(edge.get("source", "")), str(edge.get("target", "")), str(edge.get("type", "")))


def edge_type_counts(edges: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(edge["type"] for edge in edges).items()))


def edge_sort_key(edge: dict[str, Any]) -> tuple[int, int, str, str, str]:
    return (
        EDGE_TYPE_PRIORITY.get(str(edge.get("type", "")), 9),
        -int(edge.get("weight", 0)),
        str(edge.get("type", "")),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
    )
