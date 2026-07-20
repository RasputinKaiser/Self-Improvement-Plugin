from __future__ import annotations
from typing import Any

from memory_fabric_answer_eval_suite_ids import (
    missing_evidence_case_ids,
    missing_terms_case_ids,
    no_evidence_gain_case_ids,
    no_improvement_case_ids,
    proof_boundary_failed_case_ids,
)


def suite_next_checks(results: list[dict[str, Any]]) -> list[str]:
    checks = []
    if no_improvement_case_ids(results):
        checks.append("improve_memory_answers_before_suite_pass")
    if missing_terms_case_ids(results):
        checks.append("cover_required_terms_before_suite_pass")
    if missing_evidence_case_ids(results):
        checks.append("cite_selected_evidence_paths_before_suite_pass")
    if no_evidence_gain_case_ids(results):
        checks.append("increase_cited_evidence_delta_before_suite_pass")
    if proof_boundary_failed_case_ids(results):
        checks.append("fix_answer_eval_proof_boundary_blur_before_suite_pass")
    return checks
