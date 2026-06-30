from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any

from memory_fabric_evidence_supersession import superseded_targets
from memory_fabric_jsonl import load_records, store_path
from memory_fabric_store_audit_enums import LEGACY_PROVENANCE_TYPES


LOCAL_PATH_PREFIXES = ("/", "~", ".")
WARNING_STATUSES = {"empty", "missing", "relative"}
STRICT_EVIDENCE_EXEMPT_PROVENANCE_TYPES = {"user_instruction"}


def evidence_audit(
    path: str | Path | None = None,
    scope: str = "",
    strict: bool = False,
    sample_limit: int = 20,
) -> dict[str, Any]:
    records = scoped_records(load_records(path), scope)
    superseded = superseded_targets(records)
    entries = [evidence_entry(record, superseded) for record in records]
    warnings = warning_entries(entries)
    violations = strict_violations(warnings, strict)
    return {
        "ok": not violations,
        "status": audit_status(warnings, violations, strict),
        "store": str(store_path(path)),
        "scope": scope,
        "record_count": len(records),
        "checked_count": len(entries),
        "existing_count": count_status(entries, "exists"),
        "missing_count": count_status(entries, "missing"),
        "empty_count": count_status(entries, "empty"),
        "external_count": count_status(entries, "external"),
        "superseded_warning_count": superseded_warning_count(warnings),
        "warning_count": len(warnings),
        "violation_count": len(violations),
        "warnings": warnings[:sample_limit],
        "violations": violations[:sample_limit],
        "provenance_counts": provenance_counts(entries),
        "strict_exempt_provenance_types": sorted(STRICT_EVIDENCE_EXEMPT_PROVENANCE_TYPES),
        "claim_boundary": "Path audit only; not live MCP proof.",
    }


def scoped_records(records: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if not scope:
        return records
    return list(filter(lambda record: scope in str(record.get("scope", "")), records))


def evidence_entry(record: dict[str, Any], superseded: dict[str, str]) -> dict[str, Any]:
    evidence_path = str(record.get("provenance", {}).get("evidence_path", "")).strip()
    record_id = str(record.get("id", ""))
    return {
        "id": record_id,
        "tier": record.get("tier"),
        "title": record.get("title"),
        "status": record.get("status"),
        "provenance_type": normalized_provenance(record),
        "evidence_path": evidence_path,
        "evidence_status": evidence_status(evidence_path),
        "superseded_by": superseded.get(record_id, ""),
    }


def normalized_provenance(record: dict[str, Any]) -> str:
    raw = str(record.get("provenance", {}).get("type", ""))
    return LEGACY_PROVENANCE_TYPES.get(raw, raw)


def evidence_status(evidence_path: str) -> str:
    if not evidence_path:
        return "empty"
    if evidence_path.startswith(("http://", "https://")):
        return "external"
    if evidence_path.startswith(LOCAL_PATH_PREFIXES):
        return "exists" if Path(evidence_path).expanduser().exists() else "missing"
    return "relative"


def warning_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(map(warning_entry, filter(needs_warning, entries)))


def needs_warning(entry: dict[str, Any]) -> bool:
    return entry["evidence_status"] in WARNING_STATUSES


def warning_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "title": entry["title"],
        "tier": entry["tier"],
        "status": entry["status"],
        "provenance_type": entry["provenance_type"],
        "evidence_path": entry["evidence_path"],
        "superseded_by": entry["superseded_by"],
        "code": f"evidence_{entry['evidence_status']}",
    }


def superseded_warning_count(warnings: list[dict[str, Any]]) -> int:
    return len([warning for warning in warnings if warning.get("superseded_by")])


def count_status(entries: list[dict[str, Any]], status: str) -> int:
    return list(map(evidence_status_value, entries)).count(status)


def evidence_status_value(entry: dict[str, Any]) -> str:
    return entry["evidence_status"]


def provenance_type(entry: dict[str, Any]) -> str:
    return entry["provenance_type"]


def provenance_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(map(provenance_type, entries)).items()))


def strict_violations(warnings: list[dict[str, Any]], strict: bool) -> list[dict[str, Any]]:
    return [
        warning
        for warning in warnings
        if strict and warning["provenance_type"] not in STRICT_EVIDENCE_EXEMPT_PROVENANCE_TYPES
        and not warning.get("superseded_by")
    ]


def audit_status(warnings: list[dict[str, Any]], violations: list[dict[str, Any]], strict: bool) -> str:
    if violations and strict:
        return "evidence_audit_failed"
    if warnings:
        return "evidence_warnings"
    return "evidence_valid"
