from __future__ import annotations
from typing import Any

from memory_fabric_answer_grounding import cited_evidence_paths


def reasoning_evidence_grounding(answer: str, brief: dict[str, Any]) -> dict[str, Any]:
    paths = selected_evidence_paths(brief)
    cited = cited_evidence_paths(answer, paths)
    return {
        "selected_evidence_paths": paths,
        "cited_evidence_paths": cited,
        "missing_evidence_paths": [path for path in paths if path not in cited],
        "selected_evidence_count": len(paths),
        "cited_evidence_count": len(cited),
        "claim_boundary": "Reasoning evidence grounding checks citation text only.",
    }


def selected_evidence_paths(brief: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for record in brief.get("selected_records", []):
        path = str(record.get("evidence_path", ""))
        if path and path not in paths:
            paths.append(path)
    return paths
