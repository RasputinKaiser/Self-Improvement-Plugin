from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_evidence_audit import evidence_audit
from memory_fabric_projection_audit import audit_projection
from memory_fabric_store_audit import store_audit


def hook_health(
    path: str | Path | None = None,
    projection_input: str = "",
    evidence_scope: str = "",
    strict_evidence: bool = False,
    sample_limit: int = 20,
) -> dict[str, Any]:
    store = store_audit(path=path, sample_limit=sample_limit)
    evidence = evidence_audit(
        path=path,
        scope=evidence_scope,
        strict=strict_evidence,
        sample_limit=sample_limit,
    )
    projection = projection_health(projection_input)
    checks = {"store": store["ok"], "evidence": evidence["ok"], "projection": projection["ok"]}
    return {
        "ok": all(checks.values()),
        "status": health_status(checks),
        "checks": checks,
        "store": summarized_store(store),
        "evidence": summarized_evidence(evidence),
        "projection": projection,
        "claim_boundary": "Hook health checks local memory receipts only; it does not prove live MCP exposure.",
    }


def projection_health(projection_input: str) -> dict[str, Any]:
    if not projection_input:
        return {"ok": True, "status": "projection_not_requested", "input": ""}
    return audit_projection(input_path=projection_input)


def health_status(checks: dict[str, bool]) -> str:
    return "hook_ready" if all(checks.values()) else "hook_attention"


def summarized_store(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": audit["ok"],
        "status": audit["status"],
        "record_count": audit["record_count"],
        "warning_count": audit["warning_count"],
        "violation_count": audit["violation_count"],
    }


def summarized_evidence(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": audit["ok"],
        "status": audit["status"],
        "record_count": audit["record_count"],
        "existing_count": audit["existing_count"],
        "warning_count": audit["warning_count"],
        "violation_count": audit["violation_count"],
    }
