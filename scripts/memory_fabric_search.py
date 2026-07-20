from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_jsonl import load_records, store_path
from memory_fabric_search_filters import confidence_value, created_at_timestamp, provenance_value
from memory_fabric_search_filters import record_confidence, record_matches, trust_status
from memory_fabric_search_filters import status_value, verify_value
from memory_fabric_schema import normalize_tier, runtime_contract
from memory_fabric_retrieval_gate import retrieval_gate
from memory_fabric_semantic import match_explanation, query_profile, query_terms, match_score as semantic_match_score


RANKING_POLICY = "weighted_fields_semantic_expansion_then_recency"


def match_score(record: dict[str, Any], query: str) -> int:
    profile = query_profile(query)
    fields = searchable_fields(record)
    return semantic_match_score(record, profile, fields)


weighted_match_score = match_score


def searchable_fields(record: dict[str, Any]) -> list[tuple[str, int]]:
    value = record.get
    return [
        (str(value("title", "")).lower(), 8),
        (" ".join(str(tag) for tag in value("tags", [])).lower(), 6),
        (str(value("scope", "")).lower(), 4),
        (str(value("body", "")).lower(), 2),
    ]


def search_records(
    *,
    query: str = "",
    tier: str = "",
    scope: str = "",
    status: str = "",
    provenance_type: str = "",
    confidence: str = "",
    verify_before_use: str = "",
    limit: int = 10,
    path: str | Path | None = None,
) -> dict[str, Any]:
    tier_filter = normalize_tier(tier) if tier else ""
    status_filter = status_value(status)
    provenance_filter = provenance_value(provenance_type)
    confidence_filter = confidence_value(confidence)
    verify_filter = verify_value(verify_before_use)
    semantic_profile = query_profile(query)
    records = []
    for record in load_records(path):
        fields = searchable_fields(record)
        score = semantic_match_score(record, semantic_profile, fields)
        if not record_matches(
            record,
            score=score,
            tier_filter=tier_filter,
            scope=scope,
            status_filter=status_filter,
            provenance_filter=provenance_filter,
            confidence_filter=confidence_filter,
            verify_filter=verify_filter,
        ):
            continue
        retrieval = match_explanation(record, semantic_profile, fields)
        records.append(
            {
                **record,
                "confidence": record_confidence(record),
                "trust": trust_status(record),
                "retrieval": retrieval,
                "_score": score,
            }
        )
    records.sort(key=lambda item: (-int(item.get("_score", 0)), -created_at_timestamp(item), str(item.get("id", ""))))
    selected = records[: max(1, int(limit))]
    return {
        "ok": True,
        "query": query,
        "tier": tier_filter or None,
        "scope": scope or None,
        "status": status_filter or None,
        "provenance_type": provenance_filter or None,
        "confidence": confidence_filter or None,
        "verify_before_use": verify_filter,
        "count": len(records),
        "ranking_policy": RANKING_POLICY,
        "runtime_contract": runtime_contract("search", ranking_policy=RANKING_POLICY),
        "semantic_query": semantic_profile,
        "trust_policy": "provenance_confidence_status_verify_gate",
        "retrieval_gate": retrieval_gate(selected),
        "records": selected,
        "store": str(store_path(path)),
    }
