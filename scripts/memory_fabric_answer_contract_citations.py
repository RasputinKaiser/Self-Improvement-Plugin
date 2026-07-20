from __future__ import annotations
from typing import Any


def required_citation_groups(answer_policy: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for record in citable_records(answer_policy):
        path = str(record.get("evidence_path", ""))
        groups.setdefault(path, citation_group(path))
        groups[path]["record_ids"].append(record.get("id", ""))
        groups[path]["titles"].append(record.get("title", ""))
        groups[path]["provenance_types"].append(record.get("provenance_type", ""))
    return [deduped_group(item) for item in groups.values()]


def citable_records(answer_policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record
        for record in answer_policy.get("records", [])
        if record.get("answer_use") == "cite" and record.get("evidence_path")
    ]


def citation_group(path: str) -> dict[str, Any]:
    return {
        "evidence_path": path,
        "record_ids": [],
        "titles": [],
        "provenance_types": [],
    }


def deduped_group(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "record_ids": dedupe(item["record_ids"]),
        "titles": dedupe(item["titles"]),
        "provenance_types": dedupe(item["provenance_types"]),
    }


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
