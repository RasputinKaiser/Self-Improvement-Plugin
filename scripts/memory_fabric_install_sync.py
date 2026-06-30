from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_install_cache import check_cache
from memory_fabric_install_copy import copy_source
from memory_fabric_install_fingerprint import compare_directories
from memory_fabric_install_marketplace import check_marketplace
from memory_fabric_install_paths import check_source
from memory_fabric_install_sync_result import sync_preflight, sync_result


def cache_sync(
    plugin_root: str | Path,
    marketplace_path: str | Path,
    cache_root: str | Path,
    marketplace_name: str = "",
    execute: bool = False,
) -> dict[str, Any]:
    root = Path(plugin_root).expanduser().resolve()
    marketplace = Path(marketplace_path).expanduser()
    cache = Path(cache_root).expanduser()
    source = check_source(root)
    market = check_marketplace(root, marketplace)
    version = source.get("version", "")
    target = sync_target(cache, market.get("marketplace_name", ""), marketplace_name, version)
    preflight = sync_preflight(source, market, target, version)
    if execute and preflight["reasons"] == ["target_already_exists"]:
        comparison = compare_directories(root, target)
        if not comparison["ok"]:
            mismatch = {**preflight, "content_match": False, "fingerprint": comparison}
            return sync_result(False, root, target, source, market, mismatch)
        cache_result = check_cache(cache, version)
        idempotent = {**preflight, "content_match": True, "fingerprint": comparison, "idempotent": True}
        return sync_result(False, root, target, source, market, idempotent, cache=cache_result)
    if not execute or not preflight["can_sync"]:
        return sync_result(False, root, target, source, market, preflight)
    copied = copy_source(root, target)
    cache_result = check_cache(cache, version)
    return sync_result(True, root, target, source, market, preflight, copied, cache_result)


def sync_target(cache_root: Path, detected_marketplace: str, override: str, version: str) -> Path:
    marketplace = override or detected_marketplace or "local"
    return cache_root / marketplace / "codex-memory-fabric" / version
