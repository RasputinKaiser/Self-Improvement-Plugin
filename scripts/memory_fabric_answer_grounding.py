from __future__ import annotations
from typing import Any


def answer_grounding(answer: str, brief: dict[str, Any]) -> dict[str, Any]:
    paths = selected_evidence_paths(brief)
    cited = cited_evidence_paths(answer, paths)
    return {
        "selected_evidence_paths": paths,
        "cited_evidence_paths": cited,
        "missing_evidence_paths": [path for path in paths if path not in cited],
        "cited_evidence_count": len(cited),
        "selected_evidence_count": len(paths),
        "claim_boundary": "Evidence-path grounding checks citation text; it does not verify the evidence content.",
    }


def selected_evidence_paths(brief: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for records in brief.get("sections", {}).values():
        for record in records:
            add_path(paths, str(record.get("evidence_path", "")))
    return paths


def add_path(paths: list[str], path: str) -> None:
    if path and path not in paths:
        paths.append(path)


def cited_evidence_paths(answer: str, paths: list[str]) -> list[str]:
    text = answer.lower()
    return [path for path in paths if path.lower() in text]
