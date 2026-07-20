from __future__ import annotations
from pathlib import Path

from memory_fabric_install_cache import check_cache
from memory_fabric_install_cli import check_cli
from memory_fabric_install_marketplace import check_marketplace
from memory_fabric_install_mcp import check_mcp
from memory_fabric_install_paths import check_source, default_plugin_root
from memory_fabric_install_report import assemble_report
from memory_fabric_live import live_exposure
from memory_fabric_process_audit import process_audit
from memory_fabric_process_lifecycle import process_lifecycle
from memory_fabric_stdio_probe import check_stdio_tools


def doctor(
    plugin_root: str | Path | None = None,
    marketplace_path: str | Path | None = None,
    cache_root: str | Path | None = None,
    codex_command: str = "codex",
    check_cli_surface: bool = True,
    check_stdio_surface: bool = False,
    advertised_tools: list[str] | None = None,
    advertised_surface: dict | None = None,
    advertised_truncated: bool = False,
    process_lines=None,
) -> dict:
    root = resolved_plugin_root(plugin_root)
    source = check_source(root)
    cache = check_cache(
        resolved_cache_root(cache_root),
        source.get("version", ""),
        source.get("plugin_name", ""),
    )
    cli = check_cli(codex_command) if check_cli_surface else skipped_cli()
    mcp = check_mcp(root)
    return assemble_report(
        source=source,
        mcp=mcp,
        stdio=check_stdio_tools(mcp) if check_stdio_surface else skipped_stdio(),
        marketplace=check_marketplace(root, resolved_marketplace_path(marketplace_path)),
        cache=cache,
        cli=cli,
        processes=process_audit(root, process_lines),
        live=live_exposure(advertised_tools, advertised_surface, advertised_truncated),
    )


def resolved_plugin_root(plugin_root: str | Path | None) -> Path:
    if plugin_root:
        return Path(plugin_root).expanduser().resolve()
    return default_plugin_root()


def resolved_marketplace_path(marketplace_path: str | Path | None) -> Path:
    if marketplace_path:
        return Path(marketplace_path).expanduser()
    return Path.home() / ".agents/plugins/marketplace.json"


def resolved_cache_root(cache_root: str | Path | None) -> Path:
    if cache_root:
        return Path(cache_root).expanduser()
    return Path.home() / ".codex/plugins/cache"


def skipped_cli() -> dict:
    return {"ok": None, "skipped": True}


def skipped_stdio() -> dict:
    return {
        "ok": None,
        "status": "skipped",
        "skipped": True,
    }
