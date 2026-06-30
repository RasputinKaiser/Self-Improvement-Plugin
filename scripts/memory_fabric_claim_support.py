from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any

from memory_fabric_claim_support_item import claim_item
from memory_fabric_claim_support_parse import audit_claims
from memory_fabric_claim_support_text import dedupe, is_causal_claim


CLAIM_BOUNDARY = (
    "Claim support audits selected memory records; it does not prove the external truth of a claim."
)


def claim_support_audit(
    *,
    claims_json: str = "",
    scope: str = "",
    query: str = "",
    status: str = "active",
    provenance_type: str = "",
    confidence: str = "",
    verify_before_use: str = "",
    limit: int = 3,
    max_nodes: int = 24,
    max_edges: int = 80,
    path: str | Path | None = None,
) -> dict[str, Any]:
    claims = audit_claims(claims_json, query)
    items = [
        claim_item(
            claim,
            scope=scope,
            status=status,
            provenance_type=provenance_type,
            confidence=confidence,
            verify_before_use=verify_before_use,
            limit=limit,
            max_nodes=max_nodes,
            max_edges=max_edges,
            path=path,
        )
        for claim in claims
    ]
    statuses = Counter(item["status"] for item in items)
    return {
        "ok": bool(items) and all(item["status"] == "supported" for item in items),
        "status": audit_status(items),
        "claim_boundary": CLAIM_BOUNDARY,
        "scope": scope or None,
        "query": query or None,
        "source_of_truth": "append-only memory fabric store",
        "claim_count": len(items),
        "status_counts": dict(sorted(statuses.items())),
        "supported_count": statuses.get("supported", 0),
        "needs_verification_count": statuses.get("needs_verification", 0),
        "unsupported_count": statuses.get("unsupported", 0),
        "recommended_next_checks": audit_next_checks(items),
        "claims": items,
    }


def audit_next_checks(items: list[dict[str, Any]]) -> list[str]:
    checks = [check for item in items for check in item["recommended_next_checks"]]
    if not items:
        checks.append("provide_claims_to_audit")
    return dedupe(checks)


def audit_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "no_claims"
    if any(item["status"] == "unsupported" for item in items):
        return "claims_missing_support"
    if any(item["status"] == "needs_verification" for item in items):
        return "claims_need_verification"
    return "claims_supported"
