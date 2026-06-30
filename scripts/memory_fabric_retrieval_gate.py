from __future__ import annotations
from collections import Counter
from typing import Any


CLAIM_BOUNDARY = (
    "Retrieval gates summarize selected memory readiness; they do not prove the selected claims."
)

READY_TRUST = {"ready"}


def retrieval_gate(records: list[dict[str, Any]]) -> dict[str, Any]:
    trust_counts = Counter(trust_status(record) for record in records)
    match_kind_counts = Counter(match_kind(record) for record in records)
    non_ready = non_ready_records(records)
    semantic_only = semantic_only_records(records)
    semantic_only_non_ready = non_ready_records(semantic_only)
    checks = next_checks(records, non_ready, semantic_only, semantic_only_non_ready)
    return {
        "ok": not checks,
        "strong_claim_ready": bool(records) and not non_ready,
        "policy": "semantic_expansion_must_not_override_trust",
        "record_count": len(records),
        "trust_counts": dict(sorted(trust_counts.items())),
        "match_kind_counts": dict(sorted(match_kind_counts.items())),
        "non_ready_count": len(non_ready),
        "semantic_only_count": len(semantic_only),
        "semantic_only_non_ready_count": len(semantic_only_non_ready),
        "semantic_only_non_ready_ids": record_ids(semantic_only_non_ready),
        "recommended_next_checks": checks,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def non_ready_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if trust_status(record) not in READY_TRUST]


def semantic_only_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if match_kind(record) == "semantic_only"]


def next_checks(
    records: list[dict[str, Any]],
    non_ready: list[dict[str, Any]],
    semantic_only: list[dict[str, Any]],
    semantic_only_non_ready: list[dict[str, Any]],
) -> list[str]:
    checks = []
    if not records:
        checks.append("widen_query_or_record_source_backed_memory")
    if non_ready:
        checks.append("filter_to_ready_records_before_strong_claims")
    if semantic_only_non_ready:
        checks.append("verify_semantic_only_non_ready_matches_before_use")
    return checks


def record_ids(records: list[dict[str, Any]]) -> list[str]:
    return [str(record.get("id", "")) for record in records]


def trust_status(record: dict[str, Any]) -> str:
    trust = record.get("trust", {})
    if isinstance(trust, dict):
        return str(trust.get("status", "unknown"))
    return "unknown"


def match_kind(record: dict[str, Any]) -> str:
    retrieval = record.get("retrieval", {})
    if isinstance(retrieval, dict):
        return str(retrieval.get("match_kind", "unknown"))
    return "unknown"
