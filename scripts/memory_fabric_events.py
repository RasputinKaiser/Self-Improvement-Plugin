from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_classify import classify_note
from memory_fabric_jsonl import append_record
from memory_fabric_promotion import assess_promotion
from memory_fabric_records import make_record
from memory_fabric_schema import normalize_status, normalize_tier


def first_event_value(event: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = event.get(key)
        if value:
            return str(value)
    return default


def read_event_json(value: str, stdin_text: str = "") -> dict[str, Any]:
    raw = stdin_text if value == "-" else value
    candidate = Path(raw).expanduser()
    if value != "-" and candidate.exists():
        raw = candidate.read_text(encoding="utf-8")
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ValueError("hook event JSON must be an object")
    return event


def select_hook_status(policy_status: str, requested_status: str = "") -> dict[str, Any]:
    requested = normalize_status(requested_status) if requested_status else policy_status
    upgrade_blocked = policy_status == "candidate" and requested == "active"
    selected = policy_status if upgrade_blocked else requested
    return {
        "policy_recommended_status": policy_status,
        "requested_status": requested if requested_status else "",
        "selected_status": selected,
        "upgrade_blocked": upgrade_blocked,
    }


def record_from_hook_event(event: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    text = first_event_value(event, ["body", "text", "message"])
    title = first_event_value(event, ["title", "event"], "Memory Fabric hook event")
    tier = normalize_tier(first_event_value(event, ["tier"], classify_note(text)["suggested_tier"]))
    provenance_type = first_event_value(event, ["provenance_type", "source"], "hook_event")
    evidence_path = first_event_value(event, ["evidence_path"])
    confidence = first_event_value(event, ["confidence"], "medium")
    policy = assess_promotion(
        tier=tier,
        text=text,
        provenance_type=provenance_type,
        evidence_path=evidence_path,
        confidence=confidence,
    )
    status_policy = select_hook_status(policy["recommended_status"], first_event_value(event, ["status"]))
    record = make_record(
        tier=tier,
        title=title,
        body=text or json.dumps(event, sort_keys=True),
        scope=str(event.get("scope") or "global"),
        tags=event.get("tags") or ["hook-event"],
        provenance_type=policy["provenance_type"],
        provenance=first_event_value(event, ["provenance"], "codex-memory-fabric hook event"),
        evidence_path=evidence_path,
        confidence=confidence,
        verify_before_use=policy["verify_before_use"],
        status=status_policy["selected_status"],
    )
    appended = append_record(record, path)
    appended["promotion_policy"] = policy
    appended["status_policy"] = status_policy
    return appended
