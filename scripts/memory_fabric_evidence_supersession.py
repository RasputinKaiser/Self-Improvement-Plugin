from __future__ import annotations
from typing import Any

from memory_fabric_graph_explicit import explicit_references


def superseded_targets(records: list[dict[str, Any]]) -> dict[str, str]:
    ids = {str(record.get("id", "")) for record in records}
    refs = [
        ref
        for record in records
        for ref in explicit_references(record)
        if ref["type"] == "supersedes" and ref["target"] in ids
    ]
    return {ref["target"]: ref["source"] for ref in refs}
