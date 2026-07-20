#!/usr/bin/env python3
"""Resolve the SIPS-owned Memory Fabric CLI.

SIPS vendors Memory Fabric into this plugin's scripts directory. A legacy cache
fallback is kept only so older local installs fail soft during migration.
"""
from __future__ import annotations

import glob
from pathlib import Path


def find_memory_fabric_cli() -> str | None:
    local = Path(__file__).resolve().parent / "memory_fabric.py"
    if local.exists():
        return str(local)

    cache_root = Path.home() / ".codex" / "plugins" / "cache" / "harness-local" / "harness-self-improvement"
    candidates = sorted(glob.glob(str(cache_root / "*" / "scripts" / "memory_fabric.py")))
    if candidates:
        return candidates[-1]

    legacy_root = Path.home() / ".codex" / "plugins" / "cache" / "ralto-local" / "codex-memory-fabric"
    candidates = sorted(glob.glob(str(legacy_root / "0.1.0*" / "scripts" / "memory_fabric.py")))
    return candidates[-1] if candidates else None
