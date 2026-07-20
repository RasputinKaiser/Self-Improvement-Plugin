from __future__ import annotations
from typing import Any

from memory_fabric_frontier_common import gate


def release_gate(release: dict[str, Any]) -> dict[str, Any]:
    if not release:
        return gate(False, "release_report_missing", "Attach a release-report receipt.")
    local_ok = bool(release.get("local_ok"))
    gauge_ok = release.get("gauge_ok")
    ok = local_ok and gauge_ok is not False
    summary = (
        "Release report local/gauge boundary is acceptable."
        if ok
        else "Release report must show local_ok plus no gauge failure."
    )
    return gate(
        ok,
        "release_boundary_ready" if ok else "release_boundary_attention",
        summary,
        {
            "release_status": release.get("status", ""),
            "local_ok": local_ok,
            "gauge_ok": gauge_ok,
            "report_ok": release.get("ok"),
        },
    )


def plugin_eval_gate(plugin_eval: dict[str, Any], min_score: int) -> dict[str, Any]:
    if not plugin_eval:
        return gate(False, "plugin_eval_missing", "Attach a Plugin Eval receipt.")
    summary = plugin_eval.get("summary", {})
    score = int(summary.get("score", plugin_eval.get("score", 0)) or 0)
    ok = score >= int(min_score)
    grade = summary.get("grade", plugin_eval.get("grade", ""))
    return gate(
        ok,
        "plugin_eval_gauge_ready" if ok else "plugin_eval_gauge_attention",
        "Plugin Eval gauge meets the configured score floor."
        if ok
        else "Plugin Eval gauge is below the configured score floor.",
        {"score": score, "grade": grade, "min_score": int(min_score)},
    )


def budget_gate(budget: dict[str, Any], required: bool) -> dict[str, Any]:
    if not budget:
        return gate(False, "budget_plan_missing", "Attach a budget-plan receipt.")
    overage = int(budget.get("deferred_overage_tokens", 0) or 0)
    usage = budget.get("usage_evidence", {})
    observed_ready = bool(usage.get("observed_invocation_cost_available"))
    static_ready = overage == 0 and bool(budget.get("ok"))
    ok = (static_ready or observed_ready) if required else True
    status = budget_gate_status(ok, static_ready, observed_ready)
    return gate(
        ok,
        status,
        budget_summary(ok, static_ready, observed_ready),
        {
            "required": bool(required),
            "budget_status": budget.get("status", ""),
            "deferred_cost_tokens": budget.get("deferred_cost_tokens", 0),
            "deferred_overage_tokens": overage,
            "static_budget_ready": static_ready,
            "observed_usage_budget_ready": observed_ready,
            "usage_evidence_status": usage.get("status", ""),
            "usage_sample_count": usage.get("sample_count", 0),
            "usage_scenario_count": usage.get("scenario_count", 0),
            "token_averages": usage.get("token_averages", {}),
        },
    )


def budget_gate_status(ok: bool, static_ready: bool, observed_ready: bool) -> str:
    if not ok:
        return "deferred_budget_attention"
    if static_ready:
        return "deferred_budget_ready"
    if observed_ready:
        return "deferred_budget_observed_usage_ready"
    return "deferred_budget_ready"


def budget_summary(ok: bool, static_ready: bool, observed_ready: bool) -> str:
    if static_ready:
        return "Deferred budget is within target."
    if observed_ready:
        return (
            "Static deferred budget remains over target, but representative observed "
            "usage resolves the runtime-cost gate without hiding the static gauge."
        )
    if ok:
        return "Deferred budget gate is not required for this audit."
    return "Deferred static budget pressure remains unresolved."
