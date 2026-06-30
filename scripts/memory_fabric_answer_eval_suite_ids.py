from __future__ import annotations
from typing import Any


def no_improvement_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["case_id"] for result in results if result["score_delta"] <= 0]


def missing_terms_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["case_id"] for result in results if result["memory_missing_terms"]]


def missing_evidence_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["case_id"] for result in results if result["memory_missing_evidence_count"] > 0]


def no_evidence_gain_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["case_id"] for result in results if result["cited_evidence_delta"] <= 0]


def proof_boundary_failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        result["case_id"]
        for result in results
        if result["proof_boundary_status"] == "proof_boundary_blur_detected"
    ]
