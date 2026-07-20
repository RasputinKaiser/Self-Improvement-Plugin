from __future__ import annotations
from typing import Any


def isolated_report(graph: dict[str, Any]) -> dict[str, Any]:
    connected = {edge["source"] for edge in graph["edges"]} | {edge["target"] for edge in graph["edges"]}
    isolated = [node for node in graph["nodes"] if node["id"] not in connected]
    node_count = max(1, int(graph["node_count"]))
    return {
        "isolated_node_count": len(isolated),
        "isolated_ratio": round(len(isolated) / node_count, 3),
        "isolated_nodes": isolated,
    }


def warning_report(
    graph: dict[str, Any],
    explicit: dict[str, Any],
    isolated: dict[str, Any],
    max_isolated_ratio: float,
    conflicts: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    warnings = []
    if graph["truncated_edges"]:
        warnings.append({"code": "edges_truncated", "edge_count": graph["edge_count"]})
    if explicit["dangling_reference_count"]:
        warnings.append({"code": "dangling_explicit_references", "count": explicit["dangling_reference_count"]})
    if explicit["outside_selection_reference_count"]:
        warnings.append(outside_warning(explicit))
    if isolated["isolated_ratio"] > max_isolated_ratio:
        warnings.append({"code": "isolated_ratio_high", "ratio": isolated["isolated_ratio"]})
    if conflicts:
        warnings.extend(conflict_warnings(conflicts))
    return warnings


def outside_warning(explicit: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": "explicit_references_outside_selection",
        "count": explicit["outside_selection_reference_count"],
    }


def conflict_warnings(conflicts: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    if conflicts["active_superseded_count"]:
        warnings.append({"code": "active_superseded_records", "count": conflicts["active_superseded_count"]})
    if conflicts["active_contradiction_count"]:
        warnings.append({"code": "active_contradictions", "count": conflicts["active_contradiction_count"]})
    return warnings
