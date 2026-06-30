from __future__ import annotations
from typing import Any


CONFLICT_TYPES = {"contradicts", "supersedes"}


def selected_conflict_ref(
    ref: dict[str, str],
    selected_ids: set[str],
    by_id: dict[str, dict[str, Any]],
) -> bool:
    if ref["type"] not in CONFLICT_TYPES or ref["target"] not in by_id:
        return False
    if ref["type"] == "supersedes":
        return ref["target"] in selected_ids
    return bool({ref["source"], ref["target"]} & selected_ids)
