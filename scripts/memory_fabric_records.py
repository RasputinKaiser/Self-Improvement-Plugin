from __future__ import annotations
import re
import uuid
from typing import Any

from memory_fabric_schema import (
    normalize_confidence,
    normalize_provenance_type,
    normalize_status,
    normalize_tier,
    record_schema_version,
)
from memory_fabric_time import utc_now


def split_tags(value: str | list[str] | None) -> list[str]:
    values = value if isinstance(value, list) else re.split(r"[, ]+", value or "")
    tags = []
    for tag in values:
        clean = str(tag).strip().lower()
        if clean and clean not in tags:
            tags.append(clean)
    return tags


def make_record(
    *,
    tier: str,
    title: str,
    body: str,
    scope: str = "global",
    tags: str | list[str] | None = None,
    provenance_type: str = "user_or_agent_observation",
    provenance: str = "",
    evidence_path: str = "",
    confidence: str = "medium",
    verify_before_use: bool = False,
    status: str = "active",
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("title is required")
    if not body.strip():
        raise ValueError("body is required")
    return {
        "schema_version": record_schema_version(),
        "id": f"mem_{uuid.uuid4().hex[:16]}",
        "tier": normalize_tier(tier),
        "title": title.strip(),
        "body": body.strip(),
        "scope": scope.strip() or "global",
        "tags": split_tags(tags),
        "provenance": {
            "type": normalize_provenance_type(provenance_type),
            "detail": provenance.strip(),
            "evidence_path": evidence_path.strip(),
        },
        "confidence": normalize_confidence(confidence),
        "verify_before_use": bool(verify_before_use),
        "status": normalize_status(status),
        "created_at": utc_now(),
    }
