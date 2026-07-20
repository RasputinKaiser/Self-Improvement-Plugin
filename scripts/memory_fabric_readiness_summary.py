from __future__ import annotations
import json
from pathlib import Path
from typing import Any


READINESS_SUMMARY_CONTRACT_VERSION = "readiness_summary.v1"
CLAIM_BOUNDARY = (
    "Readiness summaries compose supplied receipts only; they do not run live checks, "
    "verify external truth, or upgrade source/cache proof into current-live proof."
)


def readiness_summary(
    release_report_json: str = "",
    frontier_audit_json: str = "",
    schema_json: str = "",
    store_audit_json: str = "",
    evidence_audit_json: str = "",
    current_doctor_json: str = "",
    current_behavior_json: str = "",
) -> dict[str, Any]:
    receipts = {
        "release_report": read_optional_json(release_report_json),
        "frontier_audit": read_optional_json(frontier_audit_json),
        "schema": read_optional_json(schema_json),
        "store_audit": read_optional_json(store_audit_json),
        "evidence_audit": read_optional_json(evidence_audit_json),
        "current_doctor": read_optional_json(current_doctor_json),
        "current_behavior": read_optional_json(current_behavior_json),
    }
    supplied = [name for name, receipt in receipts.items() if receipt]
    safe_claims: list[str] = []
    unproven_claims: list[str] = []
    next_checks: list[str] = []
    layers = {
        "schema": schema_layer(receipts["schema"], safe_claims, unproven_claims, next_checks),
        "release": release_layer(receipts["release_report"], safe_claims, unproven_claims, next_checks),
        "frontier": frontier_layer(receipts["frontier_audit"], safe_claims, unproven_claims, next_checks),
        "store": store_layer(receipts["store_audit"], safe_claims, unproven_claims, next_checks),
        "evidence": evidence_layer(receipts["evidence_audit"], safe_claims, unproven_claims, next_checks),
        "current_doctor": current_doctor_layer(receipts["current_doctor"], safe_claims, unproven_claims, next_checks),
        "current_behavior": current_behavior_layer(receipts["current_behavior"], safe_claims, unproven_claims, next_checks),
    }
    status = readiness_status(supplied, unproven_claims)
    return {
        "ok": bool(supplied) and not unproven_claims,
        "status": status,
        "supplied_receipts": supplied,
        "safe_claims": safe_claims,
        "unproven_or_blocked_claims": unproven_claims,
        "recommended_next_checks": dedupe(next_checks),
        "layers": layers,
        "inputs": {
            "release_report_json": release_report_json,
            "frontier_audit_json": frontier_audit_json,
            "schema_json": schema_json,
            "store_audit_json": store_audit_json,
            "evidence_audit_json": evidence_audit_json,
            "current_doctor_json": current_doctor_json,
            "current_behavior_json": current_behavior_json,
        },
        "runtime_contract": {
            "component": "readiness_summary",
            "behavior_contract_version": READINESS_SUMMARY_CONTRACT_VERSION,
            "composes_supplied_receipts_only": True,
            "separates_safe_and_unproven_claims": True,
            "preserves_source_cache_live_boundaries": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def schema_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        next_checks.append("supply_schema_receipt_for_contract_and_runtime_claims")
        return {"supplied": False}
    fingerprint = receipt.get("runtime_fingerprint", {})
    ok = fingerprint.get("ok") is True
    version = str(receipt.get("plugin_version", ""))
    detail = str(receipt.get("schema_detail", ""))
    safe_claims.append(f"Supplied schema receipt reports plugin version {version}.")
    if ok:
        safe_claims.append("Supplied schema receipt reports runtime imports matched source when it was produced.")
    else:
        unproven_claims.append("Runtime import freshness is not safe to claim from the supplied schema receipt.")
        next_checks.append("refresh_schema_or_runtime_fingerprint_receipt")
    return {
        "supplied": True,
        "ok": ok,
        "plugin_version": version,
        "schema_detail": detail,
        "runtime_status": fingerprint.get("status", ""),
        "stale_module_count": fingerprint.get("stale_module_count", 0),
    }


def release_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        next_checks.append("supply_release_report_for_source_cache_live_release_claims")
        return {"supplied": False}
    checks = receipt.get("checks", {})
    status = str(receipt.get("status", ""))
    current_live_ok = checks.get("current_live_ok") is True
    behavior_ok = checks.get("current_live_behavior_ok") is True
    if status == "release_ready" and current_live_ok and behavior_ok:
        safe_claims.append("Supplied release report supports a release-ready current-live behavior claim.")
    elif status in {"release_ready", "release_ready_with_measurement_attention"}:
        safe_claims.append("Supplied release report supports local/source/cache release readiness only.")
        unproven_claims.append("Current-live behavior is not safe to claim from the supplied release report.")
        next_checks.append("supply_current_live_behavior_receipt")
    else:
        unproven_claims.append("Release readiness is not safe to claim from the supplied release report.")
        next_checks.extend(str(item.get("code", "")) for item in receipt.get("attention", []) if item.get("code"))
    return {
        "supplied": True,
        "ok": status == "release_ready" and current_live_ok and behavior_ok,
        "status": status,
        "current_live_checked": checks.get("current_live_checked"),
        "current_live_ok": current_live_ok,
        "current_live_behavior_ok": behavior_ok,
    }


def frontier_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        next_checks.append("supply_frontier_audit_for_completion_claim")
        return {"supplied": False}
    allowed = receipt.get("completion_claim_allowed") is True
    if allowed:
        safe_claims.append("Supplied frontier audit allows the frontier completion claim.")
    else:
        unproven_claims.append("Frontier completion is not safe to claim from the supplied frontier audit.")
        next_checks.extend(str(item) for item in receipt.get("attention", []))
    return {
        "supplied": True,
        "ok": allowed,
        "status": receipt.get("status", ""),
        "attention": receipt.get("attention", []),
    }


def store_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        next_checks.append("supply_store_audit_for_store_hygiene_claim")
        return {"supplied": False}
    ok = receipt.get("ok") is True
    if ok:
        safe_claims.append("Supplied store audit supports JSONL/schema hygiene for the audited store.")
    else:
        unproven_claims.append("Store hygiene is not safe to claim from the supplied store audit.")
        next_checks.append("fix_store_audit_violations")
    return {"supplied": True, "ok": ok, "status": receipt.get("status", "")}


def evidence_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        next_checks.append("supply_evidence_audit_for_evidence_path_claim")
        return {"supplied": False}
    ok = receipt.get("ok") is True
    if ok:
        safe_claims.append("Supplied evidence audit supports audited evidence-path hygiene.")
    else:
        unproven_claims.append("Evidence-path hygiene is not safe to claim from the supplied evidence audit.")
        next_checks.append("repair_missing_or_invalid_evidence_paths")
    return {"supplied": True, "ok": ok, "status": receipt.get("status", "")}


def current_doctor_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        return {"supplied": False}
    live = receipt.get("live", receipt)
    ok = live.get("ok") is True
    if ok:
        safe_claims.append("Supplied current doctor receipt supports advertised live tool availability.")
    else:
        unproven_claims.append("Current-live tool availability is not safe to claim from the supplied doctor receipt.")
        next_checks.append("refresh_current_live_doctor")
    return {"supplied": True, "ok": ok, "status": live.get("status", "")}


def current_behavior_layer(
    receipt: dict[str, Any],
    safe_claims: list[str],
    unproven_claims: list[str],
    next_checks: list[str],
) -> dict[str, Any]:
    if not receipt:
        return {"supplied": False}
    checked = receipt.get("checked", receipt.get("receipt_count", 0) > 0)
    ok = receipt.get("ok") is True
    if checked and ok:
        safe_claims.append("Supplied current behavior receipt supports checked current-live behavior.")
    else:
        unproven_claims.append("Checked current-live behavior is not safe to claim from the supplied behavior receipt.")
        next_checks.append("refresh_current_live_behavior_receipt")
    return {"supplied": True, "checked": bool(checked), "ok": ok, "status": receipt.get("status", "")}


def readiness_status(supplied: list[str], unproven_claims: list[str]) -> str:
    if not supplied:
        return "no_receipts_supplied"
    return "claim_readiness_ready" if not unproven_claims else "claim_readiness_attention"


def read_optional_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def dedupe(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
