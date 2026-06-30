from __future__ import annotations
from collections import Counter
from typing import Any

from memory_fabric_token_isolation import declared_isolated, declared_plugin, plugin_isolated, scenario
from memory_fabric_token_isolation import thread_level_sample
from memory_fabric_usage_extract import collect_samples
from memory_fabric_usage_quality import usage_quality


CLAIM_BOUNDARY = (
    "Telemetry audit classifies supplied token rows only. It does not create token samples, "
    "prove live MCP exposure, or replace token-coverage scenario matching."
)


def telemetry_audit(
    *,
    usage_input: list[str] | None = None,
    inline_json: str = "",
    min_samples: int = 5,
    min_scenarios: int = 3,
    sample_limit: int = 20,
) -> dict[str, Any]:
    samples = collect_samples(usage_input or [], inline_json)
    issue_counts = count_issues(samples)
    isolated = list(filter(plugin_isolated, samples))
    quality = usage_quality(isolated, min_samples=min_samples, min_scenarios=min_scenarios)
    ready = bool(samples) and not issue_counts and bool(quality["representative"])
    return {
        "ok": True,
        "status": "plugin_isolated_telemetry_ready" if ready else status_for(samples, issue_counts),
        "fabricated": False,
        "sample_count": len(samples),
        "plugin_isolated_sample_count": len(isolated),
        "issue_counts": dict(sorted(issue_counts.items())),
        "isolated_usage_quality": quality,
        "samples": list(map(sample_summary, samples[:sample_limit])),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def count_issues(samples: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for sample in samples:
        counts.update(sample_issues(sample))
    return counts


def sample_issues(sample: dict[str, Any]) -> list[str]:
    checks = [
        ("thread_level_token_count", thread_level_sample(sample)),
        ("wrong_or_missing_plugin", not declared_plugin(sample)),
        ("missing_plugin_isolation", not declared_isolated(sample)),
        ("missing_scenario", not scenario(sample)),
    ]
    return [name for name, failed in checks if failed]


def status_for(samples: list[dict[str, Any]], issue_counts: Counter[str]) -> str:
    if not samples:
        return "no_token_telemetry"
    if issue_counts:
        return "telemetry_isolation_issues"
    return "insufficient_plugin_isolated_telemetry"


def sample_summary(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": sample.get("source"),
        "kind": sample.get("kind"),
        "scenario": scenario(sample) or None,
        "plugin": sample.get("plugin"),
        "isolation": sample.get("isolation"),
        "plugin_isolated": sample.get("plugin_isolated"),
        "issues": sample_issues(sample),
    }
