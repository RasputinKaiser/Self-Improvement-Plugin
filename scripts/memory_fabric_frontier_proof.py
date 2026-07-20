from __future__ import annotations
from typing import Any

from memory_fabric_frontier_common import gate, int_value


EXPECTED_REASONING_CONTRACTS = {
    "memory_fabric_graph_audit": "graph_audit.v5",
    "memory_fabric_reasoning_brief": "reasoning_brief.v9",
    "memory_fabric_reasoning_eval": "reasoning_eval.v6",
    "memory_fabric_reasoning_eval_suite": "reasoning_eval_suite.v5",
    "memory_fabric_claim_support": "claim_support.v2",
    "memory_fabric_causal_audit": "causal_audit.v2",
}


def contract_gate(schema: dict[str, Any]) -> dict[str, Any]:
    if not schema:
        return gate(False, "schema_missing", "Attach a source schema receipt.")
    mismatches = contract_mismatches(schema.get("tool_contracts", {}))
    return gate(
        not mismatches,
        "graph_reasoning_contracts_ready" if not mismatches else "graph_reasoning_contracts_attention",
        contract_summary(mismatches),
        {"mismatches": mismatches, "expected_contracts": EXPECTED_REASONING_CONTRACTS},
    )


def contract_mismatches(contracts: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches = []
    for name, version in EXPECTED_REASONING_CONTRACTS.items():
        actual = contracts.get(name, {}).get("behavior_contract_version")
        if actual != version:
            mismatches.append({"tool": name, "expected": version, "actual": actual})
    return mismatches


def contract_summary(mismatches: list[dict[str, Any]]) -> str:
    if not mismatches:
        return "Source schema exposes the expected graph/reasoning contracts."
    return "Source schema is missing required graph/reasoning contracts."


def benchmark_gate(benchmark: dict[str, Any]) -> dict[str, Any]:
    if not benchmark:
        return gate(False, "benchmark_missing", "Attach a benchmark receipt.")
    failed = int(benchmark.get("failed", 0) or 0)
    causal_cases = find_int(benchmark, "causal_memory_attribution_case_count")
    ok = bool(benchmark.get("ok")) and failed == 0 and causal_cases > 0
    return gate(
        ok,
        "reasoning_eval_proof_ready" if ok else "reasoning_eval_proof_attention",
        benchmark_summary(ok),
        {
            "passed": int(benchmark.get("passed", 0) or 0),
            "failed": failed,
            "scenario_count": benchmark.get("scenario_count", 0),
            "causal_memory_attribution_case_count": causal_cases,
        },
    )


def benchmark_summary(ok: bool) -> str:
    if ok:
        return "Benchmark proves passing cases plus at least one causal memory attribution case."
    return "Benchmark must pass with causal memory attribution coverage."


def find_int(value: Any, key: str) -> int:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            found = int_value(current.get(key))
            if found:
                return found
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return 0
