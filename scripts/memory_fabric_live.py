from __future__ import annotations
from typing import Any

from memory_fabric_live_contract import REQUIRED_LIVE_TOOLS, expected_tool_params, surface_contract
from memory_fabric_live_names import canonical_tool_name, present_tools


def live_exposure(
    advertised_tools: list[str] | None = None,
    advertised_surface: dict[str, Any] | None = None,
    advertised_truncated: bool = False,
) -> dict[str, object]:
    if advertised_tools is None and not advertised_surface:
        return unchecked_live()
    advertised_tools = advertised_tools or list(advertised_surface or {})
    return checked_live(advertised_tools, advertised_surface or {}, advertised_truncated)


def checked_live(
    advertised_tools: list[str],
    advertised_surface: dict[str, Any],
    advertised_truncated: bool = False,
) -> dict[str, object]:
    present, aliased = present_tools(REQUIRED_LIVE_TOOLS, advertised_tools)
    missing = [tool for tool in REQUIRED_LIVE_TOOLS if tool not in present]
    surface = surface_contract(advertised_surface, canonical_name)
    if advertised_truncated:
        return truncated_live_report(advertised_tools, present, missing, aliased, surface)
    status = checked_status(missing, aliased, surface)
    return live_report(advertised_tools, present, missing, aliased, status, surface)


def checked_status(
    missing: list[str],
    aliased: dict[str, list[str]],
    surface: dict[str, Any],
) -> str:
    status = live_status(missing, aliased)
    surface_stale = surface["surface_checked"] and not surface["ok"] and status == "available"
    return "stale_tool_schema" if surface_stale else status


def live_report(
    advertised_tools: list[str],
    present: list[str],
    missing: list[str],
    aliased: dict[str, list[str]],
    status: str,
    surface: dict[str, Any],
) -> dict[str, object]:
    return {
        "ok": live_ok(missing, surface),
        "status": status,
        "tool_exposure_checked": True,
        "surface_checked": surface["surface_checked"],
        "required_tools": REQUIRED_LIVE_TOOLS,
        "expected_tool_params": expected_tool_params(),
        "present_tools": present,
        "missing_tools": missing,
        "exact_missing_tools": sorted(aliased),
        "aliased_tools": aliased,
        "advertised_count": len(advertised_tools),
        "surface": surface,
    }


def truncated_live_report(
    advertised_tools: list[str],
    present: list[str],
    unverified: list[str],
    aliased: dict[str, list[str]],
    surface: dict[str, Any],
) -> dict[str, object]:
    return {
        "ok": None,
        "status": "surface_truncated_unproven",
        "tool_exposure_checked": False,
        "partial_tool_exposure_checked": True,
        "reason": "Advertised tools came from a bounded discovery result; absence is unproven.",
        "required_tools": REQUIRED_LIVE_TOOLS,
        "expected_tool_params": expected_tool_params(),
        "present_tools": present,
        "missing_tools": [],
        "unverified_tools": unverified,
        "exact_missing_tools": sorted(aliased),
        "aliased_tools": aliased,
        "advertised_count": len(advertised_tools),
        "advertised_truncated": True,
        "surface_checked": surface["surface_checked"],
        "surface": surface,
    }


def live_ok(missing: list[str], surface: dict[str, Any]) -> bool:
    return not missing and bool(surface["ok"])


def unchecked_live() -> dict[str, object]:
    return {
        "ok": None,
        "status": "unproven",
        "tool_exposure_checked": False,
        "reason": (
            "This doctor can inspect local layers by itself, but live MCP exposure "
            "requires advertised tool names from the current Codex host session."
        ),
        "required_tools": REQUIRED_LIVE_TOOLS,
        "expected_tool_params": expected_tool_params(),
    }


def canonical_name(advertised: str) -> str:
    return canonical_tool_name(advertised, REQUIRED_LIVE_TOOLS)


def live_status(missing: list[str], aliased: dict[str, list[str]]) -> str:
    if missing:
        return "missing_tools"
    if aliased:
        return "available_with_host_aliases"
    return "available"
