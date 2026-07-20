from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_token_coverage_report import coverage_report, guarded_export
from memory_fabric_token_scenarios import (
    coverage_complete,
    isolated_scenario_names,
    missing_scenarios,
    scenario_names,
)
from memory_fabric_usage_extract import collect_samples
from memory_fabric_usage_quality import usage_quality


def token_coverage(
    *,
    operations_input: str,
    usage_input: list[str] | None = None,
    inline_json: str = "",
    plugin_eval_output: str = "",
    min_samples: int = 5,
    min_scenarios: int = 3,
) -> dict[str, Any]:
    operation_names = operation_scenarios(operations_input)
    samples = collect_samples(usage_input or [], inline_json)
    token_scenarios = scenario_names(samples)
    isolated_scenarios = isolated_scenario_names(samples)
    missing = missing_scenarios(operation_names, token_scenarios)
    missing_isolated = missing_scenarios(operation_names, isolated_scenarios)
    quality = usage_quality(samples, min_samples=min_samples, min_scenarios=min_scenarios)
    complete = coverage_complete(operation_names, missing, missing_isolated, quality)
    report = coverage_report(
        operation_names,
        token_scenarios,
        isolated_scenarios,
        missing,
        missing_isolated,
        samples,
        quality,
        complete,
    )
    if plugin_eval_output:
        report["plugin_eval_export"] = guarded_export(samples, plugin_eval_output, complete)
    return report


def operation_scenarios(path: str) -> list[str]:
    names = set()
    for line in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict) and payload.get("type") == "memory_fabric.operation.done":
            names.add(str(payload.get("scenario", "")).strip())
    return sorted(name for name in names if name)
