from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_measurement import DEFAULT_SCENARIOS


def telemetry_contract(output: str = "", min_samples: int = 5, min_scenarios: int = 3) -> dict[str, Any]:
    scenarios = [scenario["id"] for scenario in DEFAULT_SCENARIOS]
    contract = {
        "ok": True,
        "status": "plugin_isolated_telemetry_contract",
        "fabricated": False,
        "minimums": {"samples": min_samples, "scenarios": min_scenarios},
        "required_metadata": required_metadata(scenarios),
        "accepted_event_shape": accepted_event_shape(scenarios[0]),
        "rejected_sources": rejected_sources(),
        "coverage_command": coverage_command(output),
        "claim_boundary": (
            "This contract does not measure tokens. Hosts must attach this metadata to real model usage "
            "before token-coverage exports Plugin Eval observed usage."
        ),
    }
    if output:
        contract["output"] = write_contract(contract, output)
    return contract


def required_metadata(scenarios: list[str]) -> dict[str, Any]:
    return {
        "plugin": "codex-memory-fabric",
        "plugin_isolated": True,
        "isolation": "plugin",
        "scenario": scenarios,
    }


def accepted_event_shape(scenario: str) -> dict[str, Any]:
    return {
        "type": "response.done",
        "metadata": {
            "plugin": "codex-memory-fabric",
            "plugin_isolated": True,
            "isolation": "plugin",
            "scenario": scenario,
        },
        "response": {
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
        },
    }


def rejected_sources() -> list[dict[str, str]]:
    return [
        {
            "source": "memory_fabric.operation.done",
            "reason": "Operational traces contain no model token usage.",
        },
        {
            "source": "codex-rollout-token-count",
            "reason": "Thread-level telemetry is not plugin-isolated.",
        },
        {
            "source": "fixture-token-usage",
            "reason": "Fixture metadata is test-only.",
        },
    ]


def coverage_command(output: str) -> str:
    usage = output or "<plugin-isolated-token-usage.jsonl>"
    return (
        "python3 scripts/memory_fabric.py token-coverage "
        "--operations-input <memory-fabric-ops.jsonl> "
        f"--usage-input {usage} "
        "--plugin-eval-output <plugin-eval-usage.jsonl>"
    )


def write_contract(contract: dict[str, Any], output: str) -> str:
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)
