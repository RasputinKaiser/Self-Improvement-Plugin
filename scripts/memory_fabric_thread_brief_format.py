from __future__ import annotations
from typing import Any

from memory_fabric_search import query_terms, searchable_fields, weighted_match_score
from memory_fabric_search_filters import created_at_timestamp, record_confidence, trust_status
from memory_fabric_semantic import match_explanation, query_profile


def section_records(
    items: list[tuple[int, dict[str, Any]]],
    per_tier: int,
    max_body_chars: int,
    query_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: (-item[0], -created_at_timestamp(item[1]), str(item[1].get("id", ""))))
    return [
        brief_record(record, score, max_body_chars, query_terms or [])
        for score, record in ordered[: max(1, int(per_tier))]
    ]


def brief_record(record: dict[str, Any], score: int, max_body_chars: int, query_terms: list[str]) -> dict[str, Any]:
    provenance = record.get("provenance", {})
    retrieval = match_explanation(record, query_profile(query_terms), searchable_fields(record))
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "body": truncate(str(record.get("body", "")), max_body_chars),
        "status": record.get("status"),
        "confidence": record_confidence(record),
        "verify_before_use": record.get("verify_before_use"),
        "trust": trust_status(record),
        "created_at": record.get("created_at"),
        "provenance_type": provenance.get("type"),
        "evidence_path": provenance.get("evidence_path", ""),
        "retrieval": retrieval,
        "score": score,
    }


def terms(query: str) -> list[str]:
    return query_terms(query)


def match_score(record: dict[str, Any], query_terms: list[str]) -> int:
    return weighted_match_score(record, query_terms)


def truncate(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def trim_brief(brief: dict[str, Any], max_total_chars: int) -> bool:
    total = sum(len(record["body"]) for records in brief["sections"].values() for record in records)
    if total <= max_total_chars:
        return False
    for records in brief["sections"].values():
        for record in records:
            record["body"] = truncate(record["body"], max(80, max_total_chars // 12))
    return True
