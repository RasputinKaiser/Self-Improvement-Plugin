from __future__ import annotations
from typing import Any


def scenario(sample: dict[str, Any]) -> str:
    return str(sample.get("scenario") or sample.get("kind") or "").strip()


def plugin_isolated(sample: dict[str, Any]) -> bool:
    return not thread_level_sample(sample) and declared_plugin(sample) and declared_isolated(sample)


def thread_level_sample(sample: dict[str, Any]) -> bool:
    return sample.get("kind") == "codex.token_count.last"


def declared_plugin(sample: dict[str, Any]) -> bool:
    return str(sample.get("plugin") or "").strip() == "codex-memory-fabric"


def declared_isolated(sample: dict[str, Any]) -> bool:
    isolation = str(sample.get("isolation") or "").strip()
    return sample.get("plugin_isolated") is True or isolation in {"plugin", "plugin-isolated", "plugin_isolated"}

