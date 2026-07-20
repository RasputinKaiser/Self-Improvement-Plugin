from __future__ import annotations
import hashlib
import os
import sys
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "runtime_import_fingerprint.v2"
CLAIM_BOUNDARY = (
    "Runtime fingerprints identify the process and imported module files used to produce this receipt; "
    "they do not prove behavior correctness or identify which duplicate MCP process the host is using."
)
WATCHED_MODULES = [
    "memory_fabric_mcp.py",
    "memory_fabric_mcp_runtime.py",
    "memory_fabric_mcp_reload_order.py",
    "memory_fabric_runtime_fingerprint.py",
    "memory_fabric_schema.py",
    "memory_fabric_schema_behavior.py",
    "memory_fabric_reasoning_brief.py",
    "memory_fabric_reasoning_brief_checks.py",
    "memory_fabric_reasoning_brief_causal_checks.py",
    "memory_fabric_reasoning_brief_summaries.py",
    "memory_fabric_answer_contract.py",
    "memory_fabric_answer_contract_actions.py",
    "memory_fabric_answer_contract_citations.py",
    "memory_fabric_answer_contract_claims.py",
    "memory_fabric_answer_contract_compliance.py",
    "memory_fabric_answer_contract_task_gate.py",
    "memory_fabric_answer_contract_uncertainty.py",
    "memory_fabric_answer_use_policy.py",
    "memory_fabric_answer_use_policy_reasons.py",
    "memory_fabric_answer_use_policy_records.py",
    "memory_fabric_answer_eval.py",
    "memory_fabric_answer_eval_suite_checks.py",
    "memory_fabric_answer_eval_suite_ids.py",
    "memory_fabric_decision_context.py",
    "memory_fabric_evidence_audit.py",
    "memory_fabric_evidence_supersession.py",
    "memory_fabric_causal_evidence.py",
    "memory_fabric_task_cue_ledger.py",
    "memory_fabric_task_cue_match.py",
    "memory_fabric_task_cue_pricing.py",
    "memory_fabric_reasoning_attribution.py",
    "memory_fabric_reasoning_eval.py",
    "memory_fabric_reasoning_eval_checks.py",
    "memory_fabric_reasoning_eval_evidence.py",
    "memory_fabric_reasoning_eval_summary.py",
    "memory_fabric_reasoning_eval_suite.py",
    "memory_fabric_reasoning_eval_suite_case.py",
    "memory_fabric_reasoning_eval_suite_category_checks.py",
    "memory_fabric_reasoning_eval_suite_categories.py",
    "memory_fabric_reasoning_eval_suite_ids.py",
    "memory_fabric_reasoning_eval_suite_summary.py",
    "memory_fabric_proof_boundary.py",
    "memory_fabric_causal_answer_policy.py",
    "memory_fabric_conflict_refs.py",
    "memory_fabric_conflict_strength.py",
    "memory_fabric_contradiction_audit.py",
    "memory_fabric_brief_readiness.py",
    "memory_fabric_claim_support.py",
    "memory_fabric_claim_support_item.py",
    "memory_fabric_claim_support_text.py",
    "memory_fabric_graph.py",
    "memory_fabric_graph_audit.py",
    "memory_fabric_graph_explicit.py",
    "memory_fabric_path_use.py",
    "memory_fabric_graph_edges.py",
    "memory_fabric_process_audit.py",
    "memory_fabric_release_host_advertisement.py",
    "memory_fabric_release_process_attention.py",
    "memory_fabric_release_report.py",
    "memory_fabric_readiness_summary.py",
]
SCRIPT_DIR = Path(__file__).resolve().parent


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_fingerprints() -> dict[str, dict[str, Any]]:
    return {
        module: file_fingerprint(SCRIPT_DIR / module)
        for module in WATCHED_MODULES
    }


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "mtime_ns": stat.st_mtime_ns,
        "size_bytes": stat.st_size,
    }


IMPORT_TIME_FINGERPRINTS = module_fingerprints()


def refresh_import_time_fingerprints() -> dict[str, dict[str, Any]]:
    global IMPORT_TIME_FINGERPRINTS
    IMPORT_TIME_FINGERPRINTS = module_fingerprints()
    return IMPORT_TIME_FINGERPRINTS


def runtime_fingerprint(import_fingerprints: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    import_hashes = import_fingerprints or IMPORT_TIME_FINGERPRINTS
    current_hashes = module_fingerprints()
    modules = [module_status(module, import_hashes, current_hashes) for module in WATCHED_MODULES]
    stale = [item for item in modules if item["status"] != "import_matches_source"]
    return {
        "ok": not stale,
        "status": "runtime_imports_match_source" if not stale else "runtime_imports_stale",
        "contract_version": CONTRACT_VERSION,
        "process_id": os.getpid(),
        "process": process_context(),
        "module_root": str(SCRIPT_DIR),
        "module_count": len(modules),
        "stale_module_count": len(stale),
        "stale_modules": [item["module"] for item in stale],
        "modules": modules,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def module_status(
    module: str,
    import_hashes: dict[str, dict[str, Any]],
    current_hashes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    imported = import_hashes.get(module, {})
    current = current_hashes.get(module, {})
    imported_sha = imported.get("sha256", "")
    current_sha = current.get("sha256", "")
    import_path = imported.get("path", "")
    current_path = current.get("path", "")
    matches = imported_sha == current_sha and import_path == current_path
    return {
        "module": module,
        "path": current_path or import_path,
        "import_path": import_path,
        "current_path": current_path,
        "import_sha256": imported_sha,
        "current_sha256": current_sha,
        "import_mtime_ns": imported.get("mtime_ns", ""),
        "current_mtime_ns": current.get("mtime_ns", ""),
        "import_size_bytes": imported.get("size_bytes", ""),
        "current_size_bytes": current.get("size_bytes", ""),
        "path_matches_source": import_path == current_path,
        "sha256_matches_source": imported_sha == current_sha,
        "status": "import_matches_source" if matches else "import_stale_vs_source",
    }


def process_context() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "script_dir": str(SCRIPT_DIR),
    }
