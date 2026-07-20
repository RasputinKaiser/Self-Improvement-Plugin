#!/usr/bin/env python3
"""Deterministic benchmark for memory retrieval and write policy behavior."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

BENCHMARK_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = BENCHMARK_DIR.parent.parent
SCRIPT_DIR = PLUGIN_ROOT / "scripts"
PLUGIN_NAME = json.loads(
    (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
)["name"]
MCP_TOOL_PREFIX = (
    "mcp__sips_homebase."
    if PLUGIN_NAME == "harness-self-improvement"
    else f"mcp__{PLUGIN_NAME.replace('-', '_')}."
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from memory_fabric_answer_eval import answer_eval
from memory_fabric_answer_eval_suite import answer_eval_suite
from memory_fabric_causal_audit import causal_audit
from memory_fabric_causal_hypotheses import causal_hypotheses
from memory_fabric_claim_support import claim_support_audit
from memory_fabric_capture import capture_representative_usage
from memory_fabric_budget_plan import budget_plan
from memory_fabric_evidence_audit import evidence_audit
from memory_fabric_evidence_repair import evidence_repair
from memory_fabric_events import record_from_hook_event
from memory_fabric_frontier_audit import frontier_audit
from memory_fabric_graph import memory_graph
from memory_fabric_graph_audit import graph_audit
from memory_fabric_hook_health import hook_health
from memory_fabric_install_sync import cache_sync
from memory_fabric_jsonl import load_records
from memory_fabric_live_behavior_cases import behavior_case
from memory_fabric_live import REQUIRED_LIVE_TOOLS, live_exposure
from memory_fabric_projection import project
from memory_fabric_projection_audit import audit_projection
from memory_fabric_promotion import assess_promotion
from memory_fabric_readiness_summary import readiness_summary
from memory_fabric_release_report import release_report
from memory_fabric_records import make_record
from memory_fabric_reasoning_brief import reasoning_brief
from memory_fabric_reasoning_eval import reasoning_eval
from memory_fabric_reasoning_eval_suite import reasoning_eval_suite
from memory_fabric_runtime_fingerprint import module_fingerprints, runtime_fingerprint
from memory_fabric_mcp_reload_order import reload_order
from memory_fabric_schema import schema
from memory_fabric_schema_behavior import schema_behavior_receipt
from memory_fabric_search import search_records
from memory_fabric_jsonl import append_record
from memory_fabric_store_audit import store_audit
from memory_fabric_telemetry_status import telemetry_status
from memory_fabric_telemetry_audit import telemetry_audit
from memory_fabric_thread_brief import thread_brief


Benchmark = Callable[[Path], dict[str, Any]]


def pass_result(name: str, details: dict[str, Any], started: float) -> dict[str, Any]:
    return {
        "name": name,
        "ok": True,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "details": details,
    }


def fail_result(name: str, error: str, started: float) -> dict[str, Any]:
    return {
        "name": name,
        "ok": False,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "error": error,
    }


def release_fixture(
    store: Path,
    suffix: str,
    scope: str,
    title: str,
    body: str,
) -> dict[str, Path]:
    root = store.parent / f"{store.stem}-{suffix}"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    write_marketplace_fixture(marketplace)
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="work",
            title=title,
            body=body,
            scope=scope,
            provenance_type="source_backed_agent_run",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    project(scope=scope, output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 22, "failed": 0, "scenario_count": 22}), encoding="utf-8")
    return {
        "root": root,
        "marketplace": marketplace,
        "cache_root": cache_root,
        "projection": projection,
        "plugin_eval": plugin_eval,
        "benchmark": benchmark,
    }


def write_marketplace_fixture(marketplace: Path) -> None:
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def benchmark_learning_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    record = make_record(
        tier="learning",
        title="Benchmark verified helper fix",
        body="Symptom: helper failed. Fix: use native binary. Proof: version command passed.",
        scope="/benchmark/repo",
        tags="benchmark,learning",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path="/tmp/version-proof.txt",
        confidence="high",
    )
    append_record(record, store)
    result = search_records(query="helper proof native", tier="learning", scope="/benchmark/repo", path=store)
    ensure(result["count"] == 1, "learning search should retrieve exactly one benchmark record")
    ensure(result["records"][0]["id"] == record["id"], "search should retrieve the written record")
    return pass_result(
        "learning_retrieval",
        {"record_id": record["id"], "score": result["records"][0]["_score"]},
        started,
    )


def benchmark_multi_tier_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    knowledge = make_record(
        tier="knowledge",
        title="Benchmark source-backed API fact",
        body="Verified source document proves the memory fabric schema API behavior.",
        scope="/benchmark/multi",
        tags="benchmark,api,source",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path="/tmp/api-proof.md",
        confidence="high",
    )
    learning = make_record(
        tier="learning",
        title="Benchmark cache mistake fix",
        body="Symptom: cache was stale. Fix: sync the cache. Proof: doctor passed.",
        scope="/benchmark/multi",
        tags="benchmark,cache,fix",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path="/tmp/cache-proof.json",
        confidence="high",
    )
    work = make_record(
        tier="work",
        title="Benchmark active cache task",
        body="Open task to inspect cache sync status after a local plugin update.",
        scope="/benchmark/multi",
        tags="benchmark,cache,task",
        provenance_type="user_instruction",
        provenance="benchmark fixture",
    )
    for record in [knowledge, learning, work]:
        append_record(record, store)

    ranked = search_records(query="source api proof", scope="/benchmark/multi", path=store)
    filtered = search_records(query="cache stale doctor", tier="learning", scope="/benchmark/multi", path=store)
    ensure(ranked["records"][0]["id"] == knowledge["id"], "knowledge record should rank first")
    ensure(filtered["count"] == 1, "learning tier filter should isolate the cache fix")
    ensure(filtered["records"][0]["id"] == learning["id"], "learning filter should return the cache fix")
    return pass_result(
        "multi_tier_retrieval",
        {
            "top_tier": ranked["records"][0]["tier"],
            "top_score": ranked["records"][0]["_score"],
            "learning_filtered_count": filtered["count"],
        },
        started,
    )


def benchmark_projection_compaction(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    record = make_record(
        tier="work",
        title="Benchmark next task",
        body="Large body that must not appear in the compact projection.",
        scope="/benchmark/projection",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path="/tmp/work-proof.txt",
    )
    append_record(record, store)
    output = store.parent / "projection-compaction.json"
    result = project(scope="/benchmark/projection", output=str(output), path=store)
    recent = result["projection"]["recent"]
    audit = audit_projection(str(output), max_bytes=20000, max_recent=12)
    ensure(recent, "projection should include recent records")
    ensure("body" not in recent[0], "projection should omit full memory bodies")
    ensure(recent[0]["status"] == "active", "projection should preserve compact status")
    ensure(result["projection"]["status_counts"] == {"active": 1}, "projection should count statuses")
    ensure(result["projection"]["source_of_truth"] == "append-only memory fabric store", "projection source mismatch")
    ensure(audit["ok"], "projection audit should accept generated compact projection")
    return pass_result(
        "projection_compaction",
        {
            "recent_count": len(recent),
            "status_counts": result["projection"]["status_counts"],
            "audit_status": audit["status"],
            "audit_byte_count": audit["byte_count"],
        },
        started,
    )


def benchmark_projection_status_boundary(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    candidate = make_record(
        tier="knowledge",
        title="Benchmark candidate observation",
        body="Screen-only observation that stays candidate.",
        scope="/benchmark/status",
        status="candidate",
    )
    active = make_record(
        tier="work",
        title="Benchmark active task",
        body="Active task for the compact projection.",
        scope="/benchmark/status",
        status="active",
    )
    append_record(candidate, store)
    append_record(active, store)
    result = project(scope="/benchmark/status", path=store)
    recent = result["projection"]["recent"]
    ensure(result["projection"]["status_counts"] == {"active": 1, "candidate": 1}, "status counts mismatch")
    ensure({record["status"] for record in recent} == {"active", "candidate"}, "compact records should expose status")
    ensure(all("body" not in record for record in recent), "projection should keep bodies out")
    return pass_result("projection_status_boundary", {"status_counts": result["projection"]["status_counts"]}, started)


def benchmark_thread_brief_tri_layer_handoff(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    for tier, title, body in [
        ("work", "Benchmark brief active task", "Open task and current decision for the release loop."),
        ("knowledge", "Benchmark brief source fact", "Source-backed framework note for memory graph networking."),
        ("learning", "Benchmark brief lesson", "Symptom: stale schema. Fix: live doctor. Proof: receipt."),
    ]:
        append_record(
            make_record(
                tier=tier,
                title=title,
                body=body,
                scope="/benchmark/thread-brief",
                provenance_type="verified_command",
                provenance="benchmark fixture",
                evidence_path="/tmp/thread-brief-proof.json",
                confidence="high",
            ),
            store,
        )
    result = thread_brief(
        scope="/benchmark/thread-brief",
        query="brief",
        path=store,
        per_tier=2,
        max_body_chars=80,
    )
    ensure(result["ok"], "thread brief should succeed")
    ensure(result["counts"] == {"work": 1, "knowledge": 1, "learning": 1}, "thread brief should cover all tiers")
    ensure(result["source_of_truth"] == "append-only memory fabric store", "thread brief source boundary mismatch")
    ensure(result["graph"]["reasoning_path_count"] >= 1, "thread brief should include graph handoff paths")
    return pass_result(
        "thread_brief_tri_layer_handoff",
        {
            "counts": result["counts"],
            "graph_path_count": result["graph"]["reasoning_path_count"],
            "truncated": result["truncated"],
            "section_count": len(result["sections"]),
        },
        started,
    )


def benchmark_thread_brief_readiness_gates(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    weak = make_record(
        tier="knowledge",
        title="Benchmark brief weak claim",
        body="Weak brief claim.",
        scope="/benchmark/brief-readiness",
        tags="benchmark,brief,readiness",
        provenance_type="user_or_agent_observation",
        confidence="medium",
    )
    strong = make_record(
        tier="knowledge",
        title="Benchmark brief source claim",
        body="placeholder",
        scope="/benchmark/brief-readiness",
        tags="benchmark,brief,readiness",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path="/tmp/brief-readiness-proof.md",
        confidence="high",
    )
    strong["body"] = f"Contradicts: {weak['id']}"
    append_record(weak, store)
    append_record(strong, store)
    result = thread_brief(scope="/benchmark/brief-readiness", query="brief", per_tier=3, path=store)
    readiness = result["readiness"]
    ensure(not readiness["ok"], "brief readiness should flag active conflict")
    ensure(readiness["trust_counts"] == {"context_only": 1, "ready": 1}, "brief trust counts mismatch")
    ensure(readiness["active_contradiction_count"] == 1, "brief should count active contradiction")
    ensure(
        "resolve_conflicts_or_supersede_records" in readiness["recommended_next_checks"],
        "brief should recommend conflict resolution",
    )
    return pass_result(
        "thread_brief_readiness_gates",
        {
            "trust_counts": readiness["trust_counts"],
            "active_contradiction_count": readiness["active_contradiction_count"],
            "recommended_next_checks": readiness["recommended_next_checks"],
        },
        started,
    )


def benchmark_thread_brief_task_profile_object_identification(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "object-identification-proof.json"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="learning",
            title="Benchmark object identification pricing workflow",
            body=(
                "Use broad visual description plus logos, codes, materials, glass, wood, trim, "
                "and style details before visual comparison and pricing."
            ),
            scope="/benchmark/object-identification",
            tags="identify,item,ebay,pricing,logo,glass,wood,trim,style",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = thread_brief(
        scope="/benchmark/object-identification",
        query="identify item logo code glass wood trim style ebay pricing",
        path=store,
        per_tier=2,
    )
    profile = result["task_profile"]
    ledger = profile["cue_ledger"]
    ensure(profile["id"] == "object_identification_pricing", "brief should select object identification profile")
    ensure("extract_text_logos_codes_markings" in profile["next_checks"], "profile should ask for markings")
    ensure("price_only_after_likely_same_item" in profile["next_checks"], "profile should defer pricing")
    ensure(ledger["ok"], "complete cue set should pass cue ledger")
    ensure(ledger["pricing_gate"]["ok"], "complete candidate comparison should open pricing context")
    ensure(profile["selected_trust_counts"] == {"ready": 1}, "profile should summarize selected trust")
    ensure("not identity or pricing proof" in profile["proof_boundary"], "profile should carry proof boundary")
    return pass_result(
        "thread_brief_task_profile_object_identification",
        {
            "profile": profile["id"],
            "next_check_count": len(profile["next_checks"]),
            "cue_status": ledger["status"],
            "selected_trust_counts": profile["selected_trust_counts"],
        },
        started,
    )


def benchmark_thread_brief_object_identification_pricing_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "object-identification-pricing-gate-proof.json"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="learning",
            title="Benchmark object identification early cues",
            body="Start with logo, code, material, glass, wood, trim and style details before pricing.",
            scope="/benchmark/object-identification-pricing-gate",
            tags="identify,item,logo,code,glass,wood,trim,style",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = thread_brief(
        scope="/benchmark/object-identification-pricing-gate",
        query="identify item logo code glass wood trim style pricing",
        path=store,
        per_tier=2,
    )
    ledger = result["task_profile"]["cue_ledger"]
    gate = ledger["pricing_gate"]
    ensure(not ledger["ok"], "missing candidate comparison cues should keep cue ledger incomplete")
    ensure(not gate["ok"], "pricing gate should block before candidate match and visual comparison")
    ensure(gate["blocked_by"] == ["candidate_match", "visual_comparison"], "pricing gate blockers mismatch")
    ensure(
        "find_candidate_match_before_pricing" in ledger["missing_next_checks"],
        "missing candidate source should be an explicit next check",
    )
    return pass_result(
        "thread_brief_object_identification_pricing_gate",
        {
            "cue_status": ledger["status"],
            "pricing_gate_status": gate["status"],
            "blocked_by": gate["blocked_by"],
        },
        started,
    )


def benchmark_reasoning_brief_answer_contract_blocks_object_pricing_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-object-pricing-gate-proof.json"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="learning",
            title="Benchmark reasoning object identification early cues",
            body="Use logo, code, material, glass, wood, trim and style details before pricing.",
            scope="/benchmark/reasoning-object-pricing-gate",
            tags="identify,item,logo,code,glass,wood,trim,style,pricing",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = reasoning_brief(
        scope="/benchmark/reasoning-object-pricing-gate",
        query="identify item logo code glass wood trim style pricing",
        path=store,
        per_tier=2,
    )
    contract = result["answer_contract"]
    ensure(not result["ready_for_answer"], "reasoning readiness should block task-gated pricing")
    ensure(result["status"] == "reasoning_brief_needs_verification", "task gate should affect brief status")
    ensure(contract["status"] == "answer_contract_needs_verification", "contract should require verification")
    ensure(
        contract["task_gate"]["blocked_by"] == ["candidate_match", "visual_comparison"],
        "contract should name pricing blockers",
    )
    ensure(
        "do_not_price_before_candidate_match_and_visual_comparison" in contract["blocked_actions"],
        "contract should name blocked pricing action",
    )
    return pass_result(
        "reasoning_brief_answer_contract_blocks_object_pricing_gate",
        {
            "status": result["status"],
            "contract_status": contract["status"],
            "blocked_actions": contract["blocked_actions"],
            "task_gate": contract["task_gate"]["status"],
        },
        started,
    )


def benchmark_answer_eval_memory_improves_answer(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "answer-eval-proof.json"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark answer eval source fact",
            body="Answer eval should preserve source cache live proof boundaries.",
            scope="/benchmark/answer-eval",
            tags="answer,eval,proof",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = answer_eval(
        scope="/benchmark/answer-eval",
        query="answer eval proof",
        baseline_answer="It is probably fine.",
        memory_answer=(
            f"Answer eval preserves source cache live proof boundaries. Evidence: {proof}. "
            "Verify live separately."
        ),
        required_terms="source cache,live proof,boundaries",
        path=store,
    )
    ensure(result["ok"], "memory answer should beat baseline")
    ensure(result["memory"]["missing_terms"] == [], "memory answer should cover required terms")
    ensure(result["memory"]["proof_boundary_present"], "memory answer should carry proof boundary language")
    ensure(
        result["memory_grounding"]["cited_evidence_paths"] == [str(proof)],
        "memory answer should cite selected evidence",
    )
    ensure(result["improvement"]["score_delta"] > 0, "score delta should be positive")
    ensure(result["improvement"]["cited_evidence_delta"] == 1, "memory answer should improve evidence grounding")
    return pass_result(
        "answer_eval_memory_improves_answer",
        {
            "status": result["status"],
            "score_delta": result["improvement"]["score_delta"],
            "cited_evidence_delta": result["improvement"]["cited_evidence_delta"],
            "required_terms": result["required_terms"],
        },
        started,
    )


def benchmark_answer_eval_suite_multi_case_grounding(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    release_proof = store.parent / "answer-suite-release-proof.json"
    policy_proof = store.parent / "answer-suite-policy-proof.json"
    release_proof.write_text("{}", encoding="utf-8")
    policy_proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark suite release boundary",
            body="Release answers must separate source cache and live proof.",
            scope="/benchmark/answer-suite/release",
            tags="answer,suite,release",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(release_proof),
            confidence="high",
        ),
        store,
    )
    append_record(
        make_record(
            tier="learning",
            title="Benchmark suite evidence lesson",
            body="Symptom: answer overclaim. Fix: cite evidence and verify live separately. Proof: suite receipt.",
            scope="/benchmark/answer-suite/policy",
            tags="answer,suite,policy",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            evidence_path=str(policy_proof),
            confidence="high",
        ),
        store,
    )
    result = answer_eval_suite(
        cases_json=json.dumps(
            [
                {
                    "id": "release-boundary",
                    "scope": "/benchmark/answer-suite/release",
                    "query": "release proof boundary",
                    "baseline_answer": "Ship it.",
                    "memory_answer": (
                        "Release answers must separate source cache and live proof. "
                        f"Evidence: {release_proof}. Verify live separately."
                    ),
                    "required_terms": "source cache,live proof,release",
                },
                {
                    "id": "evidence-policy",
                    "scope": "/benchmark/answer-suite/policy",
                    "query": "answer evidence policy",
                    "baseline_answer": "The answer is better.",
                    "memory_answer": (
                        "The answer policy is to cite evidence and verify live separately. "
                        f"Evidence: {policy_proof}. Keep the proof boundary visible."
                    ),
                    "required_terms": "cite evidence,verify live,proof boundary",
                },
            ]
        ),
        path=store,
    )
    ensure(result["ok"], "all suite cases should prove memory improvement")
    ensure(result["case_count"] == 2, "suite should run both cases")
    ensure(result["passed_count"] == 2, "suite should pass both cases")
    ensure(result["failed_count"] == 0, "suite should not hide failed cases")
    ensure(result["minimum_score_delta"] > 0, "every case should improve score")
    ensure(result["total_cited_evidence_delta"] == 2, "suite should improve cited evidence in both cases")
    ensure(result["failed_case_ids"] == [], "passing suite should not report failures")
    ensure(result["missing_terms_case_ids"] == [], "passing suite should not report missing terms")
    ensure(result["missing_evidence_case_ids"] == [], "passing suite should not report missing evidence")
    ensure(result["proof_boundary_failed_case_ids"] == [], "passing suite should not report proof-boundary failures")
    ensure("not model reasoning" in result["claim_boundary"], "suite should preserve reasoning proof boundary")
    return pass_result(
        "answer_eval_suite_multi_case_grounding",
        {
            "status": result["status"],
            "case_count": result["case_count"],
            "minimum_score_delta": result["minimum_score_delta"],
            "total_cited_evidence_delta": result["total_cited_evidence_delta"],
        },
        started,
    )


def benchmark_answer_eval_suite_failed_case_categories(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    missing_terms_proof = store.parent / "answer-suite-missing-terms-proof.json"
    no_gain_proof = store.parent / "answer-suite-no-gain-proof.json"
    context_proof = store.parent / "answer-suite-context-proof.json"
    for proof in [missing_terms_proof, no_gain_proof, context_proof]:
        proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark suite missing terms fact",
            body="Suite category eval must name missing required terms.",
            scope="/benchmark/answer-suite/categories/missing",
            tags="answer,suite,categories,missing",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(missing_terms_proof),
            confidence="high",
        ),
        store,
    )
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark suite no gain fact",
            body="Suite category eval must prove an evidence grounding gain.",
            scope="/benchmark/answer-suite/categories/no-gain",
            tags="answer,suite,categories,gain",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(no_gain_proof),
            confidence="high",
        ),
        store,
    )
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark suite context hint",
            body="OpenChronicle hinted the object identity might be studio glass.",
            scope="/benchmark/answer-suite/categories/context",
            tags="answer,suite,categories,context",
            provenance_type="openchronicle",
            provenance="benchmark fixture",
            evidence_path=str(context_proof),
            confidence="high",
        ),
        store,
    )
    no_gain_answer = (
        "Suite category eval must prove an evidence grounding gain. "
        f"Evidence: {no_gain_proof}. Verify live separately."
    )
    result = answer_eval_suite(
        cases_json=json.dumps(
            [
                {
                    "id": "missing-terms",
                    "scope": "/benchmark/answer-suite/categories/missing",
                    "query": "suite category missing terms",
                    "baseline_answer": "It might help.",
                    "memory_answer": f"Evidence: {missing_terms_proof}. Verify live separately.",
                    "required_terms": "suite category,required term",
                },
                {
                    "id": "no-gain",
                    "scope": "/benchmark/answer-suite/categories/no-gain",
                    "query": "suite category evidence gain",
                    "baseline_answer": no_gain_answer,
                    "memory_answer": no_gain_answer,
                    "required_terms": "evidence grounding gain",
                },
                {
                    "id": "proof-blur",
                    "scope": "/benchmark/answer-suite/categories/context",
                    "query": "context object identity",
                    "baseline_answer": "It might be glass.",
                    "memory_answer": (
                        "OpenChronicle verified the object identity as studio glass. "
                        f"Evidence: {context_proof}. This is proof of the identity."
                    ),
                    "required_terms": "object identity,studio glass",
                },
            ]
        ),
        path=store,
    )
    ensure(not result["ok"], "category suite should fail")
    ensure(
        set(result["failed_case_ids"]) == {"missing-terms", "no-gain", "proof-blur"},
        "suite should expose failed cases",
    )
    ensure(result["missing_terms_case_ids"] == ["missing-terms"], "suite should classify missing terms")
    ensure(result["no_improvement_case_ids"] == ["no-gain"], "suite should classify no improvement")
    ensure(result["no_evidence_gain_case_ids"] == ["no-gain"], "suite should classify no evidence gain")
    ensure(result["proof_boundary_failed_case_ids"] == ["proof-blur"], "suite should classify proof-boundary blur")
    ensure(result["missing_evidence_case_ids"] == [], "category suite should not invent missing evidence")
    return pass_result(
        "answer_eval_suite_failed_case_categories",
        {
            "status": result["status"],
            "failed_case_ids": result["failed_case_ids"],
            "missing_terms_case_ids": result["missing_terms_case_ids"],
            "no_improvement_case_ids": result["no_improvement_case_ids"],
            "no_evidence_gain_case_ids": result["no_evidence_gain_case_ids"],
            "proof_boundary_failed_case_ids": result["proof_boundary_failed_case_ids"],
        },
        started,
    )


def benchmark_memory_graph_typed_edges(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "memory-graph-proof.json"
    proof.write_text("{}", encoding="utf-8")
    work = make_record(
        tier="work",
        title="Benchmark graph active task",
        body="Graph task waiting on the reusable lesson.",
        scope="/benchmark/graph",
        tags="benchmark,graph",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    lesson = make_record(
        tier="learning",
        title="Benchmark graph lesson",
        body="Symptom: flat memory. Fix: graph edges. Proof: benchmark.",
        scope="/benchmark/graph",
        tags="benchmark,graph,fix",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    work["body"] = f"Depends on: {lesson['id']}"
    append_record(work, store)
    append_record(lesson, store)
    result = memory_graph(scope="/benchmark/graph", query="graph", path=store)
    ensure(result["ok"], "memory graph should succeed")
    ensure(result["node_count"] == 2, "memory graph should include both graph records")
    ensure(result["edge_type_counts"].get("depends_on") == 1, "memory graph should parse explicit depends_on")
    ensure(result["edge_type_counts"].get("shares_tag", 0) >= 1, "memory graph should link shared tags")
    ensure(result["reasoning_path_count"] >= 1, "memory graph should expose bounded reasoning paths")
    return pass_result(
        "memory_graph_typed_edges",
        {
            "node_count": result["node_count"],
            "edge_count": result["edge_count"],
            "edge_type_counts": result["edge_type_counts"],
            "reasoning_path_count": result["reasoning_path_count"],
        },
        started,
    )


def benchmark_memory_graph_frontier_reasoning_markers(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    targets = [
        make_record(
            tier="learning",
            title=f"Benchmark graph {title}",
            body=f"Symptom: missing {title}. Fix: add typed graph marker. Proof: frontier graph benchmark.",
            scope="/benchmark/graph-frontier",
            tags="benchmark,graph,frontier",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            confidence="high",
        )
        for title in ["proof receipt", "blocking task", "cause lesson", "pattern lesson"]
    ]
    source = make_record(
        tier="work",
        title="Benchmark graph frontier task",
        body="placeholder",
        scope="/benchmark/graph-frontier",
        tags="benchmark,graph,frontier",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        confidence="high",
    )
    source["body"] = (
        f"Proved by: {targets[0]['id']}\n"
        f"Blocked by: {targets[1]['id']}\n"
        f"Caused by: {targets[2]['id']}\n"
        f"Same pattern as: {targets[3]['id']}"
    )
    for record in [source, *targets]:
        append_record(record, store)

    result = memory_graph(scope="/benchmark/graph-frontier", query="graph", max_edges=4, path=store)
    edge_types = {edge["type"] for edge in result["edges"]}
    expected = {"blocked_by", "caused_by", "proved_by", "same_pattern_as"}
    ensure(result["truncated_edges"], "frontier graph fixture should create a tight reasoning window")
    ensure(edge_types == expected, "tight graph window should keep frontier reasoning markers")
    return pass_result(
        "memory_graph_frontier_reasoning_markers",
        {
            "edge_types": sorted(edge_types),
            "truncated_edges": result["truncated_edges"],
            "node_count": result["node_count"],
        },
        started,
    )


def benchmark_memory_graph_decision_context(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    selected = make_record(
        tier="work",
        title="Benchmark selected decision",
        body="placeholder",
        scope="/benchmark/graph-decision",
        tags="benchmark,graph,decision",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        confidence="high",
    )
    alternative = make_record(
        tier="work",
        title="Benchmark alternative decision",
        body="placeholder",
        scope="/benchmark/graph-decision",
        tags="benchmark,graph,decision",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        confidence="high",
    )
    selected["body"] = f"Decision for: {alternative['id']}\nChosen over: {alternative['id']}"
    alternative["body"] = f"Alternative to: {selected['id']}\nTradeoff with: {selected['id']}"
    append_record(selected, store)
    append_record(alternative, store)

    result = memory_graph(scope="/benchmark/graph-decision", query="decision", path=store)
    decision = result["decision_context"]
    ensure(decision["status"] == "decision_context_present", "graph should expose decision context")
    ensure(decision["has_selected_option"], "decision context should identify selected option markers")
    ensure(decision["has_alternatives"], "decision context should identify alternative/tradeoff markers")
    ensure(not decision["recommended_next_checks"], "complete decision context should need no next checks")
    chosen = [path for path in result["reasoning_paths"] if path["edges"] == ["chosen_over"]]
    ensure(chosen, "decision graph should include chosen_over reasoning path")
    ensure(chosen[0]["explanation"]["status"] == "decision_context", "decision edge should not be causal proof")
    ensure(not chosen[0]["explanation"]["causal_edge"], "decision edge should not be marked causal")
    ensure(chosen[0]["explanation"]["decision_edge"], "path explanation should mark decision edge")
    return pass_result(
        "memory_graph_decision_context",
        {
            "edge_type_counts": decision["edge_type_counts"],
            "has_selected_option": decision["has_selected_option"],
            "has_alternatives": decision["has_alternatives"],
            "path_status": chosen[0]["explanation"]["status"],
        },
        started,
    )


def benchmark_memory_graph_path_explanations(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "graph-path-explanation-proof.md"
    proof.write_text("{}", encoding="utf-8")
    source = make_record(
        tier="work",
        title="Benchmark graph path source",
        body="placeholder",
        scope="/benchmark/graph-path-explain",
        tags="benchmark,graph,path",
        provenance_type="screen_observation",
        provenance="benchmark fixture",
        confidence="medium",
    )
    target = make_record(
        tier="knowledge",
        title="Benchmark graph path target",
        body="Verified source-backed path target.",
        scope="/benchmark/graph-path-explain",
        tags="benchmark,graph,path",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source["body"] = f"Caused by: {target['id']}"
    append_record(source, store)
    append_record(target, store)
    result = memory_graph(scope="/benchmark/graph-path-explain", query="graph", path=store)
    path = next(item for item in result["reasoning_paths"] if item["edges"] == ["caused_by"])
    explanation = path["explanation"]
    ensure(explanation["status"] == "needs_verification", "context-only causal path should need verification")
    ensure(explanation["node_trusts"] == ["context_only", "ready"], "path should summarize node trust")
    ensure(str(proof) in explanation["evidence_paths"], "path should expose available evidence paths")
    ensure("do not prove causal truth" in explanation["claim_boundary"], "path should carry proof boundary")
    return pass_result(
        "memory_graph_path_explanations",
        {
            "status": explanation["status"],
            "node_trusts": explanation["node_trusts"],
            "edge_type": explanation["edge_type"],
        },
        started,
    )


def benchmark_causal_audit_verification_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "causal-audit-proof.md"
    proof.write_text("{}", encoding="utf-8")
    source = make_record(
        tier="work",
        title="Benchmark weak causal source",
        body="placeholder",
        scope="/benchmark/causal-audit",
        tags="benchmark,causal,audit",
        provenance_type="screen_observation",
        provenance="benchmark fixture",
        confidence="medium",
    )
    target = make_record(
        tier="knowledge",
        title="Benchmark sourced causal target",
        body="Verified source-backed causal target.",
        scope="/benchmark/causal-audit",
        tags="benchmark,causal,audit",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source["body"] = f"Caused by: {target['id']}"
    append_record(source, store)
    append_record(target, store)
    result = causal_audit(scope="/benchmark/causal-audit", query="causal", path=store)
    ensure(not result["ok"], "context-only causal path should not pass causal audit")
    ensure(result["status"] == "causal_paths_need_verification", "causal audit should require verification")
    ensure(result["causal_path_count"] == 1, "causal audit should count causal paths")
    ensure(result["needs_verification_count"] == 1, "causal audit should count verification-needed paths")
    ensure(result["missing_evidence_node_count"] == 1, "causal audit should count missing evidence nodes")
    ensure(
        "verify_or_downgrade_non_ready_causal_paths" in result["recommended_next_checks"],
        "causal audit should recommend verification or downgrade",
    )
    ensure(
        "attach_source_evidence_to_causal_records" in result["recommended_next_checks"],
        "causal audit should require source evidence for causal records",
    )
    ensure(str(proof) in result["causal_paths"][0]["evidence_paths"], "causal audit should expose evidence paths")
    ensure(
        result["causal_paths"][0]["evidence_ledger"]["status"] == "causal_evidence_needs_sources",
        "causal audit should emit per-path evidence ledger",
    )
    ensure(
        result["required_citation_paths"] == [str(proof)],
        "causal audit should expose required citation paths",
    )
    ensure("does not prove causal truth" in result["claim_boundary"], "causal audit should preserve proof boundary")
    return pass_result(
        "causal_audit_verification_gate",
        {
            "status": result["status"],
            "causal_path_count": result["causal_path_count"],
            "needs_verification_count": result["needs_verification_count"],
            "missing_evidence_node_count": result["missing_evidence_node_count"],
            "next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_claim_support_audit_claim_ledger(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "claim-support-proof.md"
    proof.write_text("{}", encoding="utf-8")
    ready = make_record(
        tier="knowledge",
        title="Benchmark supported claim source",
        body="Memory fabric claim support audits selected evidence and retrieval readiness.",
        scope="/benchmark/claim-support",
        tags="benchmark,claim,support",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    weak = make_record(
        tier="knowledge",
        title="Benchmark weak claim screen lead",
        body="Screen context says claim support is complete.",
        scope="/benchmark/claim-support",
        tags="benchmark,claim,support",
        provenance_type="screen_observation",
        provenance="benchmark fixture",
        confidence="medium",
    )
    append_record(ready, store)
    append_record(weak, store)
    result = claim_support_audit(
        claims_json=json.dumps(
            {
                "claims": [
                    "Memory fabric claim support audits selected evidence",
                    "claim support is complete",
                    "missing claim has no source",
                ]
            }
        ),
        scope="/benchmark/claim-support",
        path=store,
    )
    ensure(not result["ok"], "mixed claim ledger should not pass")
    ensure(result["claim_count"] == 3, "claim support should audit each claim")
    ensure(result["supported_count"] == 1, "one claim should be supported")
    ensure(result["needs_verification_count"] == 1, "one claim should need verification")
    ensure(result["unsupported_count"] == 1, "one claim should be unsupported")
    ensure(
        "record_source_backed_memory_or_downgrade_claim" in result["recommended_next_checks"],
        "unsupported claim should recommend source-backed memory or downgrade",
    )
    ensure("external truth" in result["claim_boundary"], "claim support should preserve proof boundary")
    return pass_result(
        "claim_support_audit_claim_ledger",
        {
            "status": result["status"],
            "status_counts": result["status_counts"],
            "recommended_next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_claim_support_causal_evidence_trace(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "claim-support-causal-proof.md"
    proof.write_text("{}", encoding="utf-8")
    target = make_record(
        tier="knowledge",
        title="Benchmark claim causal target",
        body="Verified causal target for claim support evidence trace.",
        scope="/benchmark/claim-support-causal",
        tags="benchmark,claim,causal,trace",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source = make_record(
        tier="work",
        title="Benchmark claim causal source",
        body=f"Claim support trace caused by source evidence. caused by: {target['id']}",
        scope="/benchmark/claim-support-causal",
        tags="benchmark,claim,causal,trace",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(target, store)
    append_record(source, store)
    result = claim_support_audit(
        claims_json=json.dumps(["Claim support trace caused by source evidence"]),
        scope="/benchmark/claim-support-causal",
        path=store,
    )
    claim = result["claims"][0]
    causal = claim["causal"]
    ensure(result["ok"], "ready causal claim should pass claim-support audit")
    ensure(claim["claim_kind"] == "causal", "claim should be classified as causal")
    ensure(causal["status"] == "causal_paths_ready", "causal trace should be ready")
    ensure(causal["required_citation_paths"] == [str(proof)], "causal trace should expose citation paths")
    ensure(causal["missing_evidence_node_count"] == 0, "ready causal trace should have no missing evidence")
    ensure(
        causal["causal_paths"][0]["evidence_ledger"]["status"] == "causal_evidence_ready",
        "causal path should carry its evidence ledger",
    )
    return pass_result(
        "claim_support_causal_evidence_trace",
        {
            "status": result["status"],
            "causal_status": causal["status"],
            "required_citation_count": len(causal["required_citation_paths"]),
            "missing_evidence_node_count": causal["missing_evidence_node_count"],
        },
        started,
    )


def benchmark_causal_hypotheses_disambiguation_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "causal-hypotheses-proof.md"
    proof.write_text("{}", encoding="utf-8")
    target = make_record(
        tier="knowledge",
        title="Benchmark shared causal target",
        body="Verified target for competing causal hypotheses.",
        scope="/benchmark/causal-hypotheses",
        tags="benchmark,causal,hypothesis",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    first = make_record(
        tier="learning",
        title="Benchmark first causal hypothesis",
        body=f"First ready causal hypothesis. caused by: {target['id']}",
        scope="/benchmark/causal-hypotheses",
        tags="benchmark,causal,hypothesis",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    second = make_record(
        tier="work",
        title="Benchmark second causal hypothesis",
        body=f"Second ready causal hypothesis. caused by: {target['id']}",
        scope="/benchmark/causal-hypotheses",
        tags="benchmark,causal,hypothesis",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    for record in [target, first, second]:
        append_record(record, store)
    result = causal_hypotheses(scope="/benchmark/causal-hypotheses", query="causal hypothesis", path=store)
    ensure(not result["ok"], "competing ready hypotheses should not pass without disambiguation")
    ensure(result["status"] == "causal_hypotheses_need_disambiguation", "hypotheses should require disambiguation")
    ensure(result["hypothesis_count"] == 2, "audit should count two hypotheses")
    ensure(result["competing_target_count"] == 1, "audit should count one competing target")
    ensure(
        "gather_discriminating_evidence_for_competing_causes" in result["recommended_next_checks"],
        "audit should recommend discriminating evidence",
    )
    ensure("do not prove causality" in result["claim_boundary"], "hypothesis audit should preserve proof boundary")
    return pass_result(
        "causal_hypotheses_disambiguation_gate",
        {
            "status": result["status"],
            "hypothesis_count": result["hypothesis_count"],
            "competing_target_count": result["competing_target_count"],
            "recommended_next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_reasoning_brief_answer_readiness_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-brief-proof.md"
    proof.write_text("{}", encoding="utf-8")
    target = make_record(
        tier="knowledge",
        title="Benchmark reasoning source cache receipt",
        body="Verified source cache receipt for reasoning brief answer readiness.",
        scope="/benchmark/reasoning-brief",
        tags="benchmark,reasoning,answer,ready,source,cache,receipt",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source = make_record(
        tier="work",
        title="Benchmark reasoning answer ready rollout",
        body=f"Reasoning answer ready rollout uses source cache receipt. depends on: {target['id']}",
        scope="/benchmark/reasoning-brief",
        tags="benchmark,reasoning,answer,ready,source,cache,receipt",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(target, store)
    append_record(source, store)
    result = reasoning_brief(
        claims_json=json.dumps({"claims": ["Reasoning answer ready rollout uses source cache receipt"]}),
        scope="/benchmark/reasoning-brief",
        query="reasoning answer ready source cache receipt",
        path=store,
    )
    ensure(result["ok"], "reasoning brief should be ready when memory, graph, and claims are ready")
    ensure(result["ready_for_answer"], "reasoning brief should expose ready_for_answer")
    ensure(result["status"] == "reasoning_brief_ready", "reasoning brief should report ready status")
    ensure(result["claim_support"]["status"] == "claims_supported", "explicit claim should be supported")
    ensure(result["graph"]["status"] == "graph_healthy", "graph should be healthy")
    ensure(result["answer_use_policy"]["status"] == "answer_use_ready", "answer-use policy should be ready")
    ensure(result["answer_use_policy"]["answer_use_counts"] == {"cite": 2}, "ready records should be citable")
    ensure(result["answer_contract"]["status"] == "answer_contract_ready", "answer contract should be ready")
    ensure(
        result["answer_contract"]["required_citations"] == [str(proof)],
        "answer contract should dedupe required evidence paths",
    )
    ensure(
        "external truth" in result["claim_boundary"] or "do not prove external truth" in result["claim_boundary"],
        "reasoning brief should preserve proof boundary",
    )
    return pass_result(
        "reasoning_brief_answer_readiness_gate",
        {
            "status": result["status"],
            "ready_for_answer": result["ready_for_answer"],
            "selected_record_count": result["selected_record_count"],
            "claim_support_status": result["claim_support"]["status"],
            "graph_status": result["graph"]["status"],
            "answer_use_status": result["answer_use_policy"]["status"],
            "answer_contract_status": result["answer_contract"]["status"],
        },
        started,
    )


def benchmark_reasoning_brief_decision_context_trace(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    selected = make_record(
        tier="work",
        title="Benchmark reasoning selected decision",
        body="placeholder",
        scope="/benchmark/reasoning-decision",
        tags="benchmark,reasoning,decision",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        confidence="high",
    )
    alternative = make_record(
        tier="work",
        title="Benchmark reasoning alternative decision",
        body="placeholder",
        scope="/benchmark/reasoning-decision",
        tags="benchmark,reasoning,decision",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        confidence="high",
    )
    selected["body"] = f"Decision for: {alternative['id']}\nChosen over: {alternative['id']}"
    alternative["body"] = f"Alternative to: {selected['id']}\nTradeoff with: {selected['id']}"
    append_record(selected, store)
    append_record(alternative, store)

    result = reasoning_brief(
        scope="/benchmark/reasoning-decision",
        query="reasoning decision",
        path=store,
    )
    decision = result["graph"]["decision_context"]
    ensure(decision["status"] == "decision_context_present", "reasoning brief should carry decision context")
    ensure(decision["has_selected_option"], "reasoning brief should carry selected-option marker")
    ensure(decision["has_alternatives"], "reasoning brief should carry alternative/tradeoff marker")
    ensure(not decision["recommended_next_checks"], "complete decision context should have no next checks")
    ensure("do not prove" in decision["claim_boundary"], "decision context should keep proof boundary")
    return pass_result(
        "reasoning_brief_decision_context_trace",
        {
            "status": result["status"],
            "decision_status": decision["status"],
            "edge_type_counts": decision["edge_type_counts"],
            "has_selected_option": decision["has_selected_option"],
            "has_alternatives": decision["has_alternatives"],
        },
        started,
    )


def benchmark_reasoning_brief_causal_evidence_trace(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-brief-causal-trace-proof.md"
    proof.write_text("{}", encoding="utf-8")
    source = make_record(
        tier="work",
        title="Benchmark reasoning weak causal source",
        body="Context-only causal source.",
        scope="/benchmark/reasoning-causal-trace",
        tags="benchmark,reasoning,causal,trace",
        provenance_type="openchronicle",
        provenance="benchmark fixture",
        confidence="low",
    )
    target = make_record(
        tier="knowledge",
        title="Benchmark reasoning sourced causal target",
        body="Verified causal target for reasoning evidence trace.",
        scope="/benchmark/reasoning-causal-trace",
        tags="benchmark,reasoning,causal,trace",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source["body"] = f"Context-only causal source. caused by: {target['id']}"
    append_record(source, store)
    append_record(target, store)
    result = reasoning_brief(
        scope="/benchmark/reasoning-causal-trace",
        query="causal reasoning trace",
        path=store,
    )
    trace = result["causal_evidence"]
    ensure(not result["ready_for_answer"], "missing causal trace evidence should block answer readiness")
    ensure(trace["status"] == "causal_paths_need_verification", "trace should report non-ready causal paths")
    ensure(trace["missing_evidence_node_count"] == 1, "trace should count missing evidence nodes")
    ensure(trace["required_citation_paths"] == [str(proof)], "trace should expose causal citation paths")
    ensure(
        "cite_or_attach_evidence_for_causal_trace_nodes" in result["recommended_next_checks"],
        "reasoning brief should recommend attaching causal trace evidence",
    )
    ensure(
        "does not prove causal truth" in trace["claim_boundary"],
        "causal evidence trace should preserve proof boundary",
    )
    return pass_result(
        "reasoning_brief_causal_evidence_trace",
        {
            "status": result["status"],
            "ready_for_answer": result["ready_for_answer"],
            "causal_evidence_status": trace["status"],
            "missing_evidence_node_count": trace["missing_evidence_node_count"],
        },
        started,
    )


def benchmark_reasoning_brief_answer_use_policy_blocks_conflicts(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    weak = make_record(
        tier="work",
        title="Benchmark answer policy weak claim",
        body="Weak conflicting claim for answer-use policy.",
        scope="/benchmark/reasoning-answer-policy-conflict",
        tags="benchmark,reasoning,answer,policy,conflict",
        provenance_type="openchronicle",
        confidence="low",
    )
    strong = make_record(
        tier="knowledge",
        title="Benchmark answer policy strong claim",
        body=f"Strong conflicting claim for answer-use policy. contradicts: {weak['id']}",
        scope="/benchmark/reasoning-answer-policy-conflict",
        tags="benchmark,reasoning,answer,policy,conflict",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path="/tmp/benchmark-answer-policy-proof.md",
        confidence="high",
    )
    append_record(weak, store)
    append_record(strong, store)
    result = reasoning_brief(
        scope="/benchmark/reasoning-answer-policy-conflict",
        query="reasoning answer policy conflict",
        path=store,
    )
    policy = result["answer_use_policy"]
    ensure(not result["ready_for_answer"], "active conflicts should block answer readiness")
    ensure(policy["status"] == "answer_use_needs_verification", "policy should require verification")
    ensure(policy["answer_use_counts"] == {"do_not_cite": 2}, "active conflict participants should not be cited")
    ensure(set(policy["blocked_record_ids"]) == {weak["id"], strong["id"]}, "policy should name blocked ids")
    return pass_result(
        "reasoning_brief_answer_use_policy_blocks_conflicts",
        {
            "status": policy["status"],
            "blocked_count": len(policy["blocked_record_ids"]),
            "answer_use_counts": policy["answer_use_counts"],
        },
        started,
    )


def benchmark_reasoning_brief_answer_use_policy_allows_descriptive_noncausal_claims(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-brief-descriptive-proof.md"
    proof.write_text("{}", encoding="utf-8")
    first = make_record(
        tier="work",
        title="Benchmark descriptive answer policy work",
        body="Selected source-backed records with evidence may be cited for descriptive claims.",
        scope="/benchmark/reasoning-answer-policy-descriptive",
        tags="benchmark,reasoning,answer,policy,descriptive,evidence",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    second = make_record(
        tier="knowledge",
        title="Benchmark descriptive answer policy knowledge",
        body="Citation policy includes selected evidence paths for memory-backed descriptive claims.",
        scope="/benchmark/reasoning-answer-policy-descriptive",
        tags="benchmark,reasoning,answer,policy,descriptive,evidence",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(first, store)
    append_record(second, store)
    result = reasoning_brief(
        claims_json=json.dumps({"claims": ["selected source-backed records with evidence may be cited"]}),
        scope="/benchmark/reasoning-answer-policy-descriptive",
        query="answer policy descriptive evidence",
        path=store,
    )
    policy = result["answer_use_policy"]
    ensure(result["ready_for_answer"], "descriptive supported claims should not require causal edges")
    ensure(result["status"] == "reasoning_brief_ready", "status should align with ready_for_answer")
    ensure(result["causal_hypotheses"]["status"] == "no_causal_hypotheses", "fixture should have no causal edges")
    ensure(policy["status"] == "answer_use_ready", "answer-use policy should allow ready descriptive evidence")
    ensure(policy["answer_use_counts"] == {"cite": 2}, "ready descriptive records should be citable")
    return pass_result(
        "reasoning_brief_answer_use_policy_allows_descriptive_noncausal_claims",
        {
            "status": result["status"],
            "ready_for_answer": result["ready_for_answer"],
            "causal_hypotheses_status": result["causal_hypotheses"]["status"],
            "answer_use_counts": policy["answer_use_counts"],
        },
        started,
    )


def benchmark_reasoning_eval_requires_ready_brief_and_evidence(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-eval-proof.md"
    proof.write_text("{}", encoding="utf-8")
    target = make_record(
        tier="knowledge",
        title="Benchmark reasoning eval source cache receipt",
        body="Verified source cache receipt for reasoning eval answer improvement.",
        scope="/benchmark/reasoning-eval",
        tags="benchmark,reasoning,eval,answer,source,cache,receipt",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source = make_record(
        tier="work",
        title="Benchmark reasoning eval answer improvement",
        body=f"Reasoning eval answer improvement uses source cache receipt. depends on: {target['id']}",
        scope="/benchmark/reasoning-eval",
        tags="benchmark,reasoning,eval,answer,source,cache,receipt",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(target, store)
    append_record(source, store)
    result = reasoning_eval(
        claims_json=json.dumps({"claims": ["Reasoning eval answer improvement uses source cache receipt"]}),
        scope="/benchmark/reasoning-eval",
        query="reasoning eval answer source cache receipt",
        baseline_answer="It probably improved.",
        memory_answer=(
            "Reasoning eval answer improvement uses source cache receipt. "
            f"Evidence: {proof}. Verify live proof boundaries separately."
        ),
        required_terms="reasoning eval,source cache,answer improvement",
        path=store,
    )
    ensure(result["ok"], "reasoning eval should pass with ready brief and cited evidence")
    ensure(result["status"] == "reasoning_answer_improved", "reasoning eval should report improved status")
    ensure(result["ready_for_answer"], "reasoning eval should require ready_for_answer")
    ensure(
        result["reasoning_evidence"]["cited_evidence_paths"] == [str(proof)],
        "reasoning eval should cite selected reasoning evidence",
    )
    ensure("not prove model reasoning" in result["claim_boundary"], "reasoning eval should preserve proof boundary")
    return pass_result(
        "reasoning_eval_requires_ready_brief_and_evidence",
        {
            "status": result["status"],
            "ready_for_answer": result["ready_for_answer"],
            "reasoning_status": result["reasoning_status"],
            "answer_eval_status": result["answer_eval_status"],
            "cited_evidence_count": result["reasoning_evidence"]["cited_evidence_count"],
        },
        started,
    )


def benchmark_reasoning_eval_rejects_context_only_proof_blur(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-context-only-proof.md"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark context-only identity hint",
            body="OpenChronicle screen context suggested the item identity might be a studio glass vase.",
            scope="/benchmark/reasoning-context-only",
            tags="benchmark,reasoning,context,identity,glass,vase",
            provenance_type="openchronicle",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = reasoning_eval(
        claims_json=json.dumps({"claims": ["item identity is studio glass vase"]}),
        scope="/benchmark/reasoning-context-only",
        query="context identity glass vase",
        baseline_answer="It might be a vase.",
        memory_answer=(
            "OpenChronicle verified the item identity as a studio glass vase. "
            f"Evidence: {proof}. This is proof of the identity."
        ),
        required_terms="item identity,studio glass,vase",
        path=store,
    )
    ensure(not result["ok"], "context-only proof blur should fail reasoning eval")
    ensure(result["status"] == "reasoning_answer_not_proven", "proof blur should not be marked improved")
    ensure(
        result["proof_boundary_status"]["status"] == "proof_boundary_blur_detected",
        "proof-boundary status should expose the blur",
    )
    ensure(
        "context_only_memory_presented_as_proof" in result["recommended_next_checks"],
        "recommended checks should name context-only proof blur",
    )
    return pass_result(
        "reasoning_eval_rejects_context_only_proof_blur",
        {
            "status": result["status"],
            "proof_boundary_status": result["proof_boundary_status"]["status"],
            "recommended_next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_reasoning_eval_rejects_answer_contract_blocked_pricing_action(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-eval-contract-pricing-proof.json"
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="learning",
        title="Benchmark reasoning eval contract pricing gate",
        body="Use logo, code, material, glass, wood, trim and style details before pricing.",
        scope="/benchmark/reasoning-eval-contract-pricing",
        tags="identify,item,logo,code,glass,wood,trim,style,pricing",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    result = reasoning_eval(
        scope="/benchmark/reasoning-eval-contract-pricing",
        query="identify item logo code glass wood trim style pricing",
        baseline_answer="It might have value.",
        memory_answer=(
            "This item is worth about $120 based on style. "
            f"Evidence: {proof}. Verify live proof boundaries separately."
        ),
        required_terms="item,style,pricing",
        path=store,
    )
    compliance = result["answer_contract_compliance"]
    ensure(not result["ok"], "reasoning eval should reject answer-contract blocked actions")
    ensure(compliance["status"] == "answer_contract_violation", "contract compliance should report violation")
    ensure(
        "remove_answer_contract_blocked_actions" in result["recommended_next_checks"],
        "contract violation should produce blocked-action next check",
    )
    return pass_result(
        "reasoning_eval_rejects_answer_contract_blocked_pricing_action",
        {
            "status": result["status"],
            "contract_status": compliance["status"],
            "blocked_action_count": len(compliance["blocked_action_violations"]),
        },
        started,
    )


def benchmark_reasoning_eval_requires_ready_causal_hypotheses_for_causal_answer(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-causal-answer-proof.md"
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark reasoning causal answer source",
            body="Source cache proof documents the release outcome for reasoning eval.",
            scope="/benchmark/reasoning-causal-answer",
            tags="benchmark,reasoning,answer,source,cache,release",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    result = reasoning_eval(
        scope="/benchmark/reasoning-causal-answer",
        query="reasoning answer release source cache",
        baseline_answer="The release happened.",
        memory_answer=(
            "The release was caused by source cache proof for reasoning eval. "
            f"Evidence: {proof}. Verify live proof boundaries separately."
        ),
        required_terms="release,source cache,reasoning eval",
        path=store,
    )
    ensure(not result["ok"], "causal answer without ready causal hypotheses should fail")
    ensure(
        result["causal_answer_policy"]["status"] == "causal_answer_needs_verification",
        "causal-answer policy should expose the missing causal hypothesis gate",
    )
    ensure(
        "require_ready_causal_hypotheses_before_causal_answer" in result["recommended_next_checks"],
        "recommended checks should require ready causal hypotheses",
    )
    return pass_result(
        "reasoning_eval_requires_ready_causal_hypotheses_for_causal_answer",
        {
            "status": result["status"],
            "causal_answer_status": result["causal_answer_policy"]["status"],
            "recommended_next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_reasoning_eval_suite_mixed_case_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    ready_proof = store.parent / "reasoning-suite-ready-proof.md"
    context_proof = store.parent / "reasoning-suite-context-proof.md"
    contract_proof = store.parent / "reasoning-suite-contract-proof.md"
    ready_proof.write_text("{}", encoding="utf-8")
    context_proof.write_text("{}", encoding="utf-8")
    contract_proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark reasoning suite ready fact",
            body="Reasoning suite ready fact requires source-backed evidence citation.",
            scope="/benchmark/reasoning-suite/ready",
            tags="benchmark,reasoning,suite,ready,evidence",
            provenance_type="source_file",
            provenance="benchmark fixture",
            evidence_path=str(ready_proof),
            confidence="high",
        ),
        store,
    )
    append_record(
        make_record(
            tier="knowledge",
            title="Benchmark reasoning suite context-only hint",
            body="OpenChronicle screen context suggested the item identity might be a studio glass vase.",
            scope="/benchmark/reasoning-suite/context",
            tags="benchmark,reasoning,suite,context,identity",
            provenance_type="openchronicle",
            provenance="benchmark fixture",
            evidence_path=str(context_proof),
            confidence="high",
        ),
        store,
    )
    append_record(
        make_record(
            tier="learning",
            title="Benchmark reasoning suite contract pricing gate",
            body="Use logo, code, material, glass, wood, trim and style details before pricing.",
            scope="/benchmark/reasoning-suite/contract",
            tags="benchmark,reasoning,suite,identify,item,logo,code,glass,wood,trim,style,pricing",
            provenance_type="verified_command",
            provenance="benchmark fixture",
            evidence_path=str(contract_proof),
            confidence="high",
        ),
        store,
    )
    result = reasoning_eval_suite(
        cases_json=json.dumps(
            [
                {
                    "id": "ready-missing-citation",
                    "claims": ["Reasoning suite ready fact requires source-backed evidence citation"],
                    "scope": "/benchmark/reasoning-suite/ready",
                    "query": "ready evidence citation",
                    "baseline_answer": "It improved.",
                    "memory_answer": (
                        "Reasoning suite ready fact requires source-backed evidence citation. "
                        "Evidence: source file. Verify live proof boundaries separately."
                    ),
                    "required_terms": "source-backed evidence,citation,reasoning suite",
                },
                {
                    "id": "context-proof-blur",
                    "claims": ["item identity is studio glass vase"],
                    "scope": "/benchmark/reasoning-suite/context",
                    "query": "context identity glass vase",
                    "baseline_answer": "It might be a vase.",
                    "memory_answer": (
                        "OpenChronicle verified the item identity as a studio glass vase. "
                        f"Evidence: {context_proof}. This is proof of the identity."
                    ),
                    "required_terms": "item identity,studio glass,vase",
                },
                {
                    "id": "contract-blocked-pricing",
                    "scope": "/benchmark/reasoning-suite/contract",
                    "query": "identify item logo code glass wood trim style pricing",
                    "baseline_answer": "It might have value.",
                    "memory_answer": (
                        "This item is worth about $120 based on style. "
                        f"Evidence: {contract_proof}. Verify live proof boundaries separately."
                    ),
                    "required_terms": "item,style,pricing",
                },
            ]
        ),
        path=store,
    )
    ensure(not result["ok"], "mixed suite should fail when any reasoning case is not proven")
    ensure(result["failed_count"] == 3, "suite should expose all failed cases")
    ensure(
        result["proof_boundary_failed_case_ids"] == ["context-proof-blur"],
        "suite should classify proof-boundary failures",
    )
    ensure(
        result["missing_evidence_case_ids"] == ["ready-missing-citation"],
        "suite should classify missing evidence failures",
    )
    ensure(
        result["answer_contract_failed_case_ids"] == ["contract-blocked-pricing"],
        "suite should classify answer-contract failures",
    )
    ensure(result["conflict_failed_case_ids"] == [], "mixed suite should not invent conflict failures")
    ensure(
        "fix_proof_boundary_blur_before_suite_pass" in result["recommended_next_checks"],
        "suite should recommend proof-boundary repair",
    )
    return pass_result(
        "reasoning_eval_suite_mixed_case_gate",
        {
            "status": result["status"],
            "failed_case_ids": result["failed_case_ids"],
            "proof_boundary_failed_case_ids": result["proof_boundary_failed_case_ids"],
            "missing_evidence_case_ids": result["missing_evidence_case_ids"],
            "answer_contract_failed_case_ids": result["answer_contract_failed_case_ids"],
            "conflict_failed_case_ids": result["conflict_failed_case_ids"],
        },
        started,
    )


def benchmark_reasoning_eval_suite_conflict_category_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    weak_proof = store.parent / "reasoning-suite-conflict-weak-proof.md"
    strong_proof = store.parent / "reasoning-suite-conflict-strong-proof.md"
    weak_proof.write_text("{}", encoding="utf-8")
    strong_proof.write_text("{}", encoding="utf-8")
    weak = make_record(
        tier="knowledge",
        title="Benchmark reasoning suite weak active claim",
        body="Reasoning suite conflict claim says the launch is not ready.",
        scope="/benchmark/reasoning-suite/conflict",
        tags="benchmark,reasoning,suite,conflict,launch",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(weak_proof),
        confidence="high",
    )
    strong = make_record(
        tier="knowledge",
        title="Benchmark reasoning suite strong active claim",
        body=f"Reasoning suite conflict claim says the launch is ready. Contradicts: {weak['id']}",
        scope="/benchmark/reasoning-suite/conflict",
        tags="benchmark,reasoning,suite,conflict,launch",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(strong_proof),
        confidence="high",
    )
    append_record(weak, store)
    append_record(strong, store)
    result = reasoning_eval_suite(
        cases_json=json.dumps(
            [
                {
                    "id": "active-conflict",
                    "claims": ["Reasoning suite conflict claim says the launch is ready"],
                    "scope": "/benchmark/reasoning-suite/conflict",
                    "query": "reasoning suite conflict launch ready",
                    "baseline_answer": "The launch status is unclear.",
                    "memory_answer": (
                        "Reasoning suite conflict claim says the launch is ready. "
                        f"Evidence: {weak_proof}. Evidence: {strong_proof}. "
                        "Verify live proof boundaries separately."
                    ),
                    "required_terms": "reasoning suite,conflict,launch,ready",
                }
            ]
        ),
        path=store,
    )
    ensure(not result["ok"], "conflicted suite case should fail")
    ensure(result["failed_case_ids"] == ["active-conflict"], "suite should expose conflict failed case")
    ensure(result["conflict_failed_case_ids"] == ["active-conflict"], "suite should classify conflict failures")
    ensure(result["proof_boundary_failed_case_ids"] == [], "conflict case should not blur proof boundaries")
    ensure(result["missing_evidence_case_ids"] == [], "conflict case should cite selected evidence")
    ensure(result["cases"][0]["active_contradiction_count"] == 1, "case should carry contradiction count")
    ensure(
        "resolve_suite_conflicts_or_supersede_records" in result["recommended_next_checks"],
        "suite should recommend conflict resolution",
    )
    return pass_result(
        "reasoning_eval_suite_conflict_category_gate",
        {
            "status": result["status"],
            "failed_case_ids": result["failed_case_ids"],
            "conflict_failed_case_ids": result["conflict_failed_case_ids"],
            "active_contradiction_count": result["cases"][0]["active_contradiction_count"],
        },
        started,
    )


def benchmark_reasoning_eval_suite_causal_memory_lift(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "reasoning-suite-causal-lift-proof.md"
    proof.write_text("{}", encoding="utf-8")
    target = make_record(
        tier="knowledge",
        title="Benchmark reasoning suite causal lift target",
        body="Verified source cache target for causal memory lift.",
        scope="/benchmark/reasoning-suite/causal-lift",
        tags="benchmark,reasoning,suite,causal,lift,source,cache",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    source = make_record(
        tier="work",
        title="Benchmark reasoning suite causal lift source",
        body=f"Causal memory lift source caused by source cache target. caused by: {target['id']}",
        scope="/benchmark/reasoning-suite/causal-lift",
        tags="benchmark,reasoning,suite,causal,lift,source,cache",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(target, store)
    append_record(source, store)
    result = reasoning_eval_suite(
        cases_json=json.dumps(
            [
                {
                    "id": "causal-lift",
                    "claims": ["Causal memory lift source caused by source cache target"],
                    "scope": "/benchmark/reasoning-suite/causal-lift",
                    "query": "causal memory lift source cache target",
                    "baseline_answer": "The source changed.",
                    "memory_answer": (
                        "Causal memory lift source was caused by source cache target. "
                        f"Evidence: {proof}. Verify live proof boundaries separately."
                    ),
                    "required_terms": "causal memory lift,source cache,target",
                }
            ]
        ),
        path=store,
    )
    ensure(result["ok"], "causal lift suite should pass with ready causal evidence")
    ensure(result["causal_memory_lift_case_count"] == 1, "suite should count causal lift cases")
    ensure(result["causal_memory_lift_case_ids"] == ["causal-lift"], "suite should identify causal lift cases")
    ensure(result["total_causal_evidence_path_count"] == 1, "suite should count ready causal evidence paths")
    ensure(result["total_causal_evidence_missing_node_count"] == 0, "suite should not hide missing causal evidence")
    ensure(result["cases"][0]["causal_answer_status"] == "causal_answer_ready", "causal answer should be ready")
    ensure(result["cases"][0]["causal_evidence_status"] == "causal_paths_ready", "causal evidence should be ready")
    ensure(
        result["cases"][0]["memory_attribution_status"] == "ready_causal_memory_attribution",
        "suite should attribute improvement to ready causal memory evidence",
    )
    ensure(result["causal_memory_attribution_case_count"] == 1, "suite should count causal attribution")
    ensure(result["descriptive_memory_attribution_case_count"] == 0, "suite should not blur causal/descriptive lift")
    return pass_result(
        "reasoning_eval_suite_causal_memory_lift",
        {
            "status": result["status"],
            "causal_memory_lift_case_count": result["causal_memory_lift_case_count"],
            "causal_memory_lift_case_ids": result["causal_memory_lift_case_ids"],
            "causal_memory_attribution_case_count": result["causal_memory_attribution_case_count"],
            "total_causal_evidence_path_count": result["total_causal_evidence_path_count"],
            "total_causal_evidence_missing_node_count": result["total_causal_evidence_missing_node_count"],
        },
        started,
    )


def benchmark_memory_graph_audit_warnings(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    record = make_record(
        tier="work",
        title="Benchmark graph audit task",
        body="Depends on: mem_deadbeefdeadbeef",
        scope="/benchmark/graph-audit",
        tags="benchmark,graph",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(store.parent / "memory-graph-audit-proof.json"),
        confidence="high",
    )
    append_record(record, store)
    result = graph_audit(scope="/benchmark/graph-audit", query="graph", max_isolated_ratio=0.25, path=store)
    ensure(not result["ok"], "graph audit should warn for dangling references")
    ensure(result["dangling_reference_count"] == 1, "graph audit should count dangling explicit refs")
    ensure(result["isolated_node_count"] == 1, "graph audit should count isolated nodes")
    return pass_result(
        "memory_graph_audit_warnings",
        {
            "status": result["status"],
            "warning_codes": [warning["code"] for warning in result["warnings"]],
            "dangling_reference_count": result["dangling_reference_count"],
            "isolated_ratio": result["isolated_ratio"],
        },
        started,
    )


def benchmark_memory_graph_audit_conflict_hygiene(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    old = make_record(
        tier="knowledge",
        title="Benchmark stale graph claim",
        body="Older claim that should not stay active after replacement.",
        scope="/benchmark/graph-conflict",
        tags="benchmark,graph,conflict",
        provenance_type="user_or_agent_observation",
        provenance="benchmark fixture",
        confidence="medium",
    )
    replacement = make_record(
        tier="knowledge",
        title="Benchmark stronger graph claim",
        body="placeholder",
        scope="/benchmark/graph-conflict",
        tags="benchmark,graph,conflict",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path="/tmp/graph-conflict-proof.md",
        confidence="high",
    )
    replacement["body"] = f"Supersedes: {old['id']}\nContradicts: {old['id']}"
    append_record(old, store)
    append_record(replacement, store)
    result = graph_audit(scope="/benchmark/graph-conflict", query="graph", path=store)
    ensure(not result["ok"], "graph audit should warn for active conflict hygiene issues")
    ensure(result["active_superseded_count"] == 1, "audit should count active superseded records")
    ensure(result["active_contradiction_count"] == 1, "audit should count active contradictions")
    ensure(result["active_contradictions"][0]["stronger_record"] == replacement["id"], "stronger record mismatch")
    plan = result["resolution_plan"]
    ensure(plan["status"] == "resolution_actions_needed", "audit should produce a resolution plan")
    ensure(plan["action_count"] == 2, "supersede plus contradiction should produce two actions")
    ensure(plan["actions"][0]["type"] == "mark_superseded", "first action should mark explicit superseded target")
    ensure(
        plan["actions"][1]["type"] == "supersede_weaker_record",
        "second action should supersede weaker contradiction",
    )
    ensure("append-only guidance" in plan["claim_boundary"], "resolution plan should preserve append-only boundary")
    contract = result["runtime_contract"]
    ensure(contract["behavior_contract_version"] == "graph_audit.v5", "graph audit contract should expose v5 behavior")
    ensure("decision_context_summary" in contract["behavior_features"], "graph audit should advertise decision context")
    ensure("path_use_ledger" in contract["behavior_features"], "graph audit should advertise path-use ledger")
    ensure(contract["conflict_resolution_plan"], "graph audit contract should advertise resolution plan behavior")
    return pass_result(
        "memory_graph_audit_conflict_hygiene",
        {
            "active_superseded_count": result["active_superseded_count"],
            "active_contradiction_count": result["active_contradiction_count"],
            "stronger_record": result["active_contradictions"][0]["stronger_record"],
            "resolution_action_count": plan["action_count"],
            "behavior_contract_version": contract["behavior_contract_version"],
            "warning_codes": [warning["code"] for warning in result["warnings"]],
        },
        started,
    )


def benchmark_graph_audit_scoped_supersession_outside_selection(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "graph-scoped-supersession-proof.md"
    proof.write_text("{}", encoding="utf-8")
    old = make_record(
        tier="knowledge",
        title="Benchmark legacy launch proof",
        body="Legacy launch proof says the release is ready.",
        scope="/benchmark/graph-scoped-supersession",
        tags="benchmark,legacy,launch",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    replacement = make_record(
        tier="knowledge",
        title="Benchmark replacement launch proof",
        body=f"Replacement record supersedes: {old['id']}",
        scope="/benchmark/graph-scoped-supersession",
        tags="benchmark,replacement",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(old, store)
    append_record(replacement, store)
    result = graph_audit(
        scope="/benchmark/graph-scoped-supersession",
        query="legacy launch proof",
        path=store,
    )
    ensure(not result["ok"], "scoped supersession outside selection should warn")
    ensure(result["active_superseded_count"] == 1, "audit should count selected active superseded target")
    ensure(result["active_superseded_records"][0]["target"] == old["id"], "old selected record should be target")
    ensure(
        result["resolution_plan"]["actions"][0]["record"] == old["id"],
        "resolution plan should mark selected old record",
    )
    return pass_result(
        "graph_audit_scoped_supersession_outside_selection",
        {
            "active_superseded_count": result["active_superseded_count"],
            "warning_codes": [item["code"] for item in result["warnings"]],
            "resolution_action": result["resolution_plan"]["actions"][0]["type"],
        },
        started,
    )


def benchmark_memory_graph_ranked_window(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "memory-graph-rank-proof.json"
    proof.write_text("{}", encoding="utf-8")
    task = make_record(
        tier="work",
        title="Benchmark graph ranked task",
        body="Graph ranked task.",
        scope="/benchmark/graph-rank",
        tags="benchmark,graph,rank,shared,bulk,alpha,beta",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    lesson = make_record(
        tier="learning",
        title="Benchmark graph ranked lesson",
        body="Symptom: noisy graph. Fix: ranked graph window. Proof: benchmark.",
        scope="/benchmark/graph-rank",
        tags="benchmark,graph,rank,shared,bulk,alpha,beta",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    task["body"] = f"Depends on: {lesson['id']}"
    append_record(task, store)
    append_record(lesson, store)
    for index in range(3):
        append_record(
            make_record(
                tier="work",
                title=f"Benchmark graph distractor {index}",
                body="Graph distractor creates tag and scope edges.",
                scope="/benchmark/graph-rank",
                tags="benchmark,graph,rank,shared,bulk,alpha,beta",
                provenance_type="verified_command",
                provenance="benchmark fixture",
                confidence="high",
            ),
            store,
        )
    result = memory_graph(scope="/benchmark/graph-rank", query="graph", max_edges=2, path=store)
    edge_types = [edge["type"] for edge in result["edges"]]
    ensure(result["truncated_edges"], "ranked graph fixture should exercise edge truncation")
    ensure(edge_types == ["depends_on", "shares_evidence"], "tight graph window should keep reasoning edges")
    return pass_result(
        "memory_graph_ranked_window",
        {
            "edge_types": edge_types,
            "edge_type_counts": result["edge_type_counts"],
            "truncated_edges": result["truncated_edges"],
        },
        started,
    )


def benchmark_memory_graph_audit_expansion_plan(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "memory-graph-expand-proof.json"
    proof.write_text("{}", encoding="utf-8")
    task = make_record(
        tier="work",
        title="Benchmark graph expand task",
        body="Graph expand task.",
        scope="/benchmark/graph-expand",
        tags="benchmark,graph,expand,shared,bulk",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    lesson = make_record(
        tier="learning",
        title="Benchmark graph expand lesson",
        body="Symptom: truncated graph. Fix: expansion plan. Proof: benchmark.",
        scope="/benchmark/graph-expand",
        tags="benchmark,graph,expand,shared,bulk",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    task["body"] = f"Depends on: {lesson['id']}"
    append_record(task, store)
    append_record(lesson, store)
    for index in range(3):
        append_record(
            make_record(
                tier="work",
                title=f"Benchmark graph expand distractor {index}",
                body="Graph expand distractor creates tag and scope edges.",
                scope="/benchmark/graph-expand",
                tags="benchmark,graph,expand,shared,bulk",
                provenance_type="verified_command",
                provenance="benchmark fixture",
                confidence="high",
            ),
            store,
        )
    result = graph_audit(scope="/benchmark/graph-expand", query="graph", max_edges=2, path=store)
    plan = result["expansion_plan"]
    edge_types = [edge["type"] for edge in plan["seed_edges"]]
    ensure(not result["ok"], "truncated audit fixture should warn")
    ensure(plan["status"] == "expand_from_ranked_edges", "audit should suggest ranked expansion")
    ensure(edge_types == ["depends_on", "shares_evidence"], "expansion should seed reasoning edges")
    ensure(plan["follow_up"][0]["args"]["max_edges"] == 4, "expansion should double the edge window")
    return pass_result(
        "memory_graph_audit_expansion_plan",
        {
            "edge_types": edge_types,
            "seed_node_count": len(plan["seed_nodes"]),
            "follow_up_count": len(plan["follow_up"]),
        },
        started,
    )


def benchmark_store_audit_health(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    record = make_record(
        tier="learning",
        title="Benchmark store audit lesson",
        body="Symptom: store drift. Fix: audit the JSONL source. Proof: benchmark passed.",
        scope="/benchmark/store-audit",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path="/tmp/store-audit-proof.txt",
        confidence="high",
    )
    append_record(record, store)
    audit = store_audit(path=store)
    ensure(audit["ok"], "store audit should accept valid benchmark records")
    ensure(audit["violation_count"] == 0, "store audit should not report violations")
    return pass_result(
        "store_audit_health",
        {"record_count": audit["record_count"], "warning_count": audit["warning_count"]},
        started,
    )


def benchmark_evidence_audit_health(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "evidence-audit-proof.json"
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="knowledge",
        title="Benchmark evidence-backed fact",
        body="Evidence path exists.",
        scope="/benchmark/evidence-audit",
        provenance_type="source_file",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    audit = evidence_audit(path=store, scope="/benchmark/evidence-audit")
    ensure(audit["ok"], "evidence audit should accept existing evidence path")
    ensure(audit["existing_count"] >= 1, "evidence audit should count existing path")
    return pass_result(
        "evidence_audit_health",
        {"existing_count": audit["existing_count"], "warning_count": audit["warning_count"]},
        started,
    )


def benchmark_evidence_repair_lifecycle(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    missing = store.parent / f"{store.stem}-missing-evidence-proof.md"
    receipt = store.parent / f"{store.stem}-replacement-evidence-receipt.json"
    missing.unlink(missing_ok=True)
    receipt.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="learning",
        title="Benchmark evidence repair lesson",
        body="Symptom: stale evidence path. Fix: create a receipt index. Proof: benchmark.",
        scope="/benchmark/evidence-repair",
        provenance_type="verified_command",
        provenance="benchmark fixture",
        evidence_path=str(missing),
        confidence="high",
    )
    append_record(record, store)
    plan = evidence_repair(
        path=store,
        scope="/benchmark/evidence-repair",
        receipt_path=str(receipt),
        allowed_root=str(store.parent),
    )
    created = evidence_repair(
        path=store,
        scope="/benchmark/evidence-repair",
        receipt_path=str(receipt),
        allowed_root=str(store.parent),
        create_indexes=True,
    )
    audit = evidence_audit(path=store, scope="/benchmark/evidence-repair", strict=True)
    ensure(plan["status"] == "evidence_repair_plan", "repair should dry-run by default")
    ensure(created["status"] == "evidence_repair_indexes_created", "repair should create index on request")
    ensure(audit["ok"], "created receipt index should satisfy strict evidence audit")
    return pass_result(
        "evidence_repair_lifecycle",
        {
            "plan_action": plan["actions"][0]["action"],
            "created_count": created["created_count"],
            "audit_status": audit["status"],
        },
        started,
    )


def benchmark_status_filtered_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    candidate = make_record(
        tier="knowledge",
        title="Benchmark candidate source lead",
        body="Potential fact needs verification before durable use.",
        scope="/benchmark/filter",
        tags="benchmark,source",
        status="candidate",
    )
    active = make_record(
        tier="knowledge",
        title="Benchmark active source fact",
        body="Verified fact ready for durable use.",
        scope="/benchmark/filter",
        tags="benchmark,source",
        status="active",
    )
    append_record(candidate, store)
    append_record(active, store)
    search = search_records(
        query="benchmark source",
        tier="knowledge",
        scope="/benchmark/filter",
        status="candidate",
        path=store,
    )
    projected = project(scope="/benchmark/filter", status="candidate", path=store)["projection"]
    ensure(search["count"] == 1, "status-filtered search should isolate one candidate")
    ensure(search["records"][0]["id"] == candidate["id"], "search should return candidate record")
    ensure(projected["status_counts"] == {"candidate": 1}, "status-filtered projection should count candidates")
    ensure(projected["recent"][0]["id"] == candidate["id"], "projection should include candidate record")
    return pass_result(
        "status_filtered_retrieval",
        {"search_count": search["count"], "status_counts": projected["status_counts"]},
        started,
    )


def benchmark_provenance_filtered_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    source_backed = make_record(
        tier="knowledge",
        title="Benchmark source-backed fact",
        body="Verified source proves the memory fabric cache behavior.",
        scope="/benchmark/provenance-filter",
        tags="benchmark,proof",
        provenance_type="source_file",
        evidence_path="/tmp/source.md",
    )
    screen_only = make_record(
        tier="knowledge",
        title="Benchmark screen-only lead",
        body="Screen context suggests the memory fabric cache behavior.",
        scope="/benchmark/provenance-filter",
        tags="benchmark,proof",
        provenance_type="screen_observation",
    )
    append_record(source_backed, store)
    append_record(screen_only, store)
    search = search_records(
        query="memory fabric cache",
        tier="knowledge",
        scope="/benchmark/provenance-filter",
        provenance_type="source_file",
        path=store,
    )
    projected = project(
        scope="/benchmark/provenance-filter",
        provenance_type="source_file",
        path=store,
    )["projection"]
    ensure(search["count"] == 1, "provenance-filtered search should isolate one source-backed record")
    ensure(search["records"][0]["id"] == source_backed["id"], "search should return source-backed record")
    ensure(projected["provenance_counts"] == {"source_file": 1}, "projection should count provenance type")
    ensure(projected["recent"][0]["provenance_type"] == "source_file", "projection should expose compact provenance")
    return pass_result(
        "provenance_filtered_retrieval",
        {"search_count": search["count"], "provenance_counts": projected["provenance_counts"]},
        started,
    )


def benchmark_semantic_provenance_gated_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    source_backed = make_record(
        tier="knowledge",
        title="Benchmark source cache live separation",
        body="Source cache live separation is verified by a receipt.",
        scope="/benchmark/semantic-filter",
        tags="benchmark,retrieval",
        provenance_type="source_file",
        provenance="benchmark fixture",
        evidence_path="/tmp/semantic-proof.md",
        confidence="high",
        verify_before_use=False,
    )
    screen_only = make_record(
        tier="knowledge",
        title="Benchmark proof boundary screen note",
        body="Proof boundary appears directly here but is only screen context.",
        scope="/benchmark/semantic-filter",
        tags="benchmark,retrieval",
        provenance_type="screen_observation",
        provenance="benchmark fixture",
        confidence="medium",
        verify_before_use=False,
    )
    append_record(source_backed, store)
    append_record(screen_only, store)
    result = search_records(
        query="proof boundary",
        tier="knowledge",
        scope="/benchmark/semantic-filter",
        provenance_type="source_file",
        confidence="high",
        verify_before_use="false",
        path=store,
    )
    ensure(result["count"] == 1, "semantic retrieval should still honor provenance/confidence gates")
    ensure(result["records"][0]["id"] == source_backed["id"], "semantic expansion should retrieve source-backed record")
    ensure(result["records"][0]["trust"]["status"] == "ready", "source-backed high-confidence record should be ready")
    ensure(
        "proof" in result["records"][0]["retrieval"]["matched_expansions"],
        "retrieval should expose matched expansion",
    )
    ensure(result["retrieval_gate"]["ok"], "ready filtered semantic retrieval should pass the retrieval gate")
    ensure(result["retrieval_gate"]["trust_counts"] == {"ready": 1}, "retrieval gate should count ready trust")
    ensure("not embedding" in result["semantic_query"]["claim_boundary"], "semantic claim boundary should be explicit")
    return pass_result(
        "semantic_provenance_gated_retrieval",
        {
            "search_count": result["count"],
            "matched_expansions": result["records"][0]["retrieval"]["matched_expansions"],
            "retrieval_gate": result["retrieval_gate"],
            "trust": result["records"][0]["trust"]["status"],
        },
        started,
    )


def benchmark_semantic_retrieval_gate_warns_on_context_only(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    context_only = make_record(
        tier="knowledge",
        title="Benchmark screen-only receipt lead",
        body="Receipt text appears only in screen context.",
        scope="/benchmark/semantic-gate",
        tags="benchmark,retrieval",
        provenance_type="screen_observation",
        provenance="benchmark fixture",
        confidence="medium",
        verify_before_use=False,
    )
    append_record(context_only, store)
    result = search_records(
        query="proof",
        tier="knowledge",
        scope="/benchmark/semantic-gate",
        path=store,
    )
    gate = result["retrieval_gate"]
    ensure(result["count"] == 1, "semantic-only query should retrieve the context lead")
    ensure(
        result["records"][0]["retrieval"]["match_kind"] == "semantic_only",
        "retrieval should mark semantic-only match",
    )
    ensure(not gate["ok"], "semantic-only context lead should not pass retrieval gate")
    ensure(gate["semantic_only_non_ready_count"] == 1, "gate should count semantic-only non-ready record")
    ensure(
        "verify_semantic_only_non_ready_matches_before_use" in gate["recommended_next_checks"],
        "gate should require verification before use",
    )
    return pass_result(
        "semantic_retrieval_gate_warns_on_context_only",
        {
            "match_kind_counts": gate["match_kind_counts"],
            "trust_counts": gate["trust_counts"],
            "recommended_next_checks": gate["recommended_next_checks"],
        },
        started,
    )


def benchmark_confidence_filtered_retrieval(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    ready = make_record(
        tier="knowledge",
        title="Benchmark ready source-backed fact",
        body="Verified source proves the memory fabric cache behavior.",
        scope="/benchmark/confidence-filter",
        tags="benchmark,ready",
        confidence="high",
        verify_before_use=False,
    )
    needs_check = make_record(
        tier="knowledge",
        title="Benchmark low-confidence lead",
        body="Needs verification before durable use.",
        scope="/benchmark/confidence-filter",
        tags="benchmark,ready",
        confidence="low",
        verify_before_use=True,
    )
    append_record(ready, store)
    append_record(needs_check, store)
    search = search_records(
        query="memory fabric",
        tier="knowledge",
        scope="/benchmark/confidence-filter",
        confidence="high",
        verify_before_use="false",
        path=store,
    )
    projected = project(
        scope="/benchmark/confidence-filter",
        confidence="high",
        verify_before_use="false",
        path=store,
    )["projection"]
    ensure(search["count"] == 1, "confidence-filtered search should isolate one ready record")
    ensure(search["records"][0]["id"] == ready["id"], "search should return high-confidence record")
    ensure(projected["confidence_counts"] == {"high": 1}, "projection should count confidence")
    ensure(projected["verify_before_use_counts"] == {"false": 1}, "projection should count verification state")
    return pass_result(
        "confidence_filtered_retrieval",
        {"search_count": search["count"], "confidence_counts": projected["confidence_counts"]},
        started,
    )


def benchmark_legacy_numeric_confidence_read_normalization(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    legacy = make_record(
        tier="knowledge",
        title="Benchmark legacy numeric confidence fact",
        body="Verified source proves legacy numeric confidence should map into high.",
        scope="/benchmark/legacy-confidence",
        tags="benchmark,legacy",
        confidence="high",
        verify_before_use=False,
    )
    legacy["confidence"] = "0.96"
    typo = make_record(
        tier="knowledge",
        title="Benchmark typo confidence note",
        body="Typo confidence must not look high.",
        scope="/benchmark/legacy-confidence",
        tags="benchmark,legacy",
        confidence="low",
        verify_before_use=True,
    )
    typo["confidence"] = "hgh"
    append_record(legacy, store)
    append_record(typo, store)
    search = search_records(
        query="legacy confidence",
        tier="knowledge",
        scope="/benchmark/legacy-confidence",
        confidence="high",
        verify_before_use="false",
        path=store,
    )
    projected = project(scope="/benchmark/legacy-confidence", path=store)["projection"]
    ensure(search["count"] == 1, "legacy numeric confidence should match high confidence filter")
    ensure(search["records"][0]["confidence"] == "high", "search should return normalized confidence")
    ensure(projected["confidence_counts"] == {"high": 1, "unknown": 1}, "projection should normalize counts")
    return pass_result(
        "legacy_numeric_confidence_read_normalization",
        {"search_count": search["count"], "confidence_counts": projected["confidence_counts"]},
        started,
    )


def benchmark_live_surface_schema_contract(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    advertised_tools = [MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS]
    stale_surface = {
        "memory_fabric_record": ["tier", "title", "body", "confidence", "store"],
        "memory_fabric_search": ["query", "tier", "scope", "limit", "store"],
        "memory_fabric_snapshot": ["scope", "limit", "store"],
        "memory_fabric_project": ["scope", "output", "limit", "store"],
        "memory_fabric_telemetry": ["output", "min_samples", "min_scenarios"],
    }
    result = live_exposure(advertised_tools, stale_surface)
    missing = result["surface"]["missing_params"]
    ensure(result["status"] == "stale_tool_schema", "stale live schemas should be explicit")
    ensure("operation" in missing["memory_fabric_telemetry"], "telemetry router should require operation")
    ensure("confidence" in missing["memory_fabric_search"], "search should require confidence filter")
    ensure("status" in missing["memory_fabric_record"], "record should require status parameter")
    return pass_result(
        "live_surface_schema_contract",
        {"status": result["status"], "stale_tool_count": len(missing)},
        started,
    )


def benchmark_truncated_live_surface_is_unproven_not_missing(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    advertised_tools = [MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS[:20]]
    result = live_exposure(advertised_tools, advertised_truncated=True)
    ensure(result["status"] == "surface_truncated_unproven", "capped discovery should be explicit")
    ensure(result["ok"] is None, "capped discovery should not prove success or failure")
    ensure(result["missing_tools"] == [], "capped discovery should not claim missing tools")
    ensure(result["unverified_tools"] == REQUIRED_LIVE_TOOLS[20:], "absent page entries should be unverified")
    ensure(not result["tool_exposure_checked"], "partial discovery should not count as full live proof")
    ensure(result["partial_tool_exposure_checked"], "partial discovery should be preserved")
    return pass_result(
        "truncated_live_surface_is_unproven_not_missing",
        {
            "status": result["status"],
            "advertised_count": result["advertised_count"],
            "unverified_tool_count": len(result["unverified_tools"]),
        },
        started,
    )


def benchmark_telemetry_status_ready_gate(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    operations = store.with_name("memory-fabric-ops.jsonl")
    usage = store.with_name("token-usage.jsonl")
    export = store.with_name("plugin-eval-usage.jsonl")
    capture = capture_representative_usage(output=str(operations))
    write_token_usage(usage, capture["scenarios"])
    result = telemetry_status(
        operations_input=str(operations),
        usage_input=[str(usage)],
        plugin_eval_output=str(export),
    )
    ensure(result["status"] == "ready_for_plugin_eval_observed_usage", "telemetry status should be ready")
    ensure(result["plugin_eval_observed_usage_ready"], "telemetry status should allow observed usage")
    ensure(export.exists(), "ready telemetry status should export Plugin Eval usage JSONL")
    return pass_result(
        "telemetry_status_ready_gate",
        {"status": result["status"], "token_sample_count": result["token_coverage"]["token_sample_count"]},
        started,
    )


def benchmark_telemetry_audit_diagnostics(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    events = token_usage_events(["record-learning-memory", "search-memory", "project-work-memory"])
    result = telemetry_audit(inline_json="[" + ",".join(events) + "]")
    ensure(result["status"] == "plugin_isolated_telemetry_ready", "telemetry audit should accept isolated rows")
    ensure(result["issue_counts"] == {}, "clean telemetry audit should have no issue counts")
    return pass_result(
        "telemetry_audit_diagnostics",
        {
            "status": result["status"],
            "sample_count": result["sample_count"],
            "plugin_isolated_sample_count": result["plugin_isolated_sample_count"],
        },
        started,
    )


def benchmark_release_report_local_ready_live_stale(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    current_doctor = root / "current-doctor.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark release proof",
        body="Release-local proof record.",
        scope="/benchmark/release",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/release", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 22, "failed": 0, "scenario_count": 22}), encoding="utf-8")
    current_doctor.write_text(
        json.dumps(
            {
                "live": {
                    "ok": False,
                    "status": "missing_tools",
                    "tool_exposure_checked": True,
                    "missing_tools": ["memory_fabric_release_report"],
                }
            }
        ),
        encoding="utf-8",
    )
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        current_doctor_json=str(current_doctor),
        evidence_scope="/benchmark/release",
        strict_evidence=True,
    )
    ensure(result["local_ok"], "release report should pass local readiness")
    ensure(not result["ok"], "stale live receipt should keep full release unready")
    ensure(result["status"] == "release_local_ready_live_stale", "release status should name stale live exposure")
    ensure(result["performance"]["ok"], "release report should stay under the performance gate")
    return pass_result(
        "release_report_local_ready_live_stale",
        {
            "status": result["status"],
            "local_ok": result["local_ok"],
            "live_status": result["current_live"]["status"],
            "elapsed_ms": result["performance"]["elapsed_ms"],
        },
        started,
    )


def benchmark_release_report_host_advertisement_stale_stdio_complete(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-host-ad-stale"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    current_doctor = root / "current-doctor.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    append_record(
        make_record(
            tier="work",
            title="Benchmark host-advertisement stale proof",
            body="Release proof where stdio is complete but host advertisement is stale.",
            scope="/benchmark/release-host-ad-stale",
            provenance_type="source_backed_agent_run",
            provenance="benchmark fixture",
            evidence_path=str(proof),
            confidence="high",
        ),
        store,
    )
    project(scope="/benchmark/release-host-ad-stale", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 22, "failed": 0, "scenario_count": 22}), encoding="utf-8")
    current_doctor.write_text(
        json.dumps(
            {
                "live": {
                    "ok": False,
                    "status": "missing_tools",
                    "tool_exposure_checked": True,
                    "missing_tools": ["memory_fabric_reasoning_eval_suite"],
                },
                "stdio": {
                    "ok": True,
                    "status": "stdio_tools_complete",
                    "tool_count": len(REQUIRED_LIVE_TOOLS),
                    "required_tool_count": len(REQUIRED_LIVE_TOOLS),
                    "missing_tools": [],
                },
            }
        ),
        encoding="utf-8",
    )
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        current_doctor_json=str(current_doctor),
        evidence_scope="/benchmark/release-host-ad-stale",
        strict_evidence=True,
    )
    attention_codes = [item["code"] for item in result["attention"]]
    ensure(result["status"] == "release_local_ready_live_stale", "host-ad stale remains live-stale")
    ensure("current_host_advertisement_stale" in attention_codes, "stdio-complete gap should be specific")
    ensure(
        result["reconnect"]["reason"] == "host_advertisement_stale_stdio_complete",
        "reconnect should not blame source/cache/server when stdio is complete",
    )
    return pass_result(
        "release_report_host_advertisement_stale_stdio_complete",
        {
            "status": result["status"],
            "attention_codes": attention_codes,
            "reconnect_reason": result["reconnect"]["reason"],
        },
        started,
    )


def benchmark_release_report_live_tool_schema_attention(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-schema-attention"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    current_doctor = root / "current-doctor.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark stale tool schema release proof",
        body="Release proof with stale live tool schema params.",
        scope="/benchmark/release-schema-attention",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/release-schema-attention", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 22, "failed": 0, "scenario_count": 22}), encoding="utf-8")
    current_doctor.write_text(
        json.dumps(
            {
                "live": {
                    "ok": False,
                    "status": "stale_tool_schema",
                    "tool_exposure_checked": True,
                    "advertised_count": len(REQUIRED_LIVE_TOOLS),
                    "missing_tools": [],
                    "surface_checked": True,
                    "surface": {
                        "surface_checked": True,
                        "missing_params": {
                            "memory_fabric_release_report": [
                                "hook_health_json",
                                "require_current_behavior",
                            ]
                        },
                        "unchecked_tools": [],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        current_doctor_json=str(current_doctor),
        evidence_scope="/benchmark/release-schema-attention",
        strict_evidence=True,
    )
    attention = [item for item in result["attention"] if item["code"] == "current_live_tool_schema_stale"]
    missing = result["current_live"]["missing_params"]["memory_fabric_release_report"]
    ensure(result["status"] == "release_local_ready_live_stale", "stale live tool schema should keep release stale")
    ensure(not result["ok"], "release should not pass with stale live tool schema")
    ensure(attention and attention[0]["blocking"], "stale tool schema attention should be blocking")
    ensure("require_current_behavior" in missing, "release schema drift should name require_current_behavior")
    return pass_result(
        "release_report_live_tool_schema_attention",
        {
            "status": result["status"],
            "attention_code": attention[0]["code"],
            "missing_params": missing,
        },
        started,
    )


def benchmark_release_report_mixed_live_freshness_attention(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    paths = release_fixture(
        store,
        "release-report-mixed-freshness",
        "/benchmark/release-mixed-freshness",
        "Benchmark mixed freshness proof",
        "Release proof where live version is fresh but behavior contract is stale.",
    )
    behavior = paths["root"] / "schema-contract-behavior.json"
    release_version = schema()["plugin_version"]
    behavior.write_text(
        json.dumps(
            {
                "ok": False,
                "status": "current_live_behavior_stale",
                "behavior": "memory_fabric_schema_release_report_contract",
                "expected_plugin_version": release_version,
                "current_live_plugin_version": release_version,
                "expected_contract_version": "release_report.v2",
                "current_live_contract_version": "",
                "missing_current_live_fields": [
                    "tool_contracts.memory_fabric_release_report.behavior_contract_version"
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_report(
        version=release_version,
        plugin_root=PLUGIN_ROOT,
        marketplace_path=paths["marketplace"],
        cache_root=paths["cache_root"],
        store=store,
        projection_input=str(paths["projection"]),
        plugin_eval_json=str(paths["plugin_eval"]),
        benchmark_json=str(paths["benchmark"]),
        current_behavior_json=str(behavior),
        advertised_tools=[MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS],
        evidence_scope="/benchmark/release-mixed-freshness",
        strict_evidence=True,
    )
    attention = [item for item in result["attention"] if item["code"] == "current_live_mixed_freshness"]
    ensure(
        result["live_freshness"]["status"] == "mixed_live_freshness_stale_behavior",
        "mixed freshness should be explicit",
    )
    ensure(result["live_freshness"]["version_fresh"], "fresh version evidence should be preserved")
    ensure(attention and attention[0]["blocking"], "mixed freshness attention should be blocking")
    ensure(not result["ok"], "mixed freshness should keep release unready")
    return pass_result(
        "release_report_mixed_live_freshness_attention",
        {
            "status": result["live_freshness"]["status"],
            "attention_code": attention[0]["code"],
            "version_fresh": result["live_freshness"]["version_fresh"],
        },
        started,
    )


def benchmark_release_report_truncated_live_surface_attention(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    paths = release_fixture(
        store,
        "release-report-truncated-live",
        "/benchmark/release-truncated-live",
        "Benchmark truncated live surface proof",
        "Release proof where live discovery is a bounded page, not a full surface.",
    )
    advertised_tools = [MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS[:20]]
    result = release_report(
        version=schema()["plugin_version"],
        plugin_root=PLUGIN_ROOT,
        marketplace_path=paths["marketplace"],
        cache_root=paths["cache_root"],
        store=store,
        projection_input=str(paths["projection"]),
        plugin_eval_json=str(paths["plugin_eval"]),
        benchmark_json=str(paths["benchmark"]),
        advertised_tools=advertised_tools,
        advertised_truncated=True,
        evidence_scope="/benchmark/release-truncated-live",
        strict_evidence=True,
    )
    attention = [item for item in result["attention"] if item["code"] == "current_live_surface_truncated_unproven"]
    ensure(result["status"] == "release_local_ready_live_unchecked", "truncated live discovery should stay unchecked")
    ensure(result["current_live"]["missing_tools"] == [], "truncated live discovery should not claim missing tools")
    ensure(result["current_live"]["unverified_tools"] == REQUIRED_LIVE_TOOLS[20:], "unseen tools should be unverified")
    ensure(attention and not attention[0]["blocking"], "truncated discovery attention should be nonblocking")
    return pass_result(
        "release_report_truncated_live_surface_attention",
        {
            "status": result["status"],
            "attention_code": attention[0]["code"],
            "unverified_tool_count": len(result["current_live"]["unverified_tools"]),
        },
        started,
    )


def benchmark_schema_behavior_receipt_mixed_freshness(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    source = schema()
    live = {
        "plugin_version": source["plugin_version"],
        "tool_contracts": {
            "memory_fabric_graph_audit": {"behavior_contract_version": "graph_audit.v2"},
            "memory_fabric_reasoning_eval": {"behavior_contract_version": "reasoning_eval.v1"},
            "memory_fabric_release_report": {"behavior_contract_version": "release_report.v2"},
        },
    }
    result = schema_behavior_receipt(
        live_schema_json=json.dumps(live),
        source_schema_json=json.dumps(source),
        behavior="memory_fabric_schema_contract",
    )
    ensure(result["status"] == "current_live_behavior_stale", "stale live schema should be explicit")
    ensure(result["expected_plugin_version"] == result["current_live_plugin_version"], "fresh version should survive")
    ensure(
        "tool_contracts.memory_fabric_release_report.handles_truncated_advertised_live_surfaces"
        in result["missing_current_live_fields"],
        "missing truncated-surface contract should be named",
    )
    ensure(
        "tool_contracts.memory_fabric_reasoning_eval.behavior_contract_version"
        in result["mismatched_current_live_fields"],
        "stale reasoning eval contract should be named",
    )
    return pass_result(
        "schema_behavior_receipt_mixed_freshness",
        {
            "status": result["status"],
            "missing_count": len(result["missing_current_live_fields"]),
            "mismatch_count": len(result["mismatched_current_live_fields"]),
        },
        started,
    )


def benchmark_behavior_case_causal_evidence_ledger(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / "behavior-case-causal-evidence"
    result = behavior_case(output_dir=str(root), output=str(root / "case-spec.json"))
    source = json.loads(Path(result["source_output_json"]).read_text(encoding="utf-8"))
    ensure(result["ok"], "behavior case should prepare successfully")
    ensure(result["live_tool"] == "memory_fabric_causal_audit", "behavior case should name the live MCP tool")
    ensure(
        source["evidence_contract_version"] == "causal_evidence_ledger.v1",
        "source output should carry causal evidence contract",
    )
    ensure(source["missing_evidence_node_count"] == 1, "source output should expose missing evidence node count")
    ensure(
        "causal_paths.0.evidence_ledger" in result["required_fields"],
        "behavior case should require live evidence ledger field",
    )
    ensure(
        result["behavior_receipt_args"]["source_json"] == result["source_output_json"],
        "behavior receipt args should point to source output",
    )
    return pass_result(
        "behavior_case_causal_evidence_ledger",
        {
            "case": result["case"],
            "behavior": result["behavior"],
            "source_status": source["status"],
            "missing_evidence_node_count": source["missing_evidence_node_count"],
            "required_field_count": len(result["required_fields"]),
        },
        started,
    )


def benchmark_release_report_inline_live_ready(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-inline"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark inline release proof",
        body="Release proof with inline live doctor.",
        scope="/benchmark/inline-release",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/inline-release", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 23, "failed": 0, "scenario_count": 23}), encoding="utf-8")
    advertised_tools = [
        MCP_TOOL_PREFIX + tool
        for tool in REQUIRED_LIVE_TOOLS
    ]
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        advertised_tools=advertised_tools,
        evidence_scope="/benchmark/inline-release",
        strict_evidence=True,
    )
    ensure(result["ok"], "inline live doctor should allow release readiness")
    ensure(result["status"] == "release_ready", "inline release status should be ready")
    ensure(result["current_live"]["source"] == "inline_doctor", "inline live source should be explicit")
    ensure(result["performance"]["ok"], "inline release report should stay under the performance gate")
    return pass_result(
        "release_report_inline_live_ready",
        {
            "status": result["status"],
            "advertised_tool_count": result["inputs"]["advertised_tool_count"],
            "elapsed_ms": result["performance"]["elapsed_ms"],
        },
        started,
    )


def benchmark_release_report_hook_health_receipt(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-hook-receipt"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    hook_receipt = root / "hook-health.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark hook receipt release proof",
        body="Release proof with explicit hook-health receipt.",
        scope="/benchmark/hook-receipt-release",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/hook-receipt-release", output=str(projection), path=store)
    hook_receipt.write_text(
        json.dumps(
            hook_health(
                path=store,
                projection_input=str(projection),
                evidence_scope="/benchmark/hook-receipt-release",
                strict_evidence=True,
            )
        ),
        encoding="utf-8",
    )
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 24, "failed": 0, "scenario_count": 24}), encoding="utf-8")
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        hook_health_json=str(hook_receipt),
        advertised_tools=[MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS],
        strict_evidence=True,
    )
    ensure(result["ok"], "hook-health receipt should allow release readiness")
    ensure(result["status"] == "release_ready", "hook-health receipt release status should be ready")
    ensure(result["hook_health"]["source"] == "receipt", "hook health source should be receipt")
    ensure(
        result["inputs"]["hook_health_json"] == str(hook_receipt),
        "release report should preserve hook receipt path",
    )
    return pass_result(
        "release_report_hook_health_receipt",
        {
            "status": result["status"],
            "hook_source": result["hook_health"]["source"],
            "hook_status": result["hook_health"]["status"],
        },
        started,
    )


def benchmark_release_report_live_behavior_attention(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-behavior-attention"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    current_doctor = root / "current-doctor.json"
    behavior = root / "behavior.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark live behavior attention proof",
        body="Release proof with stale live behavior attention.",
        scope="/benchmark/live-behavior-attention",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/live-behavior-attention", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 24, "failed": 0, "scenario_count": 24}), encoding="utf-8")
    current_doctor.write_text(
        json.dumps(
            {
                "live": {
                    "ok": True,
                    "status": "available",
                    "tool_exposure_checked": True,
                    "advertised_count": len(REQUIRED_LIVE_TOOLS),
                    "missing_tools": [],
                }
            }
        ),
        encoding="utf-8",
    )
    behavior.write_text(
        json.dumps(
            {
                "ok": False,
                "status": "current_live_behavior_stale",
                "behavior": "memory_fabric_thread_brief_readiness",
                "missing_current_live_fields": ["readiness"],
            }
        ),
        encoding="utf-8",
    )
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        current_doctor_json=str(current_doctor),
        current_behavior_json=str(behavior),
        evidence_scope="/benchmark/live-behavior-attention",
        strict_evidence=True,
    )
    attention = [item for item in result["attention"] if item["code"] == "current_live_behavior_stale"]
    ensure(result["status"] == "release_local_ready_live_stale", "behavior stale should keep release stale")
    ensure(attention and attention[0]["blocking"], "behavior stale should be blocking attention")
    ensure(
        attention[0]["stale_behaviors"] == ["memory_fabric_thread_brief_readiness"],
        "attention should name stale behavior",
    )
    ensure(attention[0]["missing_current_live_fields"] == ["readiness"], "attention should name missing live fields")
    return pass_result(
        "release_report_live_behavior_attention",
        {
            "status": result["status"],
            "attention_code": attention[0]["code"],
            "missing_current_live_fields": attention[0]["missing_current_live_fields"],
        },
        started,
    )


def benchmark_release_report_requires_behavior_receipt(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-release-report-behavior-required"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    cache_root = root / ".codex" / "plugins" / "cache"
    proof = root / "release-proof.json"
    projection = root / "release-projection.json"
    plugin_eval = root / "plugin-eval.json"
    benchmark = root / "benchmark.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "ralto-local",
                "plugins": [
                    {
                        "name": PLUGIN_NAME,
                        "source": {"source": "local", "path": str(PLUGIN_ROOT)},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache_sync(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        marketplace_name="ralto-local",
        execute=True,
    )
    proof.write_text("{}", encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark strict behavior release proof",
        body="Release proof requiring current-live behavior receipt.",
        scope="/benchmark/strict-behavior-release",
        provenance_type="source_backed_agent_run",
        provenance="benchmark fixture",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    project(scope="/benchmark/strict-behavior-release", output=str(projection), path=store)
    plugin_eval.write_text(json.dumps({"summary": {"score": 95, "grade": "A"}}), encoding="utf-8")
    benchmark.write_text(json.dumps({"ok": True, "passed": 24, "failed": 0, "scenario_count": 24}), encoding="utf-8")
    result = release_report(
        plugin_root=PLUGIN_ROOT,
        marketplace_path=marketplace,
        cache_root=cache_root,
        store=store,
        projection_input=str(projection),
        plugin_eval_json=str(plugin_eval),
        benchmark_json=str(benchmark),
        advertised_tools=[MCP_TOOL_PREFIX + tool for tool in REQUIRED_LIVE_TOOLS],
        evidence_scope="/benchmark/strict-behavior-release",
        strict_evidence=True,
        require_current_behavior=True,
    )
    attention = [item for item in result["attention"] if item["code"] == "current_live_behavior_missing"]
    ensure(
        result["status"] == "release_local_ready_live_stale",
        "missing behavior receipt should keep strict release stale",
    )
    ensure(not result["ok"], "strict release should not pass without behavior receipt")
    ensure(result["checks"]["current_live_behavior_required"], "strict behavior gate should be recorded")
    ensure(attention and attention[0]["blocking"], "missing behavior receipt should be blocking attention")
    return pass_result(
        "release_report_requires_behavior_receipt",
        {
            "status": result["status"],
            "attention_code": attention[0]["code"],
            "behavior_required": result["checks"]["current_live_behavior_required"],
        },
        started,
    )


def write_token_usage(path: Path, scenarios: list[str]) -> None:
    path.write_text("\n".join(token_usage_events(scenarios)) + "\n", encoding="utf-8")


def token_usage_events(scenarios: list[str]) -> list[str]:
    ordered = sorted(scenarios)
    return [json.dumps(token_usage_event(ordered[index % len(ordered)], index)) for index in range(6)]


def token_usage_event(scenario: str, index: int) -> dict[str, Any]:
    return {
        "type": "response.done",
        "metadata": {
            "scenario": scenario,
            "plugin": "codex-memory-fabric",
            "isolation": "plugin",
            "plugin_isolated": True,
        },
        "response": {"usage": {"input_tokens": 10 + index, "output_tokens": 2, "total_tokens": 12 + index}},
    }


def benchmark_status_vocabulary(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    expected = {"active", "candidate", "superseded", "archived"}
    schema_payload = schema()
    values = set(schema_payload["statuses"])
    ensure(values == expected, "schema should expose the typed status vocabulary")
    ensure(schema_payload["status_aliases"] == {"current": "active"}, "schema should expose status aliases")
    current = make_record(tier="work", title="Current status", body="Alias.", status="current")
    ensure(current["status"] == "active", "current status alias should normalize to active")
    try:
        make_record(tier="work", title="Bad status", body="Nope.", status="maybe")
    except ValueError:
        rejected = True
    else:
        rejected = False
    ensure(rejected, "invalid status should be rejected")
    return pass_result(
        "status_vocabulary",
        {"statuses": sorted(values), "status_aliases": schema_payload["status_aliases"]},
        started,
    )


def benchmark_schema_default_compact_runtime_fingerprint(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    compact = schema()
    full = schema(detail="full")
    ensure(compact["schema_detail"] == "compact", "schema should default to compact detail")
    ensure("modules" not in compact["runtime_fingerprint"], "compact schema should omit module list")
    ensure(
        compact["runtime_fingerprint"]["module_count"] == full["runtime_fingerprint"]["module_count"],
        "compact schema should retain module count",
    )
    ensure(full["schema_detail"] == "full", "full schema should be explicit")
    ensure(full["runtime_fingerprint"]["modules"], "full schema should expose deep module fingerprints")
    return pass_result(
        "schema_default_compact_runtime_fingerprint",
        {
            "compact_detail": compact["schema_detail"],
            "full_detail": full["schema_detail"],
            "module_count": compact["runtime_fingerprint"]["module_count"],
        },
        started,
    )


def benchmark_readiness_summary_gates_unproven_claims(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="codex-memory-fabric-readiness-") as tmp:
        base = Path(tmp)
        schema_path = base / "schema.json"
        frontier_path = base / "frontier.json"
        schema_path.write_text(json.dumps(schema()), encoding="utf-8")
        frontier_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "status": "frontier_attention",
                    "completion_claim_allowed": False,
                    "attention": ["live_freshness"],
                }
            ),
            encoding="utf-8",
        )
        result = readiness_summary(schema_json=str(schema_path), frontier_audit_json=str(frontier_path))
    ensure(not result["ok"], "readiness summary should block unproven frontier claims")
    ensure(
        "live_freshness" in result["recommended_next_checks"],
        "readiness summary should preserve frontier next checks",
    )
    ensure(result["layers"]["schema"]["ok"], "readiness summary should retain safe schema claim layer")
    return pass_result(
        "readiness_summary_gates_unproven_claims",
        {
            "status": result["status"],
            "unproven_count": len(result["unproven_or_blocked_claims"]),
            "next_checks": result["recommended_next_checks"],
        },
        started,
    )


def benchmark_runtime_fingerprint_detects_stale_imports(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    fresh = runtime_fingerprint()
    ensure(fresh["status"] == "runtime_imports_match_source", "fresh process should match source hashes")
    ensure(fresh["contract_version"] == "runtime_import_fingerprint.v2", "runtime contract should expose v2")
    ensure(
        fresh["process"].get("python_executable"),
        "runtime fingerprint should expose python executable for live process diagnosis",
    )
    ensure(
        fresh["modules"][0].get("import_path") and fresh["modules"][0].get("current_path"),
        "runtime fingerprint should expose import/current module paths",
    )
    imported = module_fingerprints()
    imported["memory_fabric_reasoning_brief.py"] = {
        **imported["memory_fabric_reasoning_brief.py"],
        "sha256": "stale-import-hash",
    }
    stale = runtime_fingerprint(import_fingerprints=imported)
    ensure(stale["status"] == "runtime_imports_stale", "fingerprint should detect stale import hashes")
    ensure(
        "memory_fabric_reasoning_brief.py" in stale["stale_modules"],
        "stale reasoning brief module should be named",
    )
    return pass_result(
        "runtime_fingerprint_detects_stale_imports",
        {
            "fresh_status": fresh["status"],
            "contract_version": fresh["contract_version"],
            "stale_status": stale["status"],
            "stale_modules": stale["stale_modules"],
        },
        started,
    )


def benchmark_reload_order_refreshes_schema_before_record_helpers(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    import memory_fabric_runtime_fingerprint

    order = reload_order(memory_fabric_runtime_fingerprint)
    ensure(
        order.index("memory_fabric_schema") < order.index("memory_fabric_records"),
        "schema should reload before direct-import record helpers",
    )
    return pass_result(
        "reload_order_refreshes_schema_before_record_helpers",
        {
            "schema_index": order.index("memory_fabric_schema"),
            "records_index": order.index("memory_fabric_records"),
        },
        started,
    )


def benchmark_confidence_vocabulary(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    expected = {"high", "medium", "low", "unknown"}
    values = set(schema()["confidences"])
    ensure(values == expected, "schema should expose the typed confidence vocabulary")
    low_policy = assess_promotion(tier="work", text="Open task.", confidence="low")
    ensure(low_policy["verify_before_use"], "low confidence should require verification")
    ensure(low_policy["confidence"] == "low", "promotion policy should normalize confidence")
    try:
        make_record(tier="work", title="Bad confidence", body="Nope.", confidence="hgh")
    except ValueError:
        rejected = True
    else:
        rejected = False
    ensure(rejected, "invalid confidence should be rejected")
    return pass_result("confidence_vocabulary", {"confidences": sorted(values)}, started)


def benchmark_provenance_vocabulary(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    provenance = schema()["provenance_types"]
    expected_groups = {"strong", "context_only", "observation"}
    ensure(set(provenance) == expected_groups, "schema should expose provenance type groups")
    policy = assess_promotion(
        tier="knowledge",
        text="Source-backed run produced a receipt.",
        provenance_type="source_backed_agent_run",
        evidence_path="/tmp/receipt.json",
        confidence="high",
    )
    ensure(policy["can_promote"], "source-backed agent runs should count as strong provenance")
    try:
        make_record(tier="work", title="Bad provenance", body="Nope.", provenance_type="verified_comand")
    except ValueError:
        rejected = True
    else:
        rejected = False
    ensure(rejected, "invalid provenance should be rejected")
    return pass_result(
        "provenance_vocabulary",
        {
            "groups": sorted(provenance),
            "strong_count": len(provenance["strong"]),
            "context_only_count": len(provenance["context_only"]),
        },
        started,
    )


def benchmark_recency_tie_break(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    older = make_record(
        tier="work",
        title="Benchmark equal relevance active task",
        body="Check cache status for the memory fabric.",
        scope="/benchmark/tie",
        tags="benchmark,cache",
    )
    newer = make_record(
        tier="work",
        title="Benchmark equal relevance active task",
        body="Check cache status for the memory fabric.",
        scope="/benchmark/tie",
        tags="benchmark,cache",
    )
    older["created_at"] = "2026-06-08T01:00:00+00:00"
    newer["created_at"] = "2026-06-08T02:00:00+00:00"
    append_record(older, store)
    append_record(newer, store)
    result = search_records(query="cache memory fabric", tier="work", scope="/benchmark/tie", path=store)
    ensure(result["records"][0]["id"] == newer["id"], "newer equal-score work memory should rank first")
    return pass_result("recency_tie_break", {"top_record_id": newer["id"]}, started)


def benchmark_write_policy_matrix(store: Path) -> dict[str, Any]:
    del store
    started = time.perf_counter()
    cases = [
        (
            "knowledge_source_backed",
            {
                "tier": "knowledge",
                "text": "Source-backed durable fact.",
                "provenance_type": "source_file",
                "evidence_path": "/tmp/source.md",
            },
            True,
            False,
        ),
        (
            "knowledge_screen_only",
            {"tier": "knowledge", "text": "OpenChronicle saw a browser setting.", "provenance_type": "openchronicle"},
            False,
            True,
        ),
        (
            "learning_complete",
            {
                "tier": "learning",
                "text": "Symptom: stale cache. Fix: sync cache. Proof: doctor passed.",
                "provenance_type": "verified_command",
            },
            True,
            False,
        ),
        (
            "learning_missing_markers",
            {"tier": "learning", "text": "Cache got better after some work.", "provenance_type": "verified_command"},
            False,
            True,
        ),
        (
            "work_context_allowed",
            {"tier": "work", "text": "Open task seen from screen context.", "provenance_type": "openchronicle"},
            True,
            False,
        ),
    ]
    outcomes = []
    for name, payload, expected_promote, expected_verify in cases:
        result = assess_promotion(**payload)
        ensure(result["can_promote"] is expected_promote, f"{name} promotion mismatch")
        ensure(result["verify_before_use"] is expected_verify, f"{name} verify-before-use mismatch")
        outcomes.append(
            {
                "name": name,
                "can_promote": result["can_promote"],
                "recommended_status": result["recommended_status"],
                "verify_before_use": result["verify_before_use"],
            }
        )
    return pass_result("write_policy_matrix", {"case_count": len(outcomes), "outcomes": outcomes}, started)


def benchmark_proof_boundary(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    policy = assess_promotion(
        tier="knowledge",
        text="OpenChronicle saw a browser setting.",
        provenance_type="openchronicle",
    )
    ensure(not policy["can_promote"], "screen-only knowledge should not promote")
    ensure(policy["recommended_status"] == "candidate", "screen-only knowledge should be candidate")
    event = record_from_hook_event(
        {
            "tier": "knowledge",
            "title": "Benchmark screen-only observation",
            "body": "OpenChronicle saw a browser setting.",
            "scope": "/benchmark/repo",
            "source": "openchronicle",
        },
        store,
    )
    ensure(event["record"]["status"] == "candidate", "hook event should record candidate status")
    return pass_result(
        "proof_boundary",
        {"required_evidence_count": len(policy["required_evidence"])},
        started,
    )


def benchmark_hook_status_policy(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    lifecycle = record_from_hook_event(
        {
            "tier": "work",
            "title": "Benchmark superseded task",
            "body": "Superseded by newer active memory.",
            "scope": "/benchmark/hooks",
            "source": "verified_command",
            "status": "superseded",
        },
        store,
    )
    weak_upgrade = record_from_hook_event(
        {
            "tier": "knowledge",
            "title": "Benchmark weak active request",
            "body": "OpenChronicle saw a browser setting.",
            "scope": "/benchmark/hooks",
            "source": "openchronicle",
            "status": "active",
        },
        store,
    )
    ensure(lifecycle["record"]["status"] == "superseded", "hook should preserve lifecycle status")
    ensure(not lifecycle["status_policy"]["upgrade_blocked"], "lifecycle status should not be an upgrade")
    ensure(weak_upgrade["record"]["status"] == "candidate", "weak evidence should stay candidate")
    ensure(weak_upgrade["status_policy"]["upgrade_blocked"], "weak active request should be blocked")
    return pass_result(
        "hook_status_policy",
        {
            "lifecycle_status": lifecycle["record"]["status"],
            "weak_evidence_status": weak_upgrade["record"]["status"],
        },
        started,
    )


def benchmark_hook_health(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    proof = store.parent / "hook-health-proof.json"
    proof.write_text(json.dumps({"ok": True}), encoding="utf-8")
    record = make_record(
        tier="work",
        title="Benchmark hook health",
        body="Hook automation should verify local memory health before trusting projections.",
        scope="/benchmark/hook-health",
        provenance_type="source_file",
        evidence_path=str(proof),
        confidence="high",
    )
    append_record(record, store)
    projection = store.parent / "hook-health-projection.json"
    project(scope="/benchmark/hook-health", output=str(projection), path=store)
    result = hook_health(
        path=store,
        projection_input=str(projection),
        evidence_scope="/benchmark/hook-health",
        strict_evidence=True,
    )
    ensure(result["ok"], "hook health should pass clean scoped evidence and projection")
    ensure(result["status"] == "hook_ready", "hook health should report ready")
    return pass_result(
        "hook_health",
        {
            "status": result["status"],
            "checks": result["checks"],
            "evidence_warning_count": result["evidence"]["warning_count"],
        },
        started,
    )


def benchmark_budget_plan_preserves_capability_boundary(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    plugin_eval = store.parent / "plugin-eval-budget-pressure.json"
    plugin_eval.write_text(
        json.dumps(
            {
                "budgets": {
                    "deferred_cost_tokens": {
                        "value": 53010,
                        "components": [
                            {"label": "scripts/memory_fabric_runtime.py", "tokens": 18000},
                            {"label": "fixtures/long_report.md", "tokens": 3200},
                            {"label": "README.md", "tokens": 1900},
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = budget_plan(
        plugin_eval_json=str(plugin_eval),
        top_n=2,
        max_deferred_tokens=50000,
    )

    ensure(result["status"] == "deferred_budget_attention", "budget plan should flag over-target deferred cost")
    ensure(result["deferred_overage_tokens"] == 3010, "budget overage should be explicit")
    ensure(
        result["top_components"][0]["label"] == "scripts/memory_fabric_runtime.py",
        "largest component should rank first",
    )
    ensure(
        any("Do not move active runtime code" in item for item in result["recommendations"]),
        "budget plan should preserve runtime capability boundary",
    )
    ensure(
        "static package-size gauge" in result["claim_boundary"],
        "claim boundary should separate static budget from observed cost",
    )
    ensure(
        result["usage_evidence"]["status"] == "observed_usage_missing",
        "budget plan should not invent observed usage",
    )
    return pass_result(
        "budget_plan_preserves_capability_boundary",
        {
            "status": result["status"],
            "overage": result["deferred_overage_tokens"],
            "largest_component": result["top_components"][0]["label"],
        },
        started,
    )


def benchmark_budget_plan_uses_representative_usage_receipt(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    plugin_eval = store.parent / "plugin-eval-budget-usage.json"
    usage_report = store.parent / "usage-report-budget-usage.json"
    plugin_eval.write_text(
        json.dumps(
            {
                "budgets": {
                    "deferred_cost_tokens": {
                        "value": 53010,
                        "components": [{"label": "skills/codex-memory-fabric/SKILL.md", "tokens": 53010}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    usage_report.write_text(
        json.dumps(
            {
                "sample_count": 6,
                "usage_quality": {"representative": True, "scenario_count": 3},
                "token_totals": {"total_tokens": 24000},
                "token_averages": {"total_tokens": 4000},
            }
        ),
        encoding="utf-8",
    )

    result = budget_plan(
        plugin_eval_json=str(plugin_eval),
        top_n=1,
        max_deferred_tokens=50000,
        usage_report_json=str(usage_report),
    )

    ensure(result["status"] == "deferred_budget_attention", "static budget warning should remain")
    ensure(
        result["usage_evidence"]["status"] == "observed_usage_representative",
        "representative usage receipt should be accepted",
    )
    ensure(
        result["usage_evidence"]["observed_invocation_cost_available"],
        "representative usage should enable observed invocation-cost discussion",
    )
    return pass_result(
        "budget_plan_uses_representative_usage_receipt",
        {
            "status": result["status"],
            "usage_status": result["usage_evidence"]["status"],
            "sample_count": result["usage_evidence"]["sample_count"],
        },
        started,
    )


def benchmark_frontier_audit_blocks_unproven_completion(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-frontier-audit"
    root.mkdir(parents=True, exist_ok=True)
    source_schema = schema()
    source_schema["runtime_fingerprint"] = {
        "ok": False,
        "status": "runtime_imports_stale",
        "stale_module_count": 3,
    }
    receipts = {
        "release_report_json": {
            "ok": False,
            "local_ok": True,
            "gauge_ok": True,
            "status": "release_local_ready_live_stale",
            "current_live": {"ok": False, "tool_exposure_checked": True},
            "current_live_behavior": {"ok": False},
        },
        "budget_plan_json": {
            "ok": False,
            "status": "deferred_budget_attention",
            "deferred_cost_tokens": 100773,
            "deferred_overage_tokens": 50773,
            "usage_evidence": {"status": "observed_usage_missing"},
        },
        "schema_json": source_schema,
        "benchmark_json": {
            "ok": True,
            "passed": 73,
            "failed": 0,
            "scenario_count": 73,
            "details": {"reasoning": {"causal_memory_attribution_case_count": 1}},
        },
        "plugin_eval_json": {"summary": {"score": 86, "grade": "B"}},
    }
    paths = {}
    for name, payload in receipts.items():
        path = root / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = str(path)

    result = frontier_audit(**paths)

    ensure(not result["ok"], "frontier audit should block completion when live is stale and budget is over target")
    ensure("live_freshness" in result["attention"], "live stale gate should be explicit")
    ensure("deferred_budget" in result["attention"], "deferred budget gate should be explicit")
    ensure(
        result["gates"]["reasoning_eval_proof"]["ok"],
        "reasoning eval proof should stay independently ready",
    )
    ensure(
        result["runtime_contract"]["behavior_contract_version"] == "frontier_audit.v3",
        "frontier audit contract should be versioned",
    )
    return pass_result(
        "frontier_audit_blocks_unproven_completion",
        {
            "status": result["status"],
            "attention": result["attention"],
            "completion_claim_allowed": result["completion_claim_allowed"],
        },
        started,
    )


def benchmark_frontier_audit_accepts_representative_usage_budget_resolution(store: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = store.parent / f"{store.stem}-frontier-audit-usage-budget"
    root.mkdir(parents=True, exist_ok=True)
    source_schema = schema()
    source_schema["runtime_fingerprint"] = {
        "ok": True,
        "status": "runtime_imports_match_source",
        "stale_module_count": 0,
    }
    receipts = {
        "release_report_json": {
            "ok": True,
            "local_ok": True,
            "gauge_ok": True,
            "status": "release_ready",
            "current_live": {"ok": True, "tool_exposure_checked": True},
            "current_live_behavior": {"ok": True, "checked": True},
        },
        "budget_plan_json": {
            "ok": False,
            "status": "deferred_budget_attention",
            "deferred_cost_tokens": 102418,
            "deferred_overage_tokens": 52418,
            "usage_evidence": {
                "status": "observed_usage_representative",
                "observed_invocation_cost_available": True,
                "sample_count": 6,
                "scenario_count": 3,
                "token_averages": {"total": 2100},
            },
        },
        "schema_json": source_schema,
        "benchmark_json": {
            "ok": True,
            "passed": 74,
            "failed": 0,
            "scenario_count": 74,
            "details": {"reasoning": {"causal_memory_attribution_case_count": 1}},
        },
        "plugin_eval_json": {"summary": {"score": 86, "grade": "B"}},
    }
    paths = {}
    for name, payload in receipts.items():
        path = root / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = str(path)

    result = frontier_audit(**paths)
    gate = result["gates"]["deferred_budget"]

    ensure(result["ok"], "representative observed usage should resolve the frontier runtime budget gate")
    ensure(result["attention"] == [], "observed usage budget resolution should remove frontier attention")
    ensure(
        gate["status"] == "deferred_budget_observed_usage_ready",
        "budget gate should name observed usage readiness",
    )
    ensure(not gate["details"]["static_budget_ready"], "static overage should remain explicit")
    ensure(gate["details"]["observed_usage_budget_ready"], "observed usage should be explicit")
    ensure(
        gate["details"]["deferred_overage_tokens"] == 52418,
        "static overage should not be hidden",
    )
    return pass_result(
        "frontier_audit_accepts_representative_usage_budget_resolution",
        {
            "status": result["status"],
            "budget_gate_status": gate["status"],
            "deferred_overage_tokens": gate["details"]["deferred_overage_tokens"],
            "completion_claim_allowed": result["completion_claim_allowed"],
        },
        started,
    )


BENCHMARK_SCENARIOS: list[Benchmark] = [
    benchmark_learning_retrieval,
    benchmark_multi_tier_retrieval,
    benchmark_projection_compaction,
    benchmark_projection_status_boundary,
    benchmark_thread_brief_tri_layer_handoff,
    benchmark_thread_brief_readiness_gates,
    benchmark_thread_brief_task_profile_object_identification,
    benchmark_thread_brief_object_identification_pricing_gate,
    benchmark_reasoning_brief_answer_contract_blocks_object_pricing_gate,
    benchmark_answer_eval_memory_improves_answer,
    benchmark_answer_eval_suite_multi_case_grounding,
    benchmark_answer_eval_suite_failed_case_categories,
    benchmark_memory_graph_typed_edges,
    benchmark_memory_graph_frontier_reasoning_markers,
    benchmark_memory_graph_decision_context,
    benchmark_memory_graph_path_explanations,
    benchmark_causal_audit_verification_gate,
    benchmark_claim_support_audit_claim_ledger,
    benchmark_claim_support_causal_evidence_trace,
    benchmark_causal_hypotheses_disambiguation_gate,
    benchmark_reasoning_brief_answer_readiness_gate,
    benchmark_reasoning_brief_decision_context_trace,
    benchmark_reasoning_brief_causal_evidence_trace,
    benchmark_reasoning_brief_answer_use_policy_blocks_conflicts,
    benchmark_reasoning_brief_answer_use_policy_allows_descriptive_noncausal_claims,
    benchmark_reasoning_eval_requires_ready_brief_and_evidence,
    benchmark_reasoning_eval_rejects_context_only_proof_blur,
    benchmark_reasoning_eval_rejects_answer_contract_blocked_pricing_action,
    benchmark_reasoning_eval_requires_ready_causal_hypotheses_for_causal_answer,
    benchmark_reasoning_eval_suite_mixed_case_gate,
    benchmark_reasoning_eval_suite_causal_memory_lift,
    benchmark_reasoning_eval_suite_conflict_category_gate,
    benchmark_memory_graph_audit_warnings,
    benchmark_memory_graph_audit_conflict_hygiene,
    benchmark_graph_audit_scoped_supersession_outside_selection,
    benchmark_memory_graph_ranked_window,
    benchmark_memory_graph_audit_expansion_plan,
    benchmark_store_audit_health,
    benchmark_evidence_audit_health,
    benchmark_evidence_repair_lifecycle,
    benchmark_status_filtered_retrieval,
    benchmark_provenance_filtered_retrieval,
    benchmark_semantic_provenance_gated_retrieval,
    benchmark_semantic_retrieval_gate_warns_on_context_only,
    benchmark_confidence_filtered_retrieval,
    benchmark_legacy_numeric_confidence_read_normalization,
    benchmark_live_surface_schema_contract,
    benchmark_truncated_live_surface_is_unproven_not_missing,
    benchmark_telemetry_status_ready_gate,
    benchmark_telemetry_audit_diagnostics,
    benchmark_release_report_local_ready_live_stale,
    benchmark_release_report_host_advertisement_stale_stdio_complete,
    benchmark_release_report_live_tool_schema_attention,
    benchmark_release_report_mixed_live_freshness_attention,
    benchmark_release_report_truncated_live_surface_attention,
    benchmark_schema_behavior_receipt_mixed_freshness,
    benchmark_release_report_inline_live_ready,
    benchmark_release_report_hook_health_receipt,
    benchmark_release_report_live_behavior_attention,
    benchmark_release_report_requires_behavior_receipt,
    benchmark_behavior_case_causal_evidence_ledger,
    benchmark_status_vocabulary,
    benchmark_schema_default_compact_runtime_fingerprint,
    benchmark_readiness_summary_gates_unproven_claims,
    benchmark_runtime_fingerprint_detects_stale_imports,
    benchmark_reload_order_refreshes_schema_before_record_helpers,
    benchmark_confidence_vocabulary,
    benchmark_provenance_vocabulary,
    benchmark_recency_tie_break,
    benchmark_write_policy_matrix,
    benchmark_proof_boundary,
    benchmark_hook_status_policy,
    benchmark_hook_health,
    benchmark_budget_plan_preserves_capability_boundary,
    benchmark_budget_plan_uses_representative_usage_receipt,
    benchmark_frontier_audit_blocks_unproven_completion,
    benchmark_frontier_audit_accepts_representative_usage_budget_resolution,
]


def run_benchmark(store: Path) -> dict[str, Any]:
    results = []
    for scenario in BENCHMARK_SCENARIOS:
        started = time.perf_counter()
        try:
            results.append(scenario(store))
        except Exception as exc:  # pragma: no cover - result payload is the test output.
            results.append(fail_result(scenario.__name__, str(exc), started))
    records = load_records(store)
    passed = sum(1 for result in results if result["ok"])
    return {
        "ok": passed == len(results),
        "scenario_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "store": str(store),
        "records_written": len(records),
        "results": results,
        "policy": {
            "state_yaml_role": "compact projection only",
            "source_of_truth": "append-only JSONL memory fabric store",
            "context_only_sources": ["openchronicle", "live_ui", "screen_observation", "cache_state"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default="", help="Optional benchmark store path.")
    parser.add_argument("--output", default="", help="Optional JSON receipt path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="codex-memory-fabric-bench-") as tmp:
        store = Path(args.store).expanduser().resolve() if args.store else Path(tmp) / "memory.jsonl"
        result = run_benchmark(store)
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
