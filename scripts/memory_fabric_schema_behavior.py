from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_behavior_probe import MISSING, payload, value_at
from memory_fabric_behavior_receipts import split_paths
from memory_fabric_schema import schema


DEFAULT_SCHEMA_FIELDS = ",".join(
    [
        "plugin_version",
        "runtime_contract.detects_runtime_import_staleness",
        "runtime_contract.mcp_runtime_autoreloads_stale_imports",
        "runtime_contract.mcp_runtime_dispatches_fresh_callables",
        "runtime_contract.mcp_runtime_dispatch_loads_runtime_module_each_call",
        "runtime_contract.mcp_runtime_exposes_last_reload_receipt",
        "runtime_contract.mcp_runtime_reload_contract_version",
        "runtime_contract.exposes_runtime_process_context",
        "runtime_contract.exposes_module_import_and_current_paths",
        "runtime_contract.runtime_fingerprint_contract_version",
        "runtime_reload.contract_version",
        "runtime_reload.status",
        "runtime_reload.reload_attempted",
        "runtime_reload.after_status",
        "runtime_fingerprint.contract_version",
        "runtime_fingerprint.status",
        "runtime_fingerprint.process.python_executable",
        "runtime_fingerprint.module_root",
        "runtime_fingerprint.module_count",
        "runtime_fingerprint.stale_module_count",
        "tool_contracts.memory_fabric_graph.behavior_contract_version",
        "tool_contracts.memory_fabric_graph.emits_decision_context_summary",
        "tool_contracts.memory_fabric_graph.emits_path_use_ledger",
        "tool_contracts.memory_fabric_graph.treats_decision_edges_as_context_not_proof",
        "tool_contracts.memory_fabric_thread_brief.behavior_contract_version",
        "tool_contracts.memory_fabric_thread_brief.emits_task_profile_cue_ledger",
        "tool_contracts.memory_fabric_thread_brief.emits_decision_context_summary",
        "tool_contracts.memory_fabric_thread_brief.gates_pricing_until_candidate_match_and_visual_comparison",
        "tool_contracts.memory_fabric_graph_audit.behavior_contract_version",
        "tool_contracts.memory_fabric_graph_audit.emits_decision_context_summary",
        "tool_contracts.memory_fabric_graph_audit.emits_path_use_ledger",
        "tool_contracts.memory_fabric_graph_audit.detects_scoped_conflicts_outside_query_selection",
        "tool_contracts.memory_fabric_claim_support.behavior_contract_version",
        "tool_contracts.memory_fabric_claim_support.gates_causal_claims_on_causal_paths",
        "tool_contracts.memory_fabric_claim_support.reports_causal_required_citation_paths",
        "tool_contracts.memory_fabric_claim_support.reports_causal_missing_evidence_nodes",
        "tool_contracts.memory_fabric_reasoning_brief.behavior_contract_version",
        "tool_contracts.memory_fabric_reasoning_brief.carries_graph_decision_context",
        "tool_contracts.memory_fabric_reasoning_brief.carries_graph_path_use_ledger",
        "tool_contracts.memory_fabric_reasoning_brief.emits_causal_evidence_summary",
        "tool_contracts.memory_fabric_reasoning_brief.carries_claim_support_causal_trace",
        "tool_contracts.memory_fabric_reasoning_brief.reports_causal_evidence_citation_paths",
        "tool_contracts.memory_fabric_reasoning_brief.reports_causal_evidence_missing_nodes",
        "tool_contracts.memory_fabric_reasoning_brief.carries_task_profile_cue_ledger",
        "tool_contracts.memory_fabric_reasoning_brief.emits_computed_answer_contract",
        "tool_contracts.memory_fabric_reasoning_brief.blocks_task_gated_actions",
        "tool_contracts.memory_fabric_reasoning_eval.behavior_contract_version",
        "tool_contracts.memory_fabric_reasoning_eval.checks_answer_contract_compliance",
        "tool_contracts.memory_fabric_reasoning_eval.rejects_answer_contract_blocked_actions",
        "tool_contracts.memory_fabric_reasoning_eval.rejects_proof_boundary_blur",
        "tool_contracts.memory_fabric_reasoning_eval.requires_ready_causal_hypotheses_for_causal_answers",
        "tool_contracts.memory_fabric_reasoning_eval.reports_reasoning_brief_conflict_counts",
        "tool_contracts.memory_fabric_reasoning_eval.emits_memory_attribution_ledger",
        "tool_contracts.memory_fabric_reasoning_eval_suite.behavior_contract_version",
        "tool_contracts.memory_fabric_reasoning_eval_suite.requires_all_cases_to_pass",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_causal_memory_lift_cases",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_causal_evidence_path_counts",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_memory_attribution_status_counts",
        "tool_contracts.memory_fabric_reasoning_eval_suite.counts_causal_vs_descriptive_memory_attribution",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_proof_boundary_failed_cases",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_missing_evidence_cases",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_causal_policy_failed_cases",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_answer_contract_failed_cases",
        "tool_contracts.memory_fabric_reasoning_eval_suite.reports_conflict_failed_cases",
        "tool_contracts.memory_fabric_causal_audit.behavior_contract_version",
        "tool_contracts.memory_fabric_causal_audit.emits_causal_evidence_ledger",
        "tool_contracts.memory_fabric_causal_audit.requires_causal_citation_paths",
        "tool_contracts.memory_fabric_causal_audit.flags_missing_evidence_nodes",
        "tool_contracts.memory_fabric_answer_eval.behavior_contract_version",
        "tool_contracts.memory_fabric_answer_eval.emits_proof_boundary_status",
        "tool_contracts.memory_fabric_answer_eval.rejects_context_only_memory_as_proof",
        "tool_contracts.memory_fabric_answer_eval_suite.behavior_contract_version",
        "tool_contracts.memory_fabric_answer_eval_suite.requires_all_cases_to_improve",
        "tool_contracts.memory_fabric_answer_eval_suite.reports_no_improvement_cases",
        "tool_contracts.memory_fabric_answer_eval_suite.reports_missing_terms_cases",
        "tool_contracts.memory_fabric_answer_eval_suite.reports_missing_evidence_cases",
        "tool_contracts.memory_fabric_answer_eval_suite.reports_no_evidence_gain_cases",
        "tool_contracts.memory_fabric_answer_eval_suite.reports_proof_boundary_failed_cases",
        "tool_contracts.memory_fabric_release_report.handles_truncated_advertised_live_surfaces",
        "tool_contracts.memory_fabric_release_report.distinguishes_stdio_complete_from_host_advertisement_stale",
    ]
)


def schema_behavior_receipt(
    live_schema_json: str,
    source_schema_json: str = "",
    fields: str = DEFAULT_SCHEMA_FIELDS,
    behavior: str = "memory_fabric_schema_contract",
    output: str = "",
) -> dict[str, Any]:
    live = payload(live_schema_json)
    source = payload(source_schema_json) if source_schema_json else schema()
    checked = split_paths(fields)
    missing = missing_live_fields(live, checked)
    mismatched = mismatched_live_fields(source, live, checked)
    ok = not missing and not mismatched
    receipt = schema_receipt_payload(
        ok=ok,
        behavior=behavior,
        checked=checked,
        missing=missing,
        mismatched=mismatched,
        source=source,
        live=live,
    )
    write_receipt(output, receipt)
    return receipt


def missing_live_fields(live: dict[str, Any], checked: list[str]) -> list[str]:
    return [field for field in checked if value_at(live, field) is MISSING]


def mismatched_live_fields(
    source: dict[str, Any],
    live: dict[str, Any],
    checked: list[str],
) -> list[str]:
    return [
        field
        for field in checked
        if source_has_field(source, field) and value_at(live, field) != value_at(source, field)
    ]


def source_has_field(source: dict[str, Any], field: str) -> bool:
    return value_at(source, field) is not MISSING


def schema_receipt_payload(
    *,
    ok: bool,
    behavior: str,
    checked: list[str],
    missing: list[str],
    mismatched: list[str],
    source: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": "current_live_behavior_ready" if ok else "current_live_behavior_stale",
        "behavior": behavior,
        "checked_fields": checked,
        "missing_current_live_fields": missing,
        "mismatched_current_live_fields": mismatched,
        "expected_plugin_version": str(source.get("plugin_version", "")),
        "current_live_plugin_version": str(live.get("plugin_version", "")),
        "expected_contract_version": contract_summary(source),
        "current_live_contract_version": contract_summary(live),
        "claim_boundary": "Schema behavior receipts compare supplied source and live schema JSON only.",
    }


def write_receipt(output: str, receipt: dict[str, Any]) -> None:
    if output:
        Path(output).expanduser().write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def contract_summary(data: dict[str, Any]) -> str:
    contracts = data.get("tool_contracts", {})
    if not isinstance(contracts, dict):
        return ""
    return ",".join(
        f"{name}:{value.get('behavior_contract_version', '')}"
        for name, value in sorted(contracts.items())
        if isinstance(value, dict) and value.get("behavior_contract_version")
    )
