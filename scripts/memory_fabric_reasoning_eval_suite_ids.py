from __future__ import annotations
from typing import Any


def failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [result["case_id"] for result in results if not result["ok"]]


def proof_boundary_failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return case_ids_with_status(results, "proof_boundary_status", "proof_boundary_blur_detected")


def missing_evidence_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        result["case_id"]
        for result in results
        if result["missing_evidence_count"] > 0
    ]


def causal_policy_failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return case_ids_with_status(results, "causal_answer_status", "causal_answer_needs_verification")


def answer_contract_failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        result["case_id"]
        for result in results
        if result.get("answer_contract_blocked_action_count", 0) > 0
    ]


def conflict_failed_case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        result["case_id"]
        for result in results
        if result.get("active_superseded_count", 0) > 0 or result.get("active_contradiction_count", 0) > 0
    ]


def case_ids_with_status(results: list[dict[str, Any]], field: str, value: str) -> list[str]:
    return [result["case_id"] for result in results if result.get(field) == value]
