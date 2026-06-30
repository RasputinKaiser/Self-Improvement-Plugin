from __future__ import annotations
from typing import Any

from memory_fabric_answer_eval_suite_metrics import minimum_metric, sum_metric
from memory_fabric_reasoning_eval_suite_ids import (
    answer_contract_failed_case_ids,
    causal_policy_failed_case_ids,
    conflict_failed_case_ids,
    failed_case_ids,
    missing_evidence_case_ids,
    proof_boundary_failed_case_ids,
)
from memory_fabric_reasoning_eval_suite_categories import (
    suite_next_checks,
)


def suite_result(results: list[dict[str, Any]], claim_boundary: str) -> dict[str, Any]:
    failed = [result for result in results if not result["ok"]]
    causal_lift = causal_memory_lift_cases(results)
    attribution_counts = memory_attribution_counts(results)
    ok = bool(results) and not failed
    return {
        "ok": ok,
        "status": "reasoning_eval_suite_passed" if ok else "reasoning_eval_suite_failed",
        "claim_boundary": claim_boundary,
        "case_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "minimum_score_delta": minimum_metric(results, "score_delta"),
        "total_cited_evidence_count": sum_metric(results, "cited_evidence_count"),
        "total_missing_evidence_count": sum_metric(results, "missing_evidence_count"),
        "causal_memory_lift_case_count": len(causal_lift),
        "causal_memory_lift_case_ids": [result["case_id"] for result in causal_lift],
        "causal_memory_lift_ready": bool(causal_lift),
        "memory_attribution_status_counts": attribution_counts,
        "causal_memory_attribution_case_count": attribution_counts.get("ready_causal_memory_attribution", 0),
        "descriptive_memory_attribution_case_count": attribution_counts.get(
            "ready_descriptive_memory_attribution",
            0,
        ),
        "total_causal_evidence_path_count": sum_metric(results, "causal_evidence_path_count"),
        "total_causal_evidence_missing_node_count": sum_metric(results, "causal_evidence_missing_node_count"),
        "failed_case_ids": failed_case_ids(results),
        "proof_boundary_failed_case_ids": proof_boundary_failed_case_ids(results),
        "missing_evidence_case_ids": missing_evidence_case_ids(results),
        "causal_policy_failed_case_ids": causal_policy_failed_case_ids(results),
        "answer_contract_failed_case_ids": answer_contract_failed_case_ids(results),
        "conflict_failed_case_ids": conflict_failed_case_ids(results),
        "recommended_next_checks": suite_next_checks(results),
        "cases": results,
    }


def causal_memory_lift_cases(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        result
        for result in results
        if result["ok"]
        and result.get("memory_attribution_status") == "ready_causal_memory_attribution"
        and result.get("causal_evidence_status") == "causal_paths_ready"
        and int(result.get("causal_evidence_path_count", 0)) > 0
        and int(result.get("score_delta", 0)) > 0
        and int(result.get("cited_evidence_count", 0)) > 0
        and int(result.get("missing_evidence_count", 0)) == 0
        and result.get("proof_boundary_status") != "proof_boundary_blur_detected"
    ]


def memory_attribution_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("memory_attribution_status", "unknown") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts
