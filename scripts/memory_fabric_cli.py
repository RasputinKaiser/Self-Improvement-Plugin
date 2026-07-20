from __future__ import annotations
import argparse
import json
from pathlib import Path

from memory_fabric_budget_plan import budget_plan
from memory_fabric_answer_eval import answer_eval
from memory_fabric_answer_eval_suite import answer_eval_suite
from memory_fabric_behavior_probe import probe_behavior_receipt
from memory_fabric_live_behavior_cases import behavior_case
from memory_fabric_capture import capture_representative_usage
from memory_fabric_causal_audit import causal_audit
from memory_fabric_causal_hypotheses import causal_hypotheses
from memory_fabric_claim_support import claim_support_audit
from memory_fabric_cli_args import ArgSpec, add_args, arg, arg_specs_from_signature
from memory_fabric_cli_json import read_event_json, read_json_object
from memory_fabric_evidence_audit import evidence_audit
from memory_fabric_evidence_repair import evidence_repair
from memory_fabric_frontier_audit import frontier_audit
from memory_fabric_graph import memory_graph
from memory_fabric_graph_audit import graph_audit
from memory_fabric_hook_health import hook_health
from memory_fabric_install import doctor
from memory_fabric_install_sync import cache_sync
from memory_fabric_measurement import measurement_plan
from memory_fabric_classify import classify_note
from memory_fabric_promotion import assess_promotion
from memory_fabric_projection import project, snapshot
from memory_fabric_projection_audit import audit_projection
from memory_fabric_runtime_fingerprint import runtime_fingerprint
from memory_fabric_schema import schema
from memory_fabric_schema_behavior import schema_behavior_receipt
from memory_fabric_search import search_records
from memory_fabric_release_report import release_report
from memory_fabric_events import record_from_hook_event
from memory_fabric_jsonl import append_record
from memory_fabric_records import make_record
from memory_fabric_readiness_summary import readiness_summary
from memory_fabric_reasoning_brief import reasoning_brief
from memory_fabric_reasoning_eval import reasoning_eval
from memory_fabric_reasoning_eval_suite import reasoning_eval_suite
from memory_fabric_store_audit import store_audit
from memory_fabric_telemetry_audit import telemetry_audit
from memory_fabric_telemetry_contract import telemetry_contract
from memory_fabric_telemetry_status import telemetry_status
from memory_fabric_thread_brief import thread_brief
from memory_fabric_token_coverage import token_coverage
from memory_fabric_usage import usage_report
from sips_runtime.memory_frontier import query_frontier


SPECIAL_ARGS = {
    "schema": [arg("--detail", default="compact")],
    "runtime-fingerprint": [],
    "classify": [arg("text")],
    "record": arg_specs_from_signature(
        make_record,
        "tier title body scope tags provenance_type provenance evidence_path confidence status verify_before_use",
    ),
    "projection-audit": [
        arg("--input", required=True),
        arg("--max-bytes", type=int, default=20000),
        arg("--max-recent", type=int, default=12),
    ],
    "doctor": [
        arg("--plugin-root", default=""),
        arg("--marketplace-path", default=""),
        arg("--cache-root", default=""),
        arg("--codex-command", default="codex"),
        arg("--skip-cli", action="store_true"),
        arg("--check-stdio", action="store_true"),
        arg("--advertised-tool", action="append", default=[]),
        arg("--advertised-surface-json", default=""),
        arg("--advertised-truncated", action="store_true"),
    ],
    "cache-sync": [
        arg("--plugin-root", default=str(Path(__file__).resolve().parents[1])),
        arg("--marketplace-path", default=str(Path.home() / ".agents/plugins/marketplace.json")),
        arg("--cache-root", default=str(Path.home() / ".codex/plugins/cache")),
        arg("--marketplace-name", default=""),
        arg("--execute", action="store_true"),
    ],
    "usage-report": [
        arg("--input", action="append", default=[]),
        arg("--inline-json", default=""),
        arg("--plugin-eval-output", default=""),
        arg("--min-samples", type=int, default=5),
        arg("--min-scenarios", type=int, default=3),
        arg("--allow-nonrepresentative-export", action="store_true"),
    ],
    "capture-representative-usage": [
        arg("--output", default=""),
        arg("--min-scenarios", type=int, default=3),
    ],
    "indexed-frontier": arg_specs_from_signature(
        query_frontier,
        "scope query include_untrusted seed_limit fanout max_depth max_nodes "
        "max_edges max_paths token_budget",
    ),
    "release-report": [
        *arg_specs_from_signature(
            release_report,
            "version plugin_root marketplace_path cache_root projection_input plugin_eval_json benchmark_json "
            "current_doctor_json current_behavior_json hook_health_json expected_doctor_json "
            "evidence_scope strict_evidence require_current_behavior "
            "min_plugin_eval_score max_report_ms sample_limit",
        ),
        arg("--advertised-tool", action="append", default=[]),
        arg("--advertised-surface-json", default=""),
        arg("--advertised-truncated", action="store_true"),
    ],
    "record-hook-event": [
        arg("--event-json", required=True, help="JSON event string, file path, '-' reads stdin.")
    ],
    "serve": [],
}


def emit(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def pick(args, names):
    return {name: getattr(args, name) for name in names.split()}


def optional_path(value):
    return value or None


def command_specs(command):
    if command in SPECIAL_ARGS:
        return SPECIAL_ARGS[command]
    func, names, _ = CALLS[command]
    return arg_specs_from_signature(func, names)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SIPS Memory Fabric CLI.")
    parser.add_argument("--store", default="", help="Override JSONL store path.")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = [*SPECIAL_ARGS, *(name for name in CALLS if name not in SPECIAL_ARGS)]
    for command in commands:
        add_args(sub.add_parser(command), command_specs(command))
    return parser


def command_record(args, store):
    record = make_record(
        **pick(args, "tier title body scope tags provenance_type provenance evidence_path confidence status"),
        verify_before_use=args.verify_before_use,
    )
    return append_record(record, store)


def command_doctor(args, store):
    del store
    return doctor(
        plugin_root=optional_path(args.plugin_root),
        marketplace_path=optional_path(args.marketplace_path),
        cache_root=optional_path(args.cache_root),
        codex_command=args.codex_command,
        check_cli_surface=not args.skip_cli,
        check_stdio_surface=args.check_stdio,
        advertised_tools=args.advertised_tool or None,
        advertised_surface=read_json_object(args.advertised_surface_json),
        advertised_truncated=args.advertised_truncated,
    )


def command_release_report(args, store):
    return release_report(
        store=store,
        **pick(
            args,
            "version projection_input plugin_eval_json benchmark_json current_doctor_json current_behavior_json "
            "hook_health_json expected_doctor_json evidence_scope strict_evidence require_current_behavior "
            "min_plugin_eval_score max_report_ms sample_limit",
        ),
        plugin_root=optional_path(args.plugin_root),
        marketplace_path=optional_path(args.marketplace_path),
        cache_root=optional_path(args.cache_root),
        advertised_tools=args.advertised_tool or None,
        advertised_surface=read_json_object(args.advertised_surface_json),
        advertised_truncated=args.advertised_truncated,
    )


def command_serve(args, store):
    del args, store
    from memory_fabric_mcp import run_server

    run_server()


CALLS = {
    "assess-promotion": (assess_promotion, "tier text provenance_type evidence_path confidence", False),
    "search": (search_records, "query tier scope status provenance_type confidence verify_before_use limit", True),
    "snapshot": (snapshot, "scope status provenance_type confidence verify_before_use limit", True),
    "project": (project, "scope output status provenance_type confidence verify_before_use limit", True),
    "graph": (
        memory_graph,
        "scope query status provenance_type confidence verify_before_use max_nodes max_edges",
        True,
    ),
    "graph-audit": (
        graph_audit,
        "scope query status provenance_type confidence verify_before_use max_nodes max_edges max_isolated_ratio",
        True,
    ),
    "causal-audit": (
        causal_audit,
        "scope query status provenance_type confidence verify_before_use max_nodes max_edges",
        True,
    ),
    "causal-hypotheses": (
        causal_hypotheses,
        "scope query status provenance_type confidence verify_before_use max_nodes max_edges",
        True,
    ),
    "claim-support": (
        claim_support_audit,
        "claims_json scope query status provenance_type confidence verify_before_use limit max_nodes max_edges",
        True,
    ),
    "reasoning-brief": (
        reasoning_brief,
        "claims_json scope query status provenance_type confidence verify_before_use "
        "per_tier max_body_chars max_total_chars max_nodes max_edges",
        True,
    ),
    "reasoning-eval": (
        reasoning_eval,
        "claims_json scope query baseline_answer memory_answer required_terms "
        "status provenance_type confidence verify_before_use per_tier "
        "max_body_chars max_total_chars max_nodes max_edges",
        True,
    ),
    "reasoning-eval-suite": (
        reasoning_eval_suite,
        "cases_json scope query status provenance_type confidence verify_before_use "
        "per_tier max_body_chars max_total_chars max_nodes max_edges",
        True,
    ),
    "store-audit": (store_audit, "max_body_chars sample_limit", True),
    "evidence-audit": (evidence_audit, "scope strict sample_limit", True),
    "evidence-repair": (evidence_repair, "scope receipt_path allowed_root create_indexes sample_limit", True),
    "hook-health": (hook_health, "projection_input evidence_scope strict_evidence sample_limit", True),
    "cache-sync": (cache_sync, "plugin_root marketplace_path cache_root marketplace_name execute", False),
    "behavior-receipt": (
        probe_behavior_receipt,
        "behavior live_output_json required_fields output expected_values_json source_json source_fields",
        False,
    ),
    "behavior-case": (behavior_case, "case output_dir output", False),
    "schema-behavior-receipt": (
        schema_behavior_receipt,
        "live_schema_json source_schema_json fields behavior output",
        False,
    ),
    "budget-plan": (budget_plan, "plugin_eval_json top_n max_deferred_tokens usage_report_json", False),
    "frontier-audit": (
        frontier_audit,
        "release_report_json budget_plan_json schema_json benchmark_json plugin_eval_json "
        "require_live_fresh require_budget_within_target min_plugin_eval_score",
        False,
    ),
    "readiness-summary": (
        readiness_summary,
        "release_report_json frontier_audit_json schema_json store_audit_json evidence_audit_json "
        "current_doctor_json current_behavior_json",
        False,
    ),
    "answer-eval": (answer_eval, "scope query baseline_answer memory_answer required_terms per_tier", True),
    "answer-eval-suite": (answer_eval_suite, "cases_json scope query per_tier", True),
    "measurement-plan": (measurement_plan, "min_samples min_scenarios usage_input plugin_eval_output", False),
    "telemetry-contract": (telemetry_contract, "output min_samples min_scenarios", False),
    "telemetry-audit": (telemetry_audit, "usage_input inline_json min_samples min_scenarios sample_limit", False),
    "telemetry-status": (
        telemetry_status,
        "operations_input usage_input inline_json plugin_eval_output min_samples min_scenarios",
        False,
    ),
    "token-coverage": (
        token_coverage,
        "operations_input usage_input inline_json plugin_eval_output min_samples min_scenarios",
        False,
    ),
    "thread-brief": (
        thread_brief,
        "scope query status confidence provenance_type verify_before_use per_tier max_body_chars max_total_chars",
        True,
    ),
}


def command_generic(args, store):
    func, names, with_path = CALLS[args.command]
    kwargs = pick(args, names)
    if with_path:
        kwargs["path"] = store
    return func(**kwargs)


def command_usage_report(args, store):
    del store
    return usage_report(
        paths=args.input,
        **pick(args, "inline_json plugin_eval_output min_samples min_scenarios allow_nonrepresentative_export"),
    )


def command_capture_usage(args, store):
    return capture_representative_usage(
        output=args.output,
        store=store or "",
        min_scenarios=args.min_scenarios,
    )


def command_indexed_frontier(args, store):
    return query_frontier(
        scope=args.scope,
        query=args.query,
        store=store or None,
        include_untrusted=args.include_untrusted,
        seed_limit=args.seed_limit,
        fanout=args.fanout,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
        max_edges=args.max_edges,
        max_paths=args.max_paths,
        token_budget=args.token_budget,
    )


def command_projection_audit(args, store):
    del store
    return audit_projection(args.input, max_bytes=args.max_bytes, max_recent=args.max_recent)


def handlers():
    return {
        **{name: command_generic for name in CALLS},
        "schema": lambda args, store: schema(detail=args.detail),
        "runtime-fingerprint": lambda args, store: runtime_fingerprint(),
        "classify": lambda args, store: classify_note(args.text),
        "record": command_record,
        "doctor": command_doctor,
        "projection-audit": command_projection_audit,
        "usage-report": command_usage_report,
        "capture-representative-usage": command_capture_usage,
        "indexed-frontier": command_indexed_frontier,
        "release-report": command_release_report,
        "record-hook-event": lambda args, store: record_from_hook_event(read_event_json(args.event_json), store),
        "serve": command_serve,
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    result = handlers()[args.command](args, args.store or None)
    if result is not None:
        emit(result)
    return 0
