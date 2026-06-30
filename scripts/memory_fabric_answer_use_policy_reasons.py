from __future__ import annotations
from typing import Any


def blocked_record_ids(graph: dict[str, Any]) -> set[str]:
    ids = []
    ids.extend(superseded_ids(graph))
    ids.extend(contradiction_ids(graph))
    return {item for item in ids if item}


def superseded_ids(graph: dict[str, Any]) -> list[str]:
    return [str(item.get("target", "")) for item in graph.get("active_superseded_records", [])]


def contradiction_ids(graph: dict[str, Any]) -> list[str]:
    ids = []
    for item in graph.get("active_contradictions", []):
        ids.extend([str(item.get("source", "")), str(item.get("target", ""))])
    return ids


def global_verify_reasons(
    brief: dict[str, Any],
    graph: dict[str, Any],
    hypotheses: dict[str, Any],
    claims: dict[str, Any],
    checks: list[str],
) -> list[str]:
    del graph, hypotheses, claims
    reasons = readiness_reasons(brief)
    reasons.extend(checks)
    return dedupe(reasons)


def readiness_reasons(brief: dict[str, Any]) -> list[str]:
    return list(brief.get("readiness", {}).get("recommended_next_checks", []))


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
