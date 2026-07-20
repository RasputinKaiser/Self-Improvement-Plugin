from __future__ import annotations
import json
import importlib
from pathlib import Path
from typing import Any

from memory_fabric_runtime_fingerprint import runtime_fingerprint


TIERS = {"work", "knowledge", "learning"}
STATUSES = {"active", "candidate", "superseded", "archived"}
STATUS_ALIASES = {"current": "active"}
CONFIDENCES = {"high", "medium", "low", "unknown"}
CONTEXT_ONLY_PROVENANCE = {"live_ui", "openchronicle", "screen_observation", "cache_state"}
STRONG_PROVENANCE = {
    "repo_receipt",
    "source_backed_agent_run",
    "source_document",
    "source_file",
    "source_url",
    "user_instruction",
    "verified_command",
}
OBSERVATION_PROVENANCE = {"hook_event", "user_or_agent_observation"}
PROVENANCE_TYPES = CONTEXT_ONLY_PROVENANCE | STRONG_PROVENANCE | OBSERVATION_PROVENANCE
RUNTIME_CONTRACT_VERSION = "runtime_contract.v1"
MEMORY_RECORD_SCHEMA_VERSION = "1.0"


def record_schema_version() -> str:
    return MEMORY_RECORD_SCHEMA_VERSION


def normalize_tier(tier: str) -> str:
    tier = (tier or "").strip().lower()
    aliases = {
        "task": "work",
        "project": "work",
        "decision": "work",
        "domain": "knowledge",
        "research": "knowledge",
        "fact": "knowledge",
        "lesson": "learning",
        "fix": "learning",
        "pattern": "learning",
    }
    tier = aliases.get(tier, tier)
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {sorted(TIERS)}")
    return tier


def normalize_status(status: str) -> str:
    status = (status or "active").strip().lower() or "active"
    status = STATUS_ALIASES.get(status, status)
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}; aliases: {STATUS_ALIASES}")
    return status


def normalize_confidence(confidence: str) -> str:
    confidence = (confidence or "medium").strip().lower() or "medium"
    if confidence not in CONFIDENCES:
        raise ValueError(f"confidence must be one of {sorted(CONFIDENCES)}")
    return confidence


def normalize_provenance_type(provenance_type: str) -> str:
    provenance_type = (provenance_type or "user_or_agent_observation").strip().lower()
    if provenance_type not in PROVENANCE_TYPES:
        raise ValueError(f"provenance_type must be one of {sorted(PROVENANCE_TYPES)}")
    return provenance_type


def plugin_version() -> str:
    return json.loads((Path(__file__).parents[1] / ".codex-plugin/plugin.json").read_text())["version"]


def schema_data_path() -> Path:
    return Path(__file__).with_name("memory_fabric_schema_data.json")


def schema_data() -> dict[str, Any]:
    return json.loads(schema_data_path().read_text(encoding="utf-8"))


def runtime_contract(component: str, **fields: Any) -> dict[str, Any]:
    return {
        "contract_version": RUNTIME_CONTRACT_VERSION,
        "component": component,
        **fields,
    }


def mcp_runtime_reload_receipt() -> dict[str, Any]:
    try:
        runtime = importlib.import_module("memory_fabric_mcp_runtime")
        return runtime.last_reload_receipt()
    except Exception as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "contract_version": "mcp_runtime_reload.v2",
            "error": type(exc).__name__,
            "claim_boundary": "Schema could not read the MCP runtime reload receipt.",
        }


def normalize_schema_detail(detail: str) -> str:
    detail = (detail or "compact").strip().lower() or "compact"
    aliases = {"deep": "full", "verbose": "full"}
    detail = aliases.get(detail, detail)
    if detail not in {"compact", "full"}:
        raise ValueError("detail must be one of ['compact', 'full']; aliases: deep=full, verbose=full")
    return detail


def compact_runtime_fingerprint(fingerprint: dict[str, Any]) -> dict[str, Any]:
    process = fingerprint.get("process", {})
    return {
        "ok": fingerprint.get("ok"),
        "status": fingerprint.get("status", ""),
        "contract_version": fingerprint.get("contract_version", ""),
        "detail": "compact",
        "process_id": fingerprint.get("process_id"),
        "process": {
            "python_executable": process.get("python_executable", ""),
            "python_version": process.get("python_version", ""),
            "script_dir": process.get("script_dir", ""),
        },
        "module_root": fingerprint.get("module_root", ""),
        "module_count": fingerprint.get("module_count", 0),
        "stale_module_count": fingerprint.get("stale_module_count", 0),
        "stale_modules": fingerprint.get("stale_modules", []),
        "claim_boundary": fingerprint.get("claim_boundary", ""),
    }


def schema(detail: str = "compact") -> dict[str, Any]:
    detail = normalize_schema_detail(detail)
    data = schema_data()
    fingerprint = runtime_fingerprint()
    return {
        **data,
        "plugin_version": plugin_version(),
        "schema_detail": detail,
        "schema_modes": {
            "default": "compact",
            "available": ["compact", "full"],
            "deep_runtime_fingerprint": "Use schema(detail='full') or the runtime-fingerprint command/tool.",
        },
        "status_aliases": STATUS_ALIASES,
        "runtime_contract": runtime_contract(
            "schema",
            detects_runtime_import_staleness=True,
            mcp_runtime_autoreloads_stale_imports=True,
            mcp_runtime_dispatches_fresh_callables=True,
            mcp_runtime_dispatch_loads_runtime_module_each_call=True,
            mcp_runtime_exposes_last_reload_receipt=True,
            mcp_runtime_reload_contract_version="mcp_runtime_reload.v2",
            exposes_runtime_process_context=True,
            exposes_module_import_and_current_paths=True,
            runtime_fingerprint_contract_version="runtime_import_fingerprint.v2",
        ),
        "runtime_reload": mcp_runtime_reload_receipt(),
        "runtime_fingerprint": (
            fingerprint if detail == "full" else compact_runtime_fingerprint(fingerprint)
        ),
        "tool_contracts": data["tool_contracts"],
        "proof_boundary": "Label proof source: OpenChronicle/UI/source/cache/live.",
        "projection_rule": "Repo files are projections, not source of truth.",
    }
