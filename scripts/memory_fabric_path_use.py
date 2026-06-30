from __future__ import annotations
from collections import Counter
from typing import Any


CONTRACT_VERSION = "path_use_ledger.v1"
CLAIM_BOUNDARY = (
    "Path-use ledger classifies memory graph paths for answer planning; "
    "it is not external proof."
)


def path_use_ledger(paths: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [path_use_entry(path) for path in paths]
    blocking = [entry for entry in entries if entry["blocks_answer"]]
    citation_ready = [entry for entry in entries if entry["citation_allowed"]]
    return {
        "ok": not blocking,
        "status": ledger_status(entries, blocking),
        "contract_version": CONTRACT_VERSION,
        "path_count": len(entries),
        "blocking_path_count": len(blocking),
        "ready_citation_path_count": len(citation_ready),
        "usable_as_counts": count_field(entries, "usable_as"),
        "proof_status_counts": count_field(entries, "proof_status"),
        "recommended_next_checks": ledger_checks(blocking),
        "entries": entries,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def path_use_entry(path: dict[str, Any]) -> dict[str, Any]:
    policy = path.get("explanation", {}).get("path_use", {})
    return {
        "nodes": path.get("nodes", []),
        "edges": path.get("edges", []),
        "status": policy.get("status", ""),
        "usable_as": policy.get("usable_as", ""),
        "proof_status": policy.get("proof_status", ""),
        "citation_allowed": bool(policy.get("citation_allowed")),
        "blocks_answer": bool(policy.get("blocks_answer")),
        "recommended_next_checks": policy.get("recommended_next_checks", []),
        "claim_boundary": policy.get("claim_boundary", ""),
    }


def ledger_status(entries: list[dict[str, Any]], blocking: list[dict[str, Any]]) -> str:
    if not entries:
        return "no_reasoning_paths"
    if blocking:
        return "path_use_has_blockers"
    return "path_use_ready"


def ledger_checks(blocking: list[dict[str, Any]]) -> list[str]:
    checks = [
        check
        for entry in blocking
        for check in entry.get("recommended_next_checks", [])
    ]
    return list(dict.fromkeys(checks))


def count_field(entries: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(entry.get(field, "")) for entry in entries).items()))
