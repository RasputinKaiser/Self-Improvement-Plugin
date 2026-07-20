from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_jsonl import load_records, store_path
from memory_fabric_search_filters import apply_record_filters, confidence_value
from memory_fabric_search_filters import count_confidence, count_field, count_provenance
from memory_fabric_search_filters import count_verify, none_if_empty, provenance_value
from memory_fabric_search_filters import record_confidence, verify_value
from memory_fabric_schema import normalize_status
from memory_fabric_time import utc_now


def snapshot(
    scope: str = "",
    status: str = "",
    provenance_type: str = "",
    confidence: str = "",
    verify_before_use: str = "",
    limit: int = 20,
    path: str | Path | None = None,
) -> dict[str, Any]:
    records = load_records(path)
    status_filter = normalize_status(status) if status.strip() else ""
    provenance_filter = provenance_value(provenance_type)
    confidence_filter = confidence_value(confidence)
    verify_filter = verify_value(verify_before_use)
    records = apply_record_filters(
        records,
        scope=scope,
        status_filter=status_filter,
        provenance_filter=provenance_filter,
        confidence_filter=confidence_filter,
        verify_filter=verify_filter,
    )
    records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {
        "ok": True,
        "scope": none_if_empty(scope),
        "status": none_if_empty(status_filter),
        "provenance_type": none_if_empty(provenance_filter),
        "confidence": none_if_empty(confidence_filter),
        "verify_before_use": verify_filter,
        "store": str(store_path(path)),
        "total": len(records),
        "counts": count_field(records, "tier"),
        "status_counts": count_field(records, "status"),
        "confidence_counts": count_confidence(records),
        "provenance_counts": count_provenance(records),
        "verify_before_use_counts": count_verify(records),
        "recent": records[: max(1, int(limit))],
        "projection_note": "Compact projection; JSONL store is authoritative.",
    }


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "tier": record.get("tier"),
        "title": record.get("title"),
        "status": record.get("status"),
        "confidence": record_confidence(record),
        "provenance_type": record.get("provenance", {}).get("type"),
        "verify_before_use": record.get("verify_before_use"),
        "created_at": record.get("created_at"),
    }


def project(
    scope: str,
    output: str = "",
    status: str = "",
    provenance_type: str = "",
    confidence: str = "",
    verify_before_use: str = "",
    limit: int = 12,
    path: str | Path | None = None,
) -> dict[str, Any]:
    if not scope:
        raise ValueError("scope is required for projections")
    data = snapshot(
        scope=scope,
        status=status,
        provenance_type=provenance_type,
        confidence=confidence,
        verify_before_use=verify_before_use,
        limit=limit,
        path=path,
    )
    projection = {
        "generated_at": utc_now(),
        "scope": scope,
        "status": data["status"],
        "provenance_type": data["provenance_type"],
        "confidence": data["confidence"],
        "verify_before_use": data["verify_before_use"],
        "memory_fabric_store": data["store"],
        "counts": data["counts"],
        "status_counts": data["status_counts"],
        "confidence_counts": data["confidence_counts"],
        "provenance_counts": data["provenance_counts"],
        "verify_before_use_counts": data["verify_before_use_counts"],
        "recent": list(map(compact_record, data["recent"])),
        "source_of_truth": "append-only memory fabric store",
    }
    if output:
        target = Path(output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"ok": True, "output": str(target), "projection": projection}
    return {"ok": True, "projection": projection}
