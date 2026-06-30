from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_install_paths import PLUGIN_NAME, read_json


def check_marketplace(plugin_root: Path, marketplace_path: Path) -> dict[str, Any]:
    marketplace = read_json(marketplace_path)
    entry = marketplace_entry(marketplace)
    source = entry.get("source") or {}
    root = marketplace_root(marketplace_path)
    resolved = resolve_source_path(root, source.get("path", ""))
    points_to_source = bool(resolved and resolved == plugin_root.resolve())
    return {
        "ok": bool(entry) and points_to_source,
        "marketplace_path": str(marketplace_path),
        "marketplace_root": str(root),
        "marketplace_exists": marketplace_path.exists(),
        "marketplace_name": marketplace.get("name", ""),
        "entry_exists": bool(entry),
        "entry_source": source.get("source", ""),
        "entry_path": source.get("path", ""),
        "resolved_entry_path": str(resolved) if resolved else "",
        "points_to_source": points_to_source,
        "installation_policy": (entry.get("policy") or {}).get("installation", ""),
        "authentication_policy": (entry.get("policy") or {}).get("authentication", ""),
    }


def marketplace_entry(marketplace: dict[str, Any]) -> dict[str, Any]:
    for item in marketplace.get("plugins") or []:
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME:
            return item
    return {}


def marketplace_root(marketplace_path: Path) -> Path:
    if is_agents_marketplace(marketplace_path):
        return marketplace_path.parent.parent.parent
    return marketplace_path.parent


def is_agents_marketplace(path: Path) -> bool:
    return (
        path.name == "marketplace.json"
        and path.parent.name == "plugins"
        and path.parent.parent.name == ".agents"
    )


def resolve_source_path(root: Path, raw_path: str) -> Path | None:
    return (root / raw_path).resolve() if raw_path else None
