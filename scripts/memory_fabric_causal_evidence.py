from __future__ import annotations
from typing import Any


CONTRACT_VERSION = "causal_evidence_ledger.v1"
CLAIM_BOUNDARY = (
    "Causal evidence ledgers identify memory-side evidence needed for a causal claim; "
    "they do not prove external causality."
)


def causal_evidence_ledger(path: dict[str, Any]) -> dict[str, Any]:
    explanation = path.get("explanation", {})
    evidence = explanation.get("evidence_by_node", {})
    nodes = [str(node) for node in path.get("nodes", [])]
    entries = [node_evidence_entry(node, evidence.get(node, {})) for node in nodes]
    missing = [entry["node"] for entry in entries if not entry["evidence_path"]]
    citations = [entry["evidence_path"] for entry in entries if entry["evidence_path"]]
    return {
        "ok": not missing,
        "contract_version": CONTRACT_VERSION,
        "status": "causal_evidence_ready" if not missing else "causal_evidence_needs_sources",
        "required_citation_paths": dedupe(citations),
        "missing_evidence_nodes": missing,
        "entry_count": len(entries),
        "entries": entries,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def node_evidence_entry(node: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "title": str(evidence.get("title", "")),
        "tier": str(evidence.get("tier", "")),
        "trust_status": str(evidence.get("trust_status", "unknown")),
        "evidence_path": str(evidence.get("evidence_path", "")),
        "provenance_type": str(evidence.get("provenance_type", "")),
    }


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
