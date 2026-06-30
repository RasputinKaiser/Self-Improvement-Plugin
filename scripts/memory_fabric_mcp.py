from __future__ import annotations
import json
import importlib
import sys
from typing import Any

from memory_fabric_mcp_args import csv_items, optional, optional_json_object
from memory_fabric_mcp_install import register_install_tools
from memory_fabric_mcp_telemetry import register_telemetry_tool

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - pure helpers are tested without MCP.
    FastMCP = None  # type: ignore[assignment]


def dumps(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def pick(values: dict[str, Any], names: str) -> dict[str, Any]:
    return {name: values[name] for name in names.split()}


def call_fresh(module_name: str, attr: str, *args: Any, **kwargs: Any) -> Any:
    runtime = importlib.import_module("memory_fabric_mcp_runtime")
    func, _receipt = runtime.fresh_callable(module_name, attr)
    return func(*args, **kwargs)


def dumps_path_fresh(module_name: str, attr: str, store: str, values: dict[str, Any], names: str) -> str:
    return dumps(call_fresh(module_name, attr, path=optional(store), **pick(values, names)))


if FastMCP is not None:
    mcp = FastMCP(
        "codex-memory-fabric",
        instructions=(
            "Typed Work, Knowledge, Learning Memory with provenance; repo state is projection."
        ),
    )

    @mcp.tool()
    def memory_fabric_schema(detail: str = "compact") -> str:
        """Schema."""
        return dumps(call_fresh("memory_fabric_schema", "schema", detail=detail))

    @mcp.tool()
    def memory_fabric_runtime_fingerprint() -> str:
        """Deep runtime import fingerprint."""
        return dumps(call_fresh("memory_fabric_runtime_fingerprint", "runtime_fingerprint"))

    @mcp.tool()
    def memory_fabric_record(
        tier: str,
        title: str,
        body: str,
        scope: str = "global",
        tags: str = "",
        provenance_type: str = "user_or_agent_observation",
        provenance: str = "",
        evidence_path: str = "",
        confidence: str = "medium",
        status: str = "active",
        verify_before_use: bool = False,
        store: str = "",
    ) -> str:
        """Record."""
        record = call_fresh(
            "memory_fabric_records",
            "make_record",
            tier=tier,
            title=title,
            body=body,
            scope=scope,
            tags=tags,
            provenance_type=provenance_type,
            provenance=provenance,
            evidence_path=evidence_path,
            confidence=confidence,
            status=status,
            verify_before_use=verify_before_use,
        )
        return dumps(call_fresh("memory_fabric_jsonl", "append_record", record, optional(store)))

    @mcp.tool()
    def memory_fabric_search(
        query: str = "",
        tier: str = "",
        scope: str = "",
        status: str = "",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        limit: int = 10,
        store: str = "",
    ) -> str:
        """Search."""
        return dumps_path_fresh(
            "memory_fabric_search",
            "search_records",
            store,
            locals(),
            "query tier scope status provenance_type confidence verify_before_use limit",
        )

    @mcp.tool()
    def memory_fabric_graph(
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Graph."""
        return dumps_path_fresh(
            "memory_fabric_graph",
            "memory_graph",
            store,
            locals(),
            "scope query status provenance_type confidence verify_before_use max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_graph_audit(
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        max_nodes: int = 24,
        max_edges: int = 80,
        max_isolated_ratio: float = 0.75,
        store: str = "",
    ) -> str:
        """Audit graph."""
        return dumps_path_fresh(
            "memory_fabric_graph_audit",
            "graph_audit",
            store,
            locals(),
            "scope query status provenance_type confidence verify_before_use max_nodes max_edges max_isolated_ratio",
        )

    @mcp.tool()
    def memory_fabric_causal_audit(
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Audit causal graph path readiness."""
        return dumps_path_fresh(
            "memory_fabric_causal_audit",
            "causal_audit",
            store,
            locals(),
            "scope query status provenance_type confidence verify_before_use max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_claim_support(
        claims_json: str = "",
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        limit: int = 3,
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Audit memory support for explicit claims."""
        return dumps_path_fresh(
            "memory_fabric_claim_support",
            "claim_support_audit",
            store,
            locals(),
            "claims_json scope query status provenance_type confidence verify_before_use limit max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_projection_audit(
        input_path: str,
        max_bytes: int = 20000,
        max_recent: int = 12,
    ) -> str:
        """Audit projection."""
        return dumps(
            call_fresh(
                "memory_fabric_projection_audit",
                "audit_projection",
                input_path=input_path,
                max_bytes=max_bytes,
                max_recent=max_recent,
            )
        )

    @mcp.tool()
    def memory_fabric_store_audit(
        store: str = "",
        max_body_chars: int = 4000,
        sample_limit: int = 20,
    ) -> str:
        """Audit store."""
        return dumps_path_fresh(
            "memory_fabric_store_audit",
            "store_audit",
            store,
            locals(),
            "max_body_chars sample_limit",
        )

    @mcp.tool()
    def memory_fabric_evidence_audit(
        store: str = "",
        scope: str = "",
        strict: bool = False,
        sample_limit: int = 20,
    ) -> str:
        """Audit evidence."""
        return dumps_path_fresh(
            "memory_fabric_evidence_audit",
            "evidence_audit",
            store,
            locals(),
            "scope strict sample_limit",
        )

    register_telemetry_tool(mcp, dumps)

    @mcp.tool()
    def memory_fabric_thread_brief(
        scope: str = "",
        query: str = "",
        status: str = "active",
        confidence: str = "",
        provenance_type: str = "",
        verify_before_use: str = "",
        per_tier: int = 4,
        max_body_chars: int = 360,
        max_total_chars: int = 6000,
        store: str = "",
    ) -> str:
        """Thread brief."""
        return dumps_path_fresh(
            "memory_fabric_thread_brief",
            "thread_brief",
            store,
            locals(),
            "scope query status confidence provenance_type verify_before_use per_tier max_body_chars max_total_chars",
        )

    @mcp.tool()
    def memory_fabric_reasoning_brief(
        claims_json: str = "",
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        per_tier: int = 3,
        max_body_chars: int = 280,
        max_total_chars: int = 5000,
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Build an answer-readiness reasoning brief."""
        return dumps_path_fresh(
            "memory_fabric_reasoning_brief",
            "reasoning_brief",
            store,
            locals(),
            "claims_json scope query status provenance_type confidence verify_before_use "
            "per_tier max_body_chars max_total_chars max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_reasoning_eval(
        claims_json: str = "",
        scope: str = "",
        query: str = "",
        baseline_answer: str = "",
        memory_answer: str = "",
        required_terms: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        per_tier: int = 3,
        max_body_chars: int = 280,
        max_total_chars: int = 5000,
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Evaluate an answer against the reasoning-brief readiness gate."""
        return dumps_path_fresh(
            "memory_fabric_reasoning_eval",
            "reasoning_eval",
            store,
            locals(),
            "claims_json scope query baseline_answer memory_answer required_terms "
            "status provenance_type confidence verify_before_use per_tier "
            "max_body_chars max_total_chars max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_reasoning_eval_suite(
        cases_json: str = "",
        scope: str = "",
        query: str = "",
        status: str = "active",
        provenance_type: str = "",
        confidence: str = "",
        verify_before_use: str = "",
        per_tier: int = 3,
        max_body_chars: int = 280,
        max_total_chars: int = 5000,
        max_nodes: int = 24,
        max_edges: int = 80,
        store: str = "",
    ) -> str:
        """Evaluate multiple reasoning-brief-gated answer improvement cases."""
        return dumps_path_fresh(
            "memory_fabric_reasoning_eval_suite",
            "reasoning_eval_suite",
            store,
            locals(),
            "cases_json scope query status provenance_type confidence verify_before_use "
            "per_tier max_body_chars max_total_chars max_nodes max_edges",
        )

    @mcp.tool()
    def memory_fabric_answer_eval(
        scope: str = "",
        query: str = "",
        baseline_answer: str = "",
        memory_answer: str = "",
        required_terms: str = "",
        per_tier: int = 3,
        store: str = "",
    ) -> str:
        """Evaluate memory-assisted answer improvement."""
        return dumps_path_fresh(
            "memory_fabric_answer_eval",
            "answer_eval",
            store,
            locals(),
            "scope query baseline_answer memory_answer required_terms per_tier",
        )

    @mcp.tool()
    def memory_fabric_answer_eval_suite(
        cases_json: str = "",
        scope: str = "",
        query: str = "",
        per_tier: int = 3,
        store: str = "",
    ) -> str:
        """Evaluate multiple memory-assisted answer improvement cases."""
        return dumps_path_fresh(
            "memory_fabric_answer_eval_suite",
            "answer_eval_suite",
            store,
            locals(),
            "cases_json scope query per_tier",
        )

    @mcp.tool()
    def memory_fabric_release_report(
        version: str = "",
        plugin_root: str = "",
        marketplace_path: str = "",
        cache_root: str = "",
        store: str = "",
        projection_input: str = "",
        plugin_eval_json: str = "",
        benchmark_json: str = "",
        current_doctor_json: str = "",
        current_behavior_json: str = "",
        hook_health_json: str = "",
        expected_doctor_json: str = "",
        advertised_tools_csv: str = "",
        advertised_surface_json: str = "",
        advertised_truncated: bool = False,
        evidence_scope: str = "",
        strict_evidence: bool = False,
        require_current_behavior: bool = False,
        min_plugin_eval_score: int = 90,
        max_report_ms: int = 1000,
        sample_limit: int = 20,
    ) -> str:
        """Release receipt."""
        return dumps(
            call_fresh(
                "memory_fabric_release_report",
                "release_report",
                version=version,
                plugin_root=optional(plugin_root),
                marketplace_path=optional(marketplace_path),
                cache_root=optional(cache_root),
                store=optional(store),
                projection_input=projection_input,
                plugin_eval_json=plugin_eval_json,
                benchmark_json=benchmark_json,
                current_doctor_json=current_doctor_json,
                current_behavior_json=current_behavior_json,
                hook_health_json=hook_health_json,
                expected_doctor_json=expected_doctor_json,
                advertised_tools=csv_items(advertised_tools_csv) or None,
                advertised_surface=optional_json_object(advertised_surface_json),
                advertised_truncated=advertised_truncated,
                evidence_scope=evidence_scope,
                strict_evidence=strict_evidence,
                require_current_behavior=require_current_behavior,
                min_plugin_eval_score=min_plugin_eval_score,
                max_report_ms=max_report_ms,
                sample_limit=sample_limit,
            )
        )

    @mcp.tool()
    def memory_fabric_readiness_summary(
        release_report_json: str = "",
        frontier_audit_json: str = "",
        schema_json: str = "",
        store_audit_json: str = "",
        evidence_audit_json: str = "",
        current_doctor_json: str = "",
        current_behavior_json: str = "",
    ) -> str:
        """Summarize which supplied-receipt claims are safe right now."""
        return dumps(
            call_fresh(
                "memory_fabric_readiness_summary",
                "readiness_summary",
                release_report_json=release_report_json,
                frontier_audit_json=frontier_audit_json,
                schema_json=schema_json,
                store_audit_json=store_audit_json,
                evidence_audit_json=evidence_audit_json,
                current_doctor_json=current_doctor_json,
                current_behavior_json=current_behavior_json,
            )
        )

    register_install_tools(mcp, dumps)


def run_server() -> None:
    if FastMCP is None:
        print("codex-memory-fabric requires the mcp package for serve mode", file=sys.stderr)
        raise SystemExit(1)
    mcp.run()
