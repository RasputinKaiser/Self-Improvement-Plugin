from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

from memory_fabric_live_contract_loader import load_surface_contract
from memory_fabric_live_params import param_names


REQUIRED_LIVE_TOOLS, EXPECTED_TOOL_PARAMS = load_surface_contract(Path(__file__))


def expected_tool_params() -> dict[str, list[str]]:
    return {tool: sorted(params) for tool, params in EXPECTED_TOOL_PARAMS.items()}


def surface_contract(
    advertised_surface: dict[str, Any],
    canonical_tool_name: Callable[[str], str],
) -> dict[str, Any]:
    if not advertised_surface:
        return {"ok": True, "surface_checked": False}
    normalized = normalize_surface(advertised_surface, canonical_tool_name)
    missing_params = missing_surface_params(normalized)
    unchecked = sorted(tool for tool in EXPECTED_TOOL_PARAMS if tool not in normalized)
    return {
        "ok": not missing_params and not unchecked,
        "surface_checked": True,
        "checked_tools": sorted(normalized),
        "missing_params": missing_params,
        "unchecked_tools": unchecked,
    }


def normalize_surface(
    advertised_surface: dict[str, Any],
    canonical_tool_name: Callable[[str], str],
) -> dict[str, set[str]]:
    normalized = {}
    for tool_name, definition in advertised_surface.items():
        canonical = canonical_tool_name(tool_name)
        if canonical:
            normalized[canonical] = param_names(definition)
    return normalized


def missing_surface_params(normalized: dict[str, set[str]]) -> dict[str, list[str]]:
    return {
        tool: sorted(expected - normalized.get(tool, set()))
        for tool, expected in EXPECTED_TOOL_PARAMS.items()
        if tool in normalized and not expected.issubset(normalized.get(tool, set()))
    }
