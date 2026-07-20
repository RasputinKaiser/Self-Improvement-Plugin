from __future__ import annotations
from collections import Counter
from datetime import datetime
from typing import Any

from memory_fabric_schema import (
    STRONG_PROVENANCE,
    normalize_confidence,
    normalize_provenance_type,
    normalize_status,
)


def created_at_timestamp(record: dict[str, Any]) -> float:
    raw = str(record.get("created_at", ""))
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return 0.0


def status_value(value: str) -> str:
    return normalized_filter(value, normalize_status)


def provenance_value(value: str) -> str:
    return normalized_filter(value, normalize_provenance_type)


def confidence_value(value: str) -> str:
    return normalized_filter(value, normalize_confidence)


def normalized_filter(value: str, normalizer) -> str:
    return normalizer(value) if value.strip() else ""


def legacy_numeric_confidence(value: str) -> str:
    try:
        score = float(value)
    except ValueError:
        return "unknown"
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    if score > 0:
        return "low"
    return "unknown"


def record_confidence(record: dict[str, Any]) -> str:
    raw = str(record.get("confidence", "")).strip().lower()
    if not raw:
        return "unknown"
    try:
        return normalize_confidence(raw)
    except ValueError:
        return legacy_numeric_confidence(raw)


def trust_status(record: dict[str, Any]) -> dict[str, Any]:
    provenance = str(record.get("provenance", {}).get("type", "unknown")).lower()
    confidence = record_confidence(record)
    reasons = [f"provenance:{provenance}", f"confidence:{confidence}"]
    if str(record.get("status", "")).lower() != "active":
        return trust_result("not_current", [*reasons, f"status:{record.get('status')}"])
    if bool(record.get("verify_before_use")):
        return trust_result("verify_before_use", [*reasons, "verify_before_use:true"])
    status = "context_only"
    if provenance in STRONG_PROVENANCE:
        status = {"high": "ready"}.get(confidence, "usable")
        reasons.append("strong_provenance")
    return trust_result(status, reasons)


def trust_result(status: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "reasons": reasons,
        "claim_boundary": "Trust labels guide retrieval; they do not prove the claim body.",
    }


def verify_value(value: str) -> bool | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise ValueError("verify_before_use expects true/false")


def none_if_empty(value: str) -> str | None:
    return value or None


def record_matches(
    record: dict[str, Any],
    *,
    score: int,
    tier_filter: str,
    scope: str,
    status_filter: str,
    provenance_filter: str = "",
    confidence_filter: str = "",
    verify_filter: bool | None = None,
) -> bool:
    return all(
        [
            score > 0,
            tier_matches(record, tier_filter),
            status_matches(record, status_filter),
            provenance_matches(record, provenance_filter),
            confidence_matches(record, confidence_filter),
            verify_matches(record, verify_filter),
            scope_matches(record, scope),
        ]
    )


def tier_matches(record: dict[str, Any], tier_filter: str) -> bool:
    return any([not tier_filter, record.get("tier") == tier_filter])


def status_matches(record: dict[str, Any], status_filter: str) -> bool:
    return any([not status_filter, str(record.get("status", "")).lower() == status_filter])


def provenance_matches(record: dict[str, Any], provenance_filter: str) -> bool:
    provenance = record.get("provenance", {})
    return any([not provenance_filter, str(provenance.get("type", "")).lower() == provenance_filter])


def confidence_matches(record: dict[str, Any], confidence_filter: str) -> bool:
    return any([not confidence_filter, record_confidence(record) == confidence_filter])


def verify_matches(record: dict[str, Any], verify_filter: bool | None) -> bool:
    return any([verify_filter is None, bool(record.get("verify_before_use")) is verify_filter])


def scope_matches(record: dict[str, Any], scope: str) -> bool:
    return any([not scope, scope in str(record.get("scope", ""))])


def apply_record_filters(
    records: list[dict[str, Any]],
    *,
    scope: str = "",
    status_filter: str = "",
    provenance_filter: str = "",
    confidence_filter: str = "",
    verify_filter: bool | None = None,
) -> list[dict[str, Any]]:
    return list(
        filter(
            lambda record: all(
                [
                    scope_matches(record, scope),
                    status_matches(record, status_filter),
                    provenance_matches(record, provenance_filter),
                    confidence_matches(record, confidence_filter),
                    verify_matches(record, verify_filter),
                ]
            ),
            records,
        )
    )


def count_field(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    values = map(lambda record: record.get(field, "unknown"), records)
    return dict(sorted(Counter(values).items()))


def count_confidence(records: list[dict[str, Any]]) -> dict[str, int]:
    values = map(record_confidence, records)
    return dict(sorted(Counter(values).items()))


def count_provenance(records: list[dict[str, Any]]) -> dict[str, int]:
    values = map(lambda record: record.get("provenance", {}).get("type", "unknown"), records)
    return dict(sorted(Counter(values).items()))


def count_verify(records: list[dict[str, Any]]) -> dict[str, int]:
    values = map(lambda record: str(bool(record.get("verify_before_use"))).lower(), records)
    return dict(sorted(Counter(values).items()))
