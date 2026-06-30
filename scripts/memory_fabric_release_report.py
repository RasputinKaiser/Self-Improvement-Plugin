from __future__ import annotations
import time

from memory_fabric_hook_health import hook_health
from memory_fabric_install import doctor
from memory_fabric_receipt_summary import (
    behavior_receipts,
    benchmark_receipt,
    current_live_summary,
    doctor_receipt,
    plugin_eval_receipt,
)
from memory_fabric_live_freshness import live_freshness_summary
from memory_fabric_release_attention import release_attention
from memory_fabric_release_reconnect import reconnect_diagnosis


CLAIM_BOUNDARY = "Local ready is not live proof."
LOCAL_CHECKS = [
    "source_ok",
    "marketplace_ok",
    "cache_ok",
    "mcp_ok",
    "hook_ok",
    "benchmark_ok",
    "performance_ok",
]


def release_report(
    version="",
    plugin_root=None,
    marketplace_path=None,
    cache_root=None,
    store=None,
    projection_input="",
    plugin_eval_json="",
    benchmark_json="",
    current_doctor_json="",
    current_behavior_json="",
    hook_health_json="",
    expected_doctor_json="",
    advertised_tools=None,
    advertised_surface=None,
    advertised_truncated=False,
    evidence_scope="",
    strict_evidence=False,
    require_current_behavior=False,
    min_plugin_eval_score=90,
    max_report_ms=1000,
    sample_limit=20,
):
    started = time.perf_counter()
    component_ms = {}
    local_started = time.perf_counter()
    local = doctor(
        plugin_root=plugin_root,
        marketplace_path=marketplace_path,
        cache_root=cache_root,
        check_cli_surface=False,
    )
    component_ms["local_doctor"] = elapsed_ms(local_started)
    release_version = version or str(local.get("source", {}).get("version", ""))
    hook_started = time.perf_counter()
    hook = hook_health_input(
        hook_health_json=hook_health_json,
        store=store,
        projection_input=projection_input,
        evidence_scope=evidence_scope,
        strict_evidence=strict_evidence,
        sample_limit=sample_limit,
    )
    component_ms["hook_health"] = elapsed_ms(hook_started)
    receipts_started = time.perf_counter()
    plugin_eval = plugin_eval_receipt(plugin_eval_json, min_plugin_eval_score)
    benchmark = benchmark_receipt(benchmark_json)
    current_live = current_live_summary(
        current_doctor_json=current_doctor_json,
        advertised_tools=advertised_tools,
        advertised_surface=advertised_surface,
        advertised_truncated=advertised_truncated,
        plugin_root=plugin_root,
        marketplace_path=marketplace_path,
        cache_root=cache_root,
    )
    expected = doctor_receipt(expected_doctor_json)
    behavior = behavior_receipts(current_behavior_json)
    freshness = live_freshness_summary(release_version, current_live, behavior)
    component_ms["receipt_reads"] = elapsed_ms(receipts_started)
    performance = performance_summary(started, component_ms, max_report_ms)
    checks = release_checks(
        local,
        hook,
        plugin_eval,
        benchmark,
        current_live,
        behavior,
        performance,
        require_current_behavior=require_current_behavior,
    )
    local_ok = all(checks[name] for name in LOCAL_CHECKS)
    gauge_ok = checks["plugin_eval_ok"]
    live_ok = all((checks["current_live_ok"], checks["current_live_behavior_ok"]))
    status = release_status(local_ok, current_live, live_ok, gauge_ok)
    reconnect = reconnect_diagnosis(checks, current_live, behavior, local)
    return {
        "ok": local_ok and live_ok,
        "local_ok": local_ok,
        "gauge_ok": gauge_ok,
        "status": status,
        "reconnect": reconnect,
        "version": release_version,
        "checks": checks,
        "attention": release_attention(checks, current_live, local, behavior, freshness),
        "local": summarize_local(local),
        "hook_health": summarize_hook(hook),
        "plugin_eval": plugin_eval,
        "benchmark": benchmark,
        "current_live": current_live,
        "current_live_behavior": behavior,
        "live_freshness": freshness,
        "expected_live": expected,
        "performance": performance,
        "inputs": {
            "plugin_eval_json": plugin_eval_json,
            "benchmark_json": benchmark_json,
            "current_doctor_json": current_doctor_json,
            "current_behavior_json": current_behavior_json,
            "hook_health_json": hook_health_json,
            "expected_doctor_json": expected_doctor_json,
            "advertised_tool_count": len(advertised_tools or []),
            "advertised_surface_supplied": bool(advertised_surface),
            "advertised_truncated": bool(advertised_truncated),
            "projection_input": projection_input,
            "evidence_scope": evidence_scope,
            "strict_evidence": strict_evidence,
            "require_current_behavior": require_current_behavior,
            "max_report_ms": max_report_ms,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }

def release_checks(
    local,
    hook,
    plugin_eval,
    benchmark,
    current_live,
    behavior,
    performance,
    require_current_behavior=False,
):
    behavior_checked = bool(behavior.get("checked"))
    behavior_ok = behavior.get("ok") is not False
    if require_current_behavior and not behavior_checked:
        behavior_ok = False
    return {
        "source_ok": bool(local.get("source", {}).get("ok")),
        "marketplace_ok": bool(local.get("marketplace", {}).get("ok")),
        "cache_ok": bool(local.get("cache", {}).get("ok")),
        "mcp_ok": bool(local.get("mcp", {}).get("ok")),
        "hook_ok": bool(hook.get("ok")),
        "plugin_eval_ok": bool(plugin_eval.get("ok")),
        "benchmark_ok": bool(benchmark.get("ok")),
        "performance_ok": bool(performance.get("ok")),
        "current_live_checked": bool(current_live.get("tool_exposure_checked")),
        "current_live_ok": bool(current_live.get("ok")),
        "current_live_behavior_checked": behavior_checked,
        "current_live_behavior_required": bool(require_current_behavior),
        "current_live_behavior_ok": behavior_ok,
    }


def hook_health_input(
    hook_health_json,
    store,
    projection_input,
    evidence_scope,
    strict_evidence,
    sample_limit,
):
    if hook_health_json:
        report = read_json(hook_health_json)
        return {
            **report,
            "source": "receipt",
            "path": hook_health_json,
        }
    report = hook_health(
        path=store,
        projection_input=projection_input,
        evidence_scope=evidence_scope,
        strict_evidence=strict_evidence,
        sample_limit=sample_limit,
    )
    return {
        **report,
        "source": "inline_hook_health",
    }


def release_status(
    local_ok,
    current_live,
    live_ok,
    gauge_ok=True,
):
    if not local_ok:
        return "release_attention"
    if live_ok:
        if not gauge_ok:
            return "release_ready_with_measurement_attention"
        return "release_ready"
    if current_live.get("tool_exposure_checked"):
        return "release_local_ready_live_stale"
    return "release_local_ready_live_unchecked"


def summarize_local(report):
    return {
        "ok": report.get("ok"),
        "status": report.get("status"),
        "source_version": report.get("source", {}).get("version", ""),
        "cache_ok": report.get("cache", {}).get("ok"),
        "marketplace_ok": report.get("marketplace", {}).get("ok"),
        "mcp_ok": report.get("mcp", {}).get("ok"),
    }


def summarize_hook(report):
    return {
        "ok": report.get("ok"),
        "status": report.get("status"),
        "source": report.get("source", ""),
        "path": report.get("path", ""),
        "checks": report.get("checks", {}),
        "store": report.get("store", {}),
        "evidence": report.get("evidence", {}),
        "projection": report.get("projection", {}),
    }


def performance_summary(started, component_ms, max_report_ms):
    elapsed = elapsed_ms(started)
    return {
        "ok": elapsed <= max_report_ms,
        "status": "release_report_fast_enough" if elapsed <= max_report_ms else "release_report_slow",
        "elapsed_ms": elapsed,
        "max_report_ms": max_report_ms,
        "component_ms": component_ms,
    }


def elapsed_ms(started):
    return round((time.perf_counter() - started) * 1000, 3)


def read_json(path):
    import json
    from pathlib import Path

    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
