from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_install_paths import PLUGIN_NAME, read_json


def cache_candidates(cache_root: Path) -> list[Path]:
    if not cache_root.exists():
        return []
    if (cache_root / ".codex-plugin" / "plugin.json").exists():
        return [cache_root]
    if cache_root.name == PLUGIN_NAME:
        return sorted(cache_root.glob("*"))
    if (cache_root / PLUGIN_NAME).exists():
        return sorted((cache_root / PLUGIN_NAME).glob("*"))
    return sorted(cache_root.glob(f"*/{PLUGIN_NAME}/*"))


def cache_entry(path: Path, source_version: str) -> dict[str, Any]:
    manifest = read_json(path / ".codex-plugin" / "plugin.json")
    version = manifest.get("version", "")
    return {
        "path": str(path),
        "version": version,
        "mcp_exists": (path / ".mcp.json").exists(),
        "skill_exists": (path / "skills" / PLUGIN_NAME / "SKILL.md").exists(),
        "version_matches_source": bool(source_version) and version == source_version,
    }


def check_cache(cache_root: Path, source_version: str) -> dict[str, Any]:
    entries = [cache_entry(path, source_version) for path in cache_candidates(cache_root)]
    return {
        "ok": any(item["version_matches_source"] for item in entries),
        "cache_root": str(cache_root),
        "cache_root_exists": cache_root.exists(),
        "candidate_count": len(entries),
        "candidates": entries,
        "source_version": source_version,
    }
