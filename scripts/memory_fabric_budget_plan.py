from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def budget_plan(
    plugin_eval_json: str,
    top_n: int = 10,
    max_deferred_tokens: int = 50000,
    usage_report_json: str = "",
) -> dict[str, Any]:
    data = read_json(plugin_eval_json)
    usage = usage_evidence(usage_report_json)
    budgets = data.get("budgets", {})
    deferred = budgets.get("deferred_cost_tokens", {})
    components = sorted(
        deferred.get("components", []),
        key=lambda item: int(item.get("tokens", 0) or 0),
        reverse=True,
    )
    value = int(deferred.get("value", 0) or 0)
    overage = max(0, value - max_deferred_tokens)
    top = components[:top_n]
    return {
        "ok": overage == 0,
        "status": "budget_within_target" if overage == 0 else "deferred_budget_attention",
        "plugin_eval_json": plugin_eval_json,
        "max_deferred_tokens": max_deferred_tokens,
        "deferred_cost_tokens": value,
        "deferred_overage_tokens": overage,
        "component_count": len(components),
        "top_components": top,
        "top_component_tokens": sum(int(item.get("tokens", 0) or 0) for item in top),
        "usage_evidence": usage,
        "recommendations": recommendations(value, overage, top, usage),
        "claim_boundary": (
            "Plugin Eval deferred budget is a static package-size gauge. "
            "Observed invocation cost must come from representative usage telemetry."
        ),
    }


def recommendations(
    value: int,
    overage: int,
    top_components: list[dict[str, Any]],
    usage: dict[str, Any] | None = None,
) -> list[str]:
    usage = usage or usage_evidence("")
    if overage == 0:
        return [
            "Keep monitoring deferred budget in release receipts.",
            usage["next_action"],
        ]
    largest = top_components[0]["label"] if top_components else "deferred support files"
    return [
        f"Trim at least {overage} estimated tokens.",
        f"Start with {largest}; keep runtime imports and tests.",
        "Prefer concise docs over duplicated prose.",
        "Do not move active runtime code into ignored folders just to improve the gauge.",
        usage["next_action"],
    ]


def usage_evidence(path: str) -> dict[str, Any]:
    if not path:
        return {
            "status": "observed_usage_missing",
            "usage_report_json": "",
            "sample_count": 0,
            "scenario_count": 0,
            "representative": False,
            "observed_invocation_cost_available": False,
            "next_action": (
                "Attach a representative usage-report receipt before treating budget pressure "
                "as observed invocation cost."
            ),
        }

    report = read_json(path)
    quality = report.get("usage_quality", {})
    scenario_count = int(quality.get("scenario_count", 0) or 0)
    sample_count = int(report.get("sample_count", 0) or 0)
    representative = bool(quality.get("representative"))
    available = bool(sample_count and representative)
    return {
        "status": "observed_usage_representative" if available else "observed_usage_not_representative",
        "usage_report_json": path,
        "sample_count": sample_count,
        "scenario_count": scenario_count,
        "representative": representative,
        "observed_invocation_cost_available": available,
        "token_totals": report.get("token_totals", {}),
        "token_averages": report.get("token_averages", {}),
        "next_action": (
            "Compare static deferred budget against observed invocation cost trends."
            if available
            else "Collect representative plugin-isolated usage before making runtime cost claims."
        ),
    }


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
