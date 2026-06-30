from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from typing import Any

from memory_fabric_live_contract import REQUIRED_LIVE_TOOLS


DEFAULT_TIMEOUT_SECONDS = 8.0


def check_stdio_tools(mcp: dict[str, Any], timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    if not mcp.get("ok"):
        return unavailable_mcp_config()

    client = load_mcp_client()
    if client["status"] != "available":
        return client

    command, script = stdio_command_and_script(mcp)
    if not Path(script).exists():
        return missing_server_script(script)

    ClientSession = client["ClientSession"]
    StdioServerParameters = client["StdioServerParameters"]
    stdio_client = client["stdio_client"]

    async def list_tool_names() -> list[str]:
        params = StdioServerParameters(command=command, args=[script, "serve"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
        return sorted(tool.name for tool in tools.tools)

    try:
        names = run_probe(list_tool_names(), timeout_seconds)
    except Exception as exc:
        return failed_stdio_probe(command, script, exc)

    return stdio_tool_report(command, script, names)


def unavailable_mcp_config() -> dict[str, Any]:
    return {
        "ok": False,
        "status": "mcp_config_unavailable",
        "reason": "MCP config failed local checks.",
    }


def load_mcp_client() -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:  # pragma: no cover - depends on host runtime packages.
        return {
            "ok": None,
            "status": "mcp_package_unavailable",
            "reason": f"mcp package unavailable in this Python runtime: {exc}",
        }
    return {
        "status": "available",
        "ClientSession": ClientSession,
        "StdioServerParameters": StdioServerParameters,
        "stdio_client": stdio_client,
    }


def stdio_command_and_script(mcp: dict[str, Any]) -> tuple[str, str]:
    return str(mcp["command"]), str(mcp["script"])


def missing_server_script(script: str) -> dict[str, Any]:
    return {"ok": False, "status": "server_script_missing", "script": script}


def failed_stdio_probe(command: str, script: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "stdio_probe_failed",
        "command": command,
        "script": script,
        "error": str(exc),
    }


def stdio_tool_report(command: str, script: str, names: list[str]) -> dict[str, Any]:
    missing = [tool for tool in REQUIRED_LIVE_TOOLS if tool not in names]
    extra = [tool for tool in names if tool not in REQUIRED_LIVE_TOOLS]
    return {
        "ok": not missing,
        "status": "stdio_tools_complete" if not missing else "stdio_tools_missing",
        "command": command,
        "script": script,
        "tool_count": len(names),
        "required_tool_count": len(REQUIRED_LIVE_TOOLS),
        "tools": names,
        "missing_tools": missing,
        "extra_tools": extra,
        "claim_boundary": "Stdio is not host.",
    }


def run_probe(coro: Any, timeout_seconds: float) -> Any:
    async def bounded() -> Any:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(bounded())

    result: dict[str, Any] = {}

    def target() -> None:
        try:
            result["value"] = asyncio.run(bounded())
        except Exception as exc:  # pragma: no cover - exercised only in nested-loop hosts.
            result["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_seconds + 1)
    if thread.is_alive():
        raise TimeoutError(f"stdio probe exceeded {timeout_seconds} seconds")
    if "error" in result:
        raise result["error"]
    return result["value"]
