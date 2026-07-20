from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_token_scenarios import plugin_isolated_sample_count
from memory_fabric_usage_export import export_plugin_eval_jsonl


CLAIM_BOUNDARY = (
    "Observed usage needs real plugin-isolated token rows; ops/thread counts are not enough."
)

TOKEN_FIELDS = ["input_tokens", "output_tokens", "total_tokens"]
FORBIDDEN = ["manual", "operation_trace", "thread_token_count", "fixture"]
CONTRACT_VERSION = "token_coverage.v2"


def coverage_report(
    operation_scenarios: list[str],
    token_scenarios: list[str],
    isolated_scenarios: list[str],
    missing: list[str],
    missing_isolated: list[str],
    samples: list[dict[str, Any]],
    quality: dict[str, Any],
    complete: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status_for(samples, complete, missing, missing_isolated),
        "contract_version": CONTRACT_VERSION,
        "fabricated": False,
        "coverage_complete": complete,
        "plugin_eval_observed_usage_ready": complete,
        "operation_scenario_count": len(operation_scenarios),
        "token_sample_count": len(samples),
        "token_scenario_count": len(token_scenarios),
        "plugin_isolated_token_sample_count": plugin_isolated_sample_count(samples),
        "plugin_isolated_token_scenario_count": len(isolated_scenarios),
        "operation_scenarios": operation_scenarios,
        "token_scenarios": token_scenarios,
        "plugin_isolated_token_scenarios": isolated_scenarios,
        "missing_token_scenarios": missing,
        "missing_plugin_isolated_token_scenarios": missing_isolated,
        "capture_requirements": capture_requirements(missing, missing_isolated, complete),
        "usage_quality": quality,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def status_for(samples: list[dict[str, Any]], complete: bool, missing: list[str], missing_isolated: list[str]) -> str:
    if not samples:
        return "no_token_telemetry"
    if complete:
        return "representative_plugin_isolated_token_coverage"
    if not missing and missing_isolated:
        return "token_coverage_not_plugin_isolated"
    return "token_coverage_incomplete"


def guarded_export(samples: list[dict[str, Any]], output: str, complete: bool) -> dict[str, Any]:
    if complete:
        return export_plugin_eval_jsonl(samples, output)
    return {
        "ok": False,
        "status": "skipped_incomplete_token_coverage",
        "output": str(Path(output).expanduser().resolve()),
        "sample_count": len(samples),
        "reason": "Export waits for isolated token coverage.",
    }


def capture_requirements(missing: list[str], missing_isolated: list[str], complete: bool) -> list[dict[str, Any]]:
    if complete:
        return []
    scenarios = sorted(set(missing) | set(missing_isolated))
    return [
        {
            "scenario": name,
            "event_type": "response.done",
            "required_metadata": {
                "plugin": "codex-memory-fabric",
                "plugin_isolated": True,
                "isolation": "plugin",
                "scenario": name,
            },
            "required_usage_fields": TOKEN_FIELDS,
            "forbidden_sources": FORBIDDEN,
        }
        for name in scenarios
    ]
