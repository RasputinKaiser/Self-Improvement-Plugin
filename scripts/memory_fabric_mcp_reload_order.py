from __future__ import annotations
import sys
from pathlib import Path
from typing import Any


PINNED_FIRST = ("memory_fabric_runtime_fingerprint", "memory_fabric_schema")
PINNED_LAST = ("memory_fabric_mcp",)
NEVER_RELOAD = {"memory_fabric_mcp_runtime"}


def reload_order(runtime_module: Any) -> list[str]:
    watched_loaded = loaded_watched_modules(runtime_module)
    return [
        *pinned_modules(watched_loaded, PINNED_FIRST),
        *unwatched_memory_modules(watched_loaded),
        *middle_modules(watched_loaded),
        *pinned_modules(watched_loaded, PINNED_LAST),
    ]


def loaded_watched_modules(runtime_module: Any) -> list[str]:
    return [
        Path(module).stem
        for module in getattr(runtime_module, "WATCHED_MODULES", [])
        if Path(module).stem in sys.modules
    ]


def unwatched_memory_modules(watched_loaded: list[str]) -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if name.startswith("memory_fabric_")
        and name not in watched_loaded
        and name not in {"memory_fabric_mcp", "memory_fabric_mcp_runtime"}
    )


def pinned_modules(watched_loaded: list[str], pins: tuple[str, ...]) -> list[str]:
    return [name for name in pins if name in watched_loaded]


def middle_modules(watched_loaded: list[str]) -> list[str]:
    excluded = {*NEVER_RELOAD, *PINNED_FIRST, *PINNED_LAST}
    return [name for name in watched_loaded if name not in excluded]
