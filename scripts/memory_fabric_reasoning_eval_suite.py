from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_answer_eval_suite_parse import suite_cases
from memory_fabric_reasoning_eval_suite_case import case_result
from memory_fabric_reasoning_eval_suite_summary import suite_result


CLAIM_BOUNDARY = (
    "Deterministic multi-case reasoning eval; it proves configured evidence-bound "
    "answer improvement only, not model reasoning or external truth."
)


def reasoning_eval_suite(
    *,
    cases_json: str = "",
    scope: str = "",
    query: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    per_tier: int = 3,
    max_body_chars: int = 280,
    max_total_chars: int = 5000,
    max_nodes: int = 24,
    max_edges: int = 80,
    path: str | Path | None = None,
) -> dict[str, Any]:
    cases = suite_cases(cases_json)
    defaults = suite_defaults(
        scope,
        query,
        status,
        confidence,
        provenance_type,
        verify_before_use,
        per_tier,
        max_body_chars,
        max_total_chars,
        max_nodes,
        max_edges,
    )
    return suite_result(
        [case_result(index, case, defaults=defaults, path=path) for index, case in enumerate(cases)],
        CLAIM_BOUNDARY,
    )


def suite_defaults(
    scope: str,
    query: str,
    status: str,
    confidence: str,
    provenance_type: str,
    verify_before_use: str,
    per_tier: int,
    max_body_chars: int,
    max_total_chars: int,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "query": query,
        "status": status,
        "confidence": confidence,
        "provenance_type": provenance_type,
        "verify_before_use": verify_before_use,
        "per_tier": per_tier,
        "max_body_chars": max_body_chars,
        "max_total_chars": max_total_chars,
        "max_nodes": max_nodes,
        "max_edges": max_edges,
    }
