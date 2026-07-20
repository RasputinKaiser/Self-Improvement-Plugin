from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_measurement import measurement_plan
from memory_fabric_token_coverage import token_coverage
from memory_fabric_usage import usage_report


CLAIM_BOUNDARY = (
    "Telemetry status is a readiness report only. It reads supplied operation and token "
    "usage files; it does not fabricate samples or prove current-host tool exposure."
)


def telemetry_status(
    *,
    operations_input: str = "",
    usage_input: list[str] | None = None,
    inline_json: str = "",
    plugin_eval_output: str = "",
    min_samples: int = 5,
    min_scenarios: int = 3,
) -> dict[str, Any]:
    usage = usage_report(
        paths=usage_input or [],
        inline_json=inline_json,
        min_samples=min_samples,
        min_scenarios=min_scenarios,
    )
    if not readable_file(operations_input):
        return status_without_operations(operations_input, usage, min_samples, min_scenarios)
    coverage = token_coverage(
        operations_input=operations_input,
        usage_input=usage_input or [],
        inline_json=inline_json,
        plugin_eval_output=plugin_eval_output,
        min_samples=min_samples,
        min_scenarios=min_scenarios,
    )
    return status_with_coverage(operations_input, usage, coverage)


def status_without_operations(
    operations_input: str,
    usage: dict[str, Any],
    min_samples: int,
    min_scenarios: int,
) -> dict[str, Any]:
    plan = measurement_plan(min_samples=min_samples, min_scenarios=min_scenarios)
    return {
        "ok": True,
        "status": "missing_operational_trace",
        "fabricated": False,
        "plugin_eval_observed_usage_ready": False,
        "operations_input": operations_input or None,
        "usage_report": usage,
        "measurement_plan": plan,
        "next_action": "capture_representative_operations_first",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def status_with_coverage(
    operations_input: str,
    usage: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    ready = bool(coverage["plugin_eval_observed_usage_ready"])
    return {
        "ok": True,
        "status": "ready_for_plugin_eval_observed_usage" if ready else coverage["status"],
        "fabricated": False,
        "plugin_eval_observed_usage_ready": ready,
        "operations_input": str(Path(operations_input).expanduser().resolve()),
        "usage_report": usage,
        "token_coverage": coverage,
        "next_action": next_action(ready, coverage),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def next_action(ready: bool, coverage: dict[str, Any]) -> str:
    if ready:
        return "run_plugin_eval_with_observed_usage_export"
    if coverage["status"] == "no_token_telemetry":
        return "capture_plugin_isolated_token_rows"
    if coverage["status"] == "token_coverage_not_plugin_isolated":
        return "recapture_with_plugin_isolated_metadata"
    return "fill_missing_token_scenarios"


def readable_file(path: str) -> bool:
    return bool(path) and Path(path).expanduser().is_file()
