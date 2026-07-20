from __future__ import annotations
from typing import Any

from memory_fabric_graph_explicit import make_edge


def pair_edges(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    source, target = sorted([str(left.get("id", "")), str(right.get("id", ""))])
    if source == target:
        return []
    edges = []
    edges.extend(scope_edges(source, target, left, right))
    edges.extend(tag_edges(source, target, left, right))
    edges.extend(evidence_edges(source, target, left, right))
    return edges


def scope_edges(
    source: str,
    target: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> list[dict[str, Any]]:
    scope = str(left.get("scope", ""))
    if not scope or scope == "global" or scope != str(right.get("scope", "")):
        return []
    return [make_edge(source, target, "same_scope", 2, "same_scope", scope)]


def tag_edges(
    source: str,
    target: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> list[dict[str, Any]]:
    shared = sorted(set(left.get("tags", [])) & set(right.get("tags", [])))
    if not shared:
        return []
    return [make_edge(source, target, "shares_tag", 1 + len(shared), "shared_tags", ",".join(shared[:5]))]


def evidence_edges(
    source: str,
    target: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence = str(left.get("provenance", {}).get("evidence_path", ""))
    right_evidence = str(right.get("provenance", {}).get("evidence_path", ""))
    if not evidence or evidence != right_evidence:
        return []
    return [make_edge(source, target, "shares_evidence", 4, "same_evidence_path", evidence)]
