from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

from memory_fabric_install import doctor
from memory_fabric_install_sync import cache_sync
from memory_fabric_mcp_args import csv_items, optional_json_object


def register_install_tools(mcp: Any, dumps: Callable[[object], str]) -> None:
    @mcp.tool()
    def memory_fabric_doctor(
        plugin_root: str = "",
        marketplace_path: str = "",
        cache_root: str = "",
        codex_command: str = "codex",
        check_cli_surface: bool = True,
        check_stdio_surface: bool = False,
        advertised_tools_csv: str = "",
        advertised_surface_json: str = "",
        advertised_truncated: bool = False,
    ) -> str:
        """Diagnose source, marketplace, cache, MCP, CLI, and live-exposure boundaries."""
        return dumps(
            doctor(
                plugin_root=plugin_root or None,
                marketplace_path=marketplace_path or None,
                cache_root=cache_root or None,
                codex_command=codex_command,
                check_cli_surface=check_cli_surface,
                check_stdio_surface=check_stdio_surface,
                advertised_tools=csv_items(advertised_tools_csv) or None,
                advertised_surface=optional_json_object(advertised_surface_json),
                advertised_truncated=advertised_truncated,
            )
        )

    @mcp.tool()
    def memory_fabric_cache_sync(
        plugin_root: str = "",
        marketplace_path: str = "",
        cache_root: str = "",
        marketplace_name: str = "",
        execute: bool = False,
    ) -> str:
        """Dry-run or execute guarded source-to-cache sync; live exposure remains separate."""
        return dumps(
            cache_sync(
                plugin_root=plugin_root or str(Path.home() / "plugins/codex-memory-fabric"),
                marketplace_path=marketplace_path or str(Path.home() / ".agents/plugins/marketplace.json"),
                cache_root=cache_root or str(Path.home() / ".codex/plugins/cache"),
                marketplace_name=marketplace_name,
                execute=execute,
            )
        )
