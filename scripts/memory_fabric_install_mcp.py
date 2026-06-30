from __future__ import annotations
from pathlib import Path

from memory_fabric_install_paths import PLUGIN_NAME, read_json


def check_mcp(plugin_root: Path) -> dict[str, object]:
    mcp_path = plugin_root / ".mcp.json"
    server = mcp_server(mcp_path)
    command = server_command(server)
    script = server_script(server)
    command_path = command_path_value(command)
    command_ready = command_path_ready(command_path)
    script_ready = script_path_ready(script)
    return mcp_report(
        ok=command_ready and script_ready,
        mcp_path=mcp_path,
        server=server,
        command=command,
        command_path=command_path,
        script=script,
    )


def mcp_server(mcp_path: Path) -> dict:
    servers = read_json(mcp_path).get("mcpServers") or {}
    return servers.get(PLUGIN_NAME) or {}


def server_command(server: dict) -> str:
    return str(server.get("command", ""))


def server_script(server: dict) -> Path | None:
    args = server.get("args") or []
    return Path(args[0]).expanduser() if args else None


def command_path_value(command: str) -> Path | None:
    return Path(command) if command else None


def mcp_report(
    *,
    ok: bool,
    mcp_path: Path,
    server: dict,
    command: str,
    command_path: Path | None,
    script: Path | None,
) -> dict[str, object]:
    return {
        "ok": ok,
        "mcp_path": str(mcp_path),
        "server_exists": bool(server),
        "command": command,
        "command_absolute": bool(command_path and command_path.is_absolute()),
        "command_exists": bool(command_path and command_path.exists()),
        "script": str(script) if script else "",
        "script_exists": bool(script and script.exists()),
    }


def mcp_ok(command_path: Path | None, script: Path | None) -> bool:
    return command_path_ready(command_path) and script_path_ready(script)


def command_path_ready(command_path: Path | None) -> bool:
    return bool(command_path and command_path.is_absolute() and command_path.exists())


def script_path_ready(script: Path | None) -> bool:
    return bool(script and script.exists())
