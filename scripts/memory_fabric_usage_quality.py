from __future__ import annotations
from typing import Any


def usage_quality(
    samples: list[dict[str, Any]],
    min_samples: int = 5,
    min_scenarios: int = 3,
) -> dict[str, Any]:
    sample_count = len(samples)
    scenarios = sorted({scenario_name(sample) for sample in samples if scenario_name(sample)})
    reasons = []
    if sample_count < min_samples:
        reasons.append(f"Need at least {min_samples} samples; found {sample_count}.")
    if len(scenarios) < min_scenarios:
        reasons.append(f"Need at least {min_scenarios} scenarios; found {len(scenarios)}.")
    representative = not reasons
    return {
        "representative": representative,
        "status": "representative_usage_available" if representative else "insufficient_observed_usage",
        "sample_count": sample_count,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "minimums": {
            "samples": min_samples,
            "scenarios": min_scenarios,
        },
        "reasons": reasons or ["Observed usage meets the configured representation gate."],
    }


def scenario_name(sample: dict[str, Any]) -> str:
    return str(sample.get("scenario") or sample.get("kind") or "").strip()
