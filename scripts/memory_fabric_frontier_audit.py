from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_frontier_live import live_gate
from memory_fabric_frontier_proof import benchmark_gate, contract_gate
from memory_fabric_frontier_release import budget_gate, plugin_eval_gate, release_gate


FRONTIER_AUDIT_CONTRACT_VERSION = "frontier_audit.v3"
CLAIM_BOUNDARY = (
    "Frontier audit composes existing receipts into a completion gate; it does not replace "
    "source tests, cache sync, current-live behavior checks, or observed usage telemetry."
)


def frontier_audit(
    release_report_json: str = "",
    budget_plan_json: str = "",
    schema_json: str = "",
    benchmark_json: str = "",
    plugin_eval_json: str = "",
    require_live_fresh: bool = True,
    require_budget_within_target: bool = True,
    min_plugin_eval_score: int = 85,
) -> dict[str, Any]:
    release = read_optional_json(release_report_json)
    budget = read_optional_json(budget_plan_json)
    schema = read_optional_json(schema_json)
    benchmark = read_optional_json(benchmark_json)
    plugin_eval = read_optional_json(plugin_eval_json)

    gates = frontier_gates(
        release=release,
        budget=budget,
        schema=schema,
        benchmark=benchmark,
        plugin_eval=plugin_eval,
        require_live_fresh=require_live_fresh,
        require_budget_within_target=require_budget_within_target,
        min_plugin_eval_score=min_plugin_eval_score,
    )
    attention = [name for name, gate in gates.items() if not gate["ok"]]
    completion_claim_allowed = not attention
    return {
        "ok": completion_claim_allowed,
        "status": "frontier_ready" if completion_claim_allowed else "frontier_attention",
        "completion_claim_allowed": completion_claim_allowed,
        "attention": attention,
        "gates": gates,
        "inputs": {
            "release_report_json": release_report_json,
            "budget_plan_json": budget_plan_json,
            "schema_json": schema_json,
            "benchmark_json": benchmark_json,
            "plugin_eval_json": plugin_eval_json,
            "require_live_fresh": bool(require_live_fresh),
            "require_budget_within_target": bool(require_budget_within_target),
            "min_plugin_eval_score": int(min_plugin_eval_score),
        },
        "runtime_contract": {
            "component": "frontier_audit",
            "behavior_contract_version": FRONTIER_AUDIT_CONTRACT_VERSION,
            "composes_existing_receipts": True,
            "blocks_completion_on_live_stale": True,
            "blocks_completion_on_unresolved_budget_pressure": True,
            "requires_checked_live_behavior_receipt": True,
            "accepts_representative_observed_usage_budget_resolution": True,
            "preserves_proof_boundaries": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def frontier_gates(
    release: dict[str, Any],
    budget: dict[str, Any],
    schema: dict[str, Any],
    benchmark: dict[str, Any],
    plugin_eval: dict[str, Any],
    require_live_fresh: bool,
    require_budget_within_target: bool,
    min_plugin_eval_score: int,
) -> dict[str, dict[str, Any]]:
    return {
        "release_boundary": release_gate(release),
        "live_freshness": live_gate(release, schema, require_live_fresh),
        "graph_reasoning_contracts": contract_gate(schema),
        "reasoning_eval_proof": benchmark_gate(benchmark),
        "plugin_eval_gauge": plugin_eval_gate(plugin_eval, min_plugin_eval_score),
        "deferred_budget": budget_gate(budget, require_budget_within_target),
    }


def read_optional_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
