from __future__ import annotations
from typing import Any


def body_paths(value: Any, prefix: str = "recent") -> list[str]:
    if isinstance(value, dict):
        return dict_body_paths(value, prefix)
    if isinstance(value, list):
        return list_body_paths(value, prefix)
    return []


def dict_body_paths(value: dict[str, Any], prefix: str) -> list[str]:
    paths = [f"{prefix}.body"] if "body" in value else []
    for key, item in value.items():
        paths.extend(body_paths(item, f"{prefix}.{key}"))
    return paths


def list_body_paths(value: list[Any], prefix: str) -> list[str]:
    paths = []
    for index, item in enumerate(value):
        paths.extend(body_paths(item, f"{prefix}[{index}]"))
    return paths
