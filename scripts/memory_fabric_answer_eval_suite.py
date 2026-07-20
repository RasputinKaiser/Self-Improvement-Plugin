from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_answer_eval import answer_eval
from memory_fabric_answer_eval_suite_checks import suite_next_checks
from memory_fabric_answer_eval_suite_ids import (
    missing_evidence_case_ids,
    missing_terms_case_ids,
    no_evidence_gain_case_ids,
    no_improvement_case_ids,
    proof_boundary_failed_case_ids,
)
from memory_fabric_answer_eval_suite_metrics import minimum_metric, sum_metric
from memory_fabric_answer_eval_suite_parse import suite_cases


CLAIM_BOUNDARY = (
    "Deterministic multi-case lexical answer eval; it proves configured evidence-bound "
    "answer improvement only, not model reasoning."
)


def answer_eval_suite(
    *,
    cases_json: str = "",
    scope: str = "",
    query: str = "",
    per_tier: int = 3,
    path: str | Path | None = None,
) -> dict[str, Any]:
    cases = suite_cases(cases_json)
    results = [
        case_result(index, case, scope=scope, query=query, per_tier=per_tier, path=path)
        for index, case in enumerate(cases)
    ]
    passed = [result for result in results if result["ok"]]
    failed = [result for result in results if not result["ok"]]
    ok = bool(results) and not failed
    return {
        "ok": ok,
        "status": "answer_eval_suite_passed" if ok else "answer_eval_suite_failed",
        "claim_boundary": CLAIM_BOUNDARY,
        "case_count": len(results),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "minimum_score_delta": minimum_metric(results, "score_delta"),
        "total_cited_evidence_delta": sum_metric(results, "cited_evidence_delta"),
        "failed_case_ids": [result["case_id"] for result in failed],
        "no_improvement_case_ids": no_improvement_case_ids(results),
        "missing_terms_case_ids": missing_terms_case_ids(results),
        "missing_evidence_case_ids": missing_evidence_case_ids(results),
        "no_evidence_gain_case_ids": no_evidence_gain_case_ids(results),
        "proof_boundary_failed_case_ids": proof_boundary_failed_case_ids(results),
        "recommended_next_checks": suite_next_checks(results),
        "cases": results,
    }


def case_result(
    index: int,
    case: dict[str, Any],
    *,
    scope: str,
    query: str,
    per_tier: int,
    path: str | Path | None,
) -> dict[str, Any]:
    case_id = str(case.get("id") or f"case_{index + 1}")
    result = answer_eval(
        scope=str(case.get("scope") or scope),
        query=str(case.get("query") or query),
        baseline_answer=str(case.get("baseline_answer", "")),
        memory_answer=str(case.get("memory_answer", "")),
        required_terms=str(case.get("required_terms", "")),
        per_tier=int(case.get("per_tier") or per_tier),
        path=path,
    )
    return {
        "case_id": case_id,
        "ok": result["ok"],
        "status": result["status"],
        "scope": result["scope"],
        "query": result["query"],
        "required_terms": result["required_terms"],
        "score_delta": result["improvement"]["score_delta"],
        "covered_term_delta": result["improvement"]["covered_term_delta"],
        "evidence_reference_delta": result["improvement"]["evidence_reference_delta"],
        "cited_evidence_delta": result["improvement"]["cited_evidence_delta"],
        "proof_boundary_status": result["proof_boundary_status"]["status"],
        "proof_boundary_reasons": result["proof_boundary_status"]["reasons"],
        "memory_missing_terms": result["memory"]["missing_terms"],
        "memory_cited_evidence_count": result["memory_grounding"]["cited_evidence_count"],
        "memory_missing_evidence_count": len(result["memory_grounding"]["missing_evidence_paths"]),
        "selected_evidence_count": result["memory_grounding"]["selected_evidence_count"],
    }
