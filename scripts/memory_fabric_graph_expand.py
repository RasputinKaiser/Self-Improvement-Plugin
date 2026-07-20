from __future__ import annotations
from memory_fabric_graph_edges import EDGE_TYPE_PRIORITY


def expansion_plan(graph: dict, max_seed_edges: int = 5) -> dict:
    if not graph.get("truncated_edges"):
        return {"status": "not_needed", "reason": "edges_not_truncated", "seed_edges": [], "seed_nodes": []}
    seeds = seed_edges(graph, max_seed_edges)
    nodes = seed_nodes(graph, seeds)
    return {
        "status": "expand_from_ranked_edges",
        "reason": "edges_truncated",
        "claim_boundary": "Expansion hints are not proof.",
        "seed_edges": seeds,
        "seed_nodes": nodes,
        "follow_up": follow_up(graph, nodes),
    }


def seed_edges(graph: dict, limit: int) -> list[dict]:
    ranked = sorted(graph.get("edges", []), key=edge_key)
    return [edge_summary(edge) for edge in ranked[: max(1, int(limit))]]


def seed_nodes(graph: dict, edges: list[dict]) -> list[dict]:
    ids = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
    nodes = [node for node in graph.get("nodes", []) if node.get("id") in ids]
    return [node_summary(node) for node in sorted(nodes, key=lambda node: str(node.get("id", "")))]


def follow_up(graph: dict, nodes: list[dict]) -> list[dict]:
    base = {
        "scope": graph.get("scope", ""),
        "query": graph.get("query", ""),
        "status": graph.get("status", "active"),
        "max_nodes": graph.get("limits", {}).get("max_nodes", 24),
        "max_edges": graph.get("limits", {}).get("max_edges", 80) * 2,
    }
    steps = [{"operation": "memory_fabric_graph", "args": base}]
    steps.extend(search_step(node, graph.get("scope", "")) for node in nodes[:3])
    return steps


def search_step(node: dict, scope: str) -> dict:
    return {
        "operation": "memory_fabric_search",
        "args": {"query": node["title"], "scope": scope, "limit": 5},
    }


def edge_key(edge: dict) -> tuple[int, int, str, str, str]:
    return (
        EDGE_TYPE_PRIORITY.get(str(edge.get("type", "")), 9),
        -int(edge.get("weight", 0)),
        str(edge.get("type", "")),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
    )


def edge_summary(edge: dict) -> dict:
    return {key: edge.get(key) for key in ["source", "target", "type", "weight", "reason"]}


def node_summary(node: dict) -> dict:
    return {key: node.get(key) for key in ["id", "tier", "title", "status", "confidence"]}
