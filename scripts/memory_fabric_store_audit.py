from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any

from memory_fabric_store_audit_io import store_entries
from memory_fabric_store_audit_rules import audit_record


def store_audit(
    path: str | Path | None = None,
    max_body_chars: int = 4000,
    sample_limit: int = 20,
) -> dict[str, Any]:
    target, entries = store_entries(path)
    violations, warnings, ids = inspect_entries(entries, max_body_chars)
    duplicate_ids = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
    duplicate_violations = duplicate_reports(duplicate_ids)
    all_violations = violations + duplicate_violations
    return {
        "ok": not all_violations,
        "status": "store_valid" if not all_violations else "store_audit_failed",
        "store": str(target),
        "line_count": len(entries),
        "record_count": len(ids),
        "violation_count": len(all_violations),
        "warning_count": len(warnings),
        "violations": all_violations[:sample_limit],
        "warnings": warnings[:sample_limit],
        "duplicate_id_count": len(duplicate_ids),
        "max_body_chars": max_body_chars,
        "claim_boundary": "Store audit checks JSONL/schema hygiene only; it does not prove live MCP exposure.",
    }


def inspect_entries(
    entries: list[dict[str, Any]],
    max_body_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    ids: list[str] = []
    for entry in entries:
        record = entry["record"]
        if entry["error"]:
            violations.append(report(entry, "json_invalid"))
            continue
        record_violations, record_warnings = audit_record(record, max_body_chars)
        violations.extend(report(entry, code) for code in record_violations)
        warnings.extend(report(entry, code) for code in record_warnings)
        if isinstance(record, dict) and record.get("id"):
            ids.append(str(record["id"]))
    return violations, warnings, ids


def duplicate_reports(duplicate_ids: list[str]) -> list[dict[str, Any]]:
    return [{"line": None, "id": identifier, "code": "duplicate_id"} for identifier in duplicate_ids]


def report(entry: dict[str, Any], code: str) -> dict[str, Any]:
    record = entry.get("record")
    identifier = record.get("id") if isinstance(record, dict) else None
    return {"line": entry.get("line"), "id": identifier, "code": code}
