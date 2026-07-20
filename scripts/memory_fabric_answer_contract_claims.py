from __future__ import annotations
from typing import Any


def claim_buckets(
    claims: list[dict[str, Any]],
    answer_policy: dict[str, Any],
    checks: list[str],
    blocked_actions: list[str],
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "allowed_claims": [],
        "unverified_claims": [],
        "blocked_claims": [],
    }
    for item in claims:
        if item.get("status") != "supported":
            buckets["blocked_claims"].append(blocked_claim(item))
        elif checks or blocked_actions or not answer_policy.get("ok"):
            buckets["unverified_claims"].append(unverified_claim(item, answer_policy, checks, blocked_actions))
        else:
            buckets["allowed_claims"].append(claim_row(item))
    return buckets


def unverified_claim(
    item: dict[str, Any],
    answer_policy: dict[str, Any],
    checks: list[str],
    blocked_actions: list[str],
) -> dict[str, Any]:
    reasons = dedupe([*checks, *blocked_actions, *answer_policy.get("global_verify_reasons", [])])
    return {
        **claim_row(item),
        "reasons": reasons or item.get("recommended_next_checks", []),
    }


def blocked_claim(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **claim_row(item),
        "reasons": item.get("recommended_next_checks", []),
    }


def claim_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim": item.get("claim", ""),
        "claim_kind": item.get("claim_kind", ""),
        "status": item.get("status", ""),
        "support_record_ids": [record.get("id", "") for record in item.get("selected_records", [])],
        "required_evidence_paths": dedupe(
            [record.get("evidence_path", "") for record in item.get("selected_records", [])]
        ),
    }


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
