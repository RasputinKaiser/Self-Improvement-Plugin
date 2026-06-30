from __future__ import annotations
from typing import Any

from memory_fabric_reasoning_eval_suite_ids import (
    answer_contract_failed_case_ids,
    causal_policy_failed_case_ids,
    conflict_failed_case_ids,
    missing_evidence_case_ids,
    proof_boundary_failed_case_ids,
)


def category_checks(results: list[dict[str, Any]]) -> list[str]:
    checks = []
    if proof_boundary_failed_case_ids(results):
        checks.append("fix_proof_boundary_blur_before_suite_pass")
    if missing_evidence_case_ids(results):
        checks.append("cite_all_suite_reasoning_evidence_paths")
    if causal_policy_failed_case_ids(results):
        checks.append("require_ready_causal_hypotheses_for_suite_causal_answers")
    if answer_contract_failed_case_ids(results):
        checks.append("fix_answer_contract_violations_before_suite_pass")
    if conflict_failed_case_ids(results):
        checks.append("resolve_suite_conflicts_or_supersede_records")
    return checks
