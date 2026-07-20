from __future__ import annotations
from typing import Any


CLAIM_BOUNDARY = (
    "Source, marketplace, cache, MCP, and CLI diagnostics are local evidence. "
    "Live tool exposure remains unproven until a Codex host session exposes memory_fabric_* tools."
)


def assemble_report(
    source: dict[str, Any],
    mcp: dict[str, Any],
    stdio: dict[str, Any],
    marketplace: dict[str, Any],
    cache: dict[str, Any],
    cli: dict[str, Any],
    processes: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": report_ok(source, mcp, marketplace, cache, stdio, live),
        "status": status(cache, stdio, live),
        "source": source,
        "mcp": mcp,
        "stdio": stdio,
        "marketplace": marketplace,
        "cache": cache,
        "cli": cli,
        "processes": processes,
        "live": live,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def local_layers_ok(*layers: dict[str, Any]) -> bool:
    return all(bool(layer.get("ok")) for layer in layers)


def report_ok(*layers: dict[str, Any]) -> bool:
    local_layers = layers[:-2]
    stdio = layers[-2]
    live = layers[-1]
    if stdio.get("ok") is False:
        return False
    if live.get("tool_exposure_checked"):
        return local_layers_ok(*local_layers) and bool(live.get("ok"))
    return local_layers_ok(*local_layers)


def status(cache: dict[str, Any], stdio: dict[str, Any], live: dict[str, Any]) -> str:
    if stdio.get("ok") is False:
        return str(stdio.get("status", "stdio_probe_failed"))
    if live.get("tool_exposure_checked"):
        return checked_live_status(live)
    return "ready_for_live_thread_check" if cache.get("ok") else "not_installed_in_cache"


def checked_live_status(live: dict[str, Any]) -> str:
    if live.get("status") == "surface_truncated_unproven":
        return "live_surface_truncated_unproven"
    if not live.get("ok"):
        if live.get("status") == "stale_tool_schema":
            return "live_tool_schema_stale"
        return "live_tools_missing"
    if live.get("status") == "available_with_host_aliases":
        return "live_tools_available_with_host_aliases"
    return "live_tools_available"
