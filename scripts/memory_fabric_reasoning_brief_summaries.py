from __future__ import annotations
from typing import Any


def graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": graph.get("ok"),
        "status": graph.get("status"),
        "node_count": graph.get("node_count", 0),
        "edge_count": graph.get("edge_count", 0),
        "edge_type_counts": graph.get("edge_type_counts", {}),
        "decision_context": compact_decision_context(graph.get("decision_context", {})),
        "path_use_ledger": compact_path_use_ledger(graph.get("path_use_ledger", {})),
        "warning_count": len(graph.get("warnings", [])),
        "warnings": graph.get("warnings", []),
        "active_superseded_count": graph.get("active_superseded_count", 0),
        "active_contradiction_count": graph.get("active_contradiction_count", 0),
        "resolution_plan": graph.get("resolution_plan", {}),
        "claim_boundary": graph.get("claim_boundary", ""),
    }


def compact_path_use_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": ledger.get("ok", True),
        "status": ledger.get("status", "no_reasoning_paths"),
        "contract_version": ledger.get("contract_version", ""),
        "path_count": ledger.get("path_count", 0),
        "blocking_path_count": ledger.get("blocking_path_count", 0),
        "ready_citation_path_count": ledger.get("ready_citation_path_count", 0),
        "usable_as_counts": ledger.get("usable_as_counts", {}),
        "proof_status_counts": ledger.get("proof_status_counts", {}),
        "recommended_next_checks": ledger.get("recommended_next_checks", []),
        "claim_boundary": ledger.get("claim_boundary", ""),
    }


def compact_decision_context(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": decision.get("ok", True),
        "status": decision.get("status", "no_decision_context"),
        "edge_count": decision.get("edge_count", 0),
        "edge_type_counts": decision.get("edge_type_counts", {}),
        "has_selected_option": decision.get("has_selected_option", False),
        "has_alternatives": decision.get("has_alternatives", False),
        "recommended_next_checks": decision.get("recommended_next_checks", []),
        "claim_boundary": decision.get("claim_boundary", ""),
    }


def hypothesis_summary(hypotheses: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": hypotheses.get("ok"),
        "status": hypotheses.get("status"),
        "hypothesis_count": hypotheses.get("hypothesis_count", 0),
        "ready_hypothesis_count": hypotheses.get("ready_hypothesis_count", 0),
        "needs_verification_count": hypotheses.get("needs_verification_count", 0),
        "competing_target_count": hypotheses.get("competing_target_count", 0),
        "recommended_next_checks": hypotheses.get("recommended_next_checks", []),
        "target_groups": compact_target_groups(hypotheses.get("target_groups", [])),
        "claim_boundary": hypotheses.get("claim_boundary", ""),
    }


def causal_evidence_summary(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": audit.get("ok"),
        "status": audit.get("status"),
        "evidence_contract_version": audit.get("evidence_contract_version", ""),
        "causal_path_count": audit.get("causal_path_count", 0),
        "ready_causal_path_count": audit.get("ready_causal_path_count", 0),
        "needs_verification_count": audit.get("needs_verification_count", 0),
        "missing_evidence_node_count": audit.get("missing_evidence_node_count", 0),
        "required_citation_paths": audit.get("required_citation_paths", []),
        "recommended_next_checks": audit.get("recommended_next_checks", []),
        "paths": compact_causal_paths(audit.get("causal_paths", [])),
        "claim_boundary": audit.get("claim_boundary", ""),
    }


def compact_causal_paths(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "nodes": item.get("nodes", []),
            "edges": item.get("edges", []),
            "status": item.get("status", ""),
            "required_citation_paths": item.get("required_citation_paths", []),
            "missing_evidence_nodes": item.get("missing_evidence_nodes", []),
            "evidence_status": item.get("evidence_ledger", {}).get("status", ""),
        }
        for item in paths
    ]


def compact_target_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "target": group.get("target"),
            "target_title": group.get("target_title", ""),
            "hypothesis_count": group.get("hypothesis_count", 0),
            "ready_count": group.get("ready_count", 0),
            "needs_verification_count": group.get("needs_verification_count", 0),
            "status": group.get("status", ""),
        }
        for group in groups
    ]


def claim_support_summary(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": claims.get("ok"),
        "status": claims.get("status"),
        "claim_count": claims.get("claim_count", 0),
        "status_counts": claims.get("status_counts", {}),
        "recommended_next_checks": claims.get("recommended_next_checks", []),
        "claims": compact_claims(claims.get("claims", [])),
        "claim_boundary": claims.get("claim_boundary", ""),
    }


def compact_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "claim": item.get("claim", ""),
            "status": item.get("status", ""),
            "claim_kind": item.get("claim_kind", ""),
            "support_record_count": item.get("support_record_count", 0),
            "causal": compact_claim_causal(item.get("causal", {})),
            "recommended_next_checks": item.get("recommended_next_checks", []),
        }
        for item in claims
    ]


def compact_claim_causal(causal: dict[str, Any]) -> dict[str, Any]:
    if not causal.get("required"):
        return {
            "required": False,
            "status": causal.get("status", "not_causal_claim"),
        }
    return {
        "required": True,
        "ok": causal.get("ok"),
        "status": causal.get("status", ""),
        "causal_path_count": causal.get("causal_path_count", 0),
        "needs_verification_count": causal.get("needs_verification_count", 0),
        "missing_evidence_node_count": causal.get("missing_evidence_node_count", 0),
        "required_citation_paths": causal.get("required_citation_paths", []),
        "recommended_next_checks": causal.get("recommended_next_checks", []),
        "claim_boundary": causal.get("claim_boundary", ""),
    }
