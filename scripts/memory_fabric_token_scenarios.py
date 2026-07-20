from __future__ import annotations
from typing import Any

from memory_fabric_token_isolation import plugin_isolated, scenario


def scenario_names(samples: list[dict[str, Any]]) -> list[str]:
    names = set()
    for sample in samples:
        name = scenario(sample)
        if name:
            names.add(name)
    return sorted(names)


def isolated_scenario_names(samples: list[dict[str, Any]]) -> list[str]:
    names = set()
    for sample in samples:
        add_isolated_scenario(names, sample)
    return sorted(names)


def add_isolated_scenario(names: set[str], sample: dict[str, Any]) -> None:
    if not plugin_isolated(sample):
        return
    name = scenario(sample)
    if name:
        names.add(name)


def missing_scenarios(operation_names: list[str], token_scenarios: list[str]) -> list[str]:
    return [name for name in operation_names if name not in token_scenarios]


def coverage_complete(
    operation_names: list[str],
    missing: list[str],
    missing_isolated: list[str],
    quality: dict[str, Any],
) -> bool:
    return bool(operation_names) and not missing and not missing_isolated and bool(quality["representative"])


def plugin_isolated_sample_count(samples: list[dict[str, Any]]) -> int:
    return sum(1 for sample in samples if plugin_isolated(sample))
