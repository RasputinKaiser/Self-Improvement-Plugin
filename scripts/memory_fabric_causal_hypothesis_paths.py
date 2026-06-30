from __future__ import annotations
from typing import Any

from memory_fabric_causal_audit import READY_STATUS


def causal_path_hypotheses(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {str(node.get("id", "")): node for node in graph.get("nodes", [])}
    hypotheses = []
    for path in graph.get("reasoning_paths", []):
        explanation = path.get("explanation", {})
        if not explanation.get("causal_edge"):
            continue
        source, target = node_pair(path.get("nodes", []))
        hypotheses.append(
            {
                "source": source,
                "target": target,
                "source_title": nodes.get(source, {}).get("title", ""),
                "target_title": nodes.get(target, {}).get("title", ""),
                "edges": path.get("edges", []),
                "status": explanation.get("status", ""),
                "node_trusts": explanation.get("node_trusts", []),
                "trust_reasons": explanation.get("trust_reasons", {}),
                "evidence_paths": explanation.get("evidence_paths", []),
                "required_citation_paths": explanation.get("evidence_paths", []),
                "evidence_by_node": explanation.get("evidence_by_node", {}),
                "score": path.get("score", 0),
                "claim_boundary": explanation.get("claim_boundary", ""),
            }
        )
    return sorted(hypotheses, key=hypothesis_rank)


def node_pair(nodes: list[Any]) -> tuple[str, str]:
    values = [str(item) for item in nodes]
    return (values + ["", ""])[:2]


def hypothesis_rank(item: dict[str, Any]) -> tuple[int, int, str, str]:
    ready_rank = 0 if item.get("status") == READY_STATUS else 1
    return (ready_rank, -int(item.get("score", 0)), str(item.get("target", "")), str(item.get("source", "")))
