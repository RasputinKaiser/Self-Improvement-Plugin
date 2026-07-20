from __future__ import annotations
from typing import Any

CLI = "python3 scripts/memory_fabric.py"
REAL_USAGE = "<real-token-usage.jsonl>"
PLUGIN_ROOT = "<plugin-root>"

DEFAULT_SCENARIOS = [
    {
        "id": "record-learning-memory",
        "purpose": "Record source-backed Learning Memory.",
        "expected_tiers": ["learning"],
    },
    {
        "id": "search-and-project-work-memory",
        "purpose": "Search memory; build a compact Work projection.",
        "expected_tiers": ["work"],
    },
    {
        "id": "proof-boundary-knowledge",
        "purpose": "Reject weak Knowledge without evidence.",
        "expected_tiers": ["knowledge"],
    },
]


def measurement_plan(
    *,
    min_samples: int = 5,
    min_scenarios: int = 3,
    usage_input: str = "/tmp/codex-memory-fabric-usage.jsonl",
    plugin_eval_output: str = "/tmp/codex-memory-fabric-plugin-eval-usage.jsonl",
) -> dict[str, Any]:
    scenario_count = len(DEFAULT_SCENARIOS)
    return {
        "ok": True,
        "status": "ready_for_representative_usage_capture",
        "fabricated": False,
        "minimums": {
            "samples": min_samples,
            "scenarios": min_scenarios,
        },
        "scenario_count": scenario_count,
        "scenarios": DEFAULT_SCENARIOS,
        "quality_gate": "Requires real sample/scenario coverage.",
        "capture_boundary": (
            "This does not create token telemetry; capture plugin-isolated logs."
        ),
        "commands": commands(min_samples, min_scenarios, usage_input, plugin_eval_output),
    }


def commands(min_samples: int, min_scenarios: int, usage_input: str, plugin_eval_output: str) -> dict[str, str]:
    sample_gate = f"--min-samples {min_samples} --min-scenarios {min_scenarios}"
    usage_report = usage_report_command(usage_input, plugin_eval_output, sample_gate)
    return {
        "telemetry_contract": f"{CLI} telemetry-contract {sample_gate}",
        "representative_operational_capture": f"{CLI} capture-representative-usage --output {usage_input}",
        "token_coverage_gate": (
            f"{CLI} token-coverage "
            f"--operations-input {usage_input} --usage-input {REAL_USAGE} "
            f"--plugin-eval-output {plugin_eval_output} {sample_gate}"
        ),
        "telemetry_audit": f"{CLI} telemetry-audit --usage-input {REAL_USAGE} {sample_gate}",
        "codex_rollout_usage_report": (
            f"{CLI} usage-report --input <codex-rollout.jsonl> "
            f"--plugin-eval-output {plugin_eval_output} {sample_gate}"
        ),
        "codex_rollout_gauge_export": (
            f"{CLI} usage-report --input <codex-rollout.jsonl> "
            f"--plugin-eval-output {plugin_eval_output} {sample_gate} --allow-nonrepresentative-export"
        ),
        "usage_report": usage_report,
        "plugin_eval_with_observed_usage": (
            f"plugin-eval analyze {PLUGIN_ROOT} --format json --observed-usage {plugin_eval_output}"
        ),
        "deterministic_policy_benchmark": (
            "python3 scripts/memory_fabric_benchmark.py --output <benchmark.json>"
        ),
    }


def usage_report_command(usage_input: str, plugin_eval_output: str, sample_gate: str) -> str:
    return (
        f"{CLI} usage-report "
        f"--input {usage_input} --plugin-eval-output {plugin_eval_output} {sample_gate}"
    )
