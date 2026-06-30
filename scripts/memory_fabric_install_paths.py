from __future__ import annotations
import json
from pathlib import Path
from typing import Any


PLUGIN_NAME = "codex-memory-fabric"


def default_plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def check_source(plugin_root: Path) -> dict[str, Any]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    mcp_path = plugin_root / ".mcp.json"
    skill_path = plugin_root / "skills" / PLUGIN_NAME / "SKILL.md"
    manifest = read_json(manifest_path)
    return {
        "ok": source_ok(manifest, mcp_path, skill_path),
        "plugin_root": str(plugin_root),
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "manifest_name": manifest.get("name", ""),
        "version": manifest.get("version", ""),
        "mcp_path": str(mcp_path),
        "mcp_exists": mcp_path.exists(),
        "skill_path": str(skill_path),
        "skill_exists": skill_path.exists(),
    }


def source_ok(manifest: dict[str, Any], mcp_path: Path, skill_path: Path) -> bool:
    return manifest.get("name") == PLUGIN_NAME and mcp_path.exists() and skill_path.exists()

