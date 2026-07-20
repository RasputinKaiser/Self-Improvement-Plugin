from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_causal_audit import causal_audit


CLAIM_BOUNDARY = (
    "Behavior cases prepare deterministic source-side fixtures and comparison specs; "
    "current-live proof still requires executing the live MCP tool and comparing the response."
)
CAUSAL_EVIDENCE_CASE = "causal-evidence-ledger"
CAUSAL_SOURCE_ID = "mem_1111111111111111"
CAUSAL_TARGET_ID = "mem_2222222222222222"
CAUSAL_SCOPE = "/tmp/memory-fabric-live-causal-evidence"
CAUSAL_QUERY = "causal"
CAUSAL_REQUIRED_FIELDS = [
    "ok",
    "status",
    "causal_path_count",
    "needs_verification_count",
    "missing_evidence_node_count",
    "required_citation_paths",
    "causal_paths.0.evidence_ledger",
    "causal_paths.0.required_citation_paths",
    "causal_paths.0.missing_evidence_nodes",
]


def behavior_case(
    case: str = CAUSAL_EVIDENCE_CASE,
    output_dir: str = "",
    output: str = "",
) -> dict[str, Any]:
    if case != CAUSAL_EVIDENCE_CASE:
        raise ValueError(f"unknown behavior case: {case}")
    root = case_root(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    spec = causal_evidence_case(root)
    if output:
        Path(output).expanduser().write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return spec


def case_root(output_dir: str) -> Path:
    return Path(output_dir).expanduser() if output_dir else Path.cwd() / ".memory-fabric-behavior-case"


def causal_evidence_case(root: Path) -> dict[str, Any]:
    proof_path = root / "target-proof.json"
    store_path = root / "memory.jsonl"
    source_output_path = root / "source-causal-audit.json"
    proof_path.write_text('{"receipt":"source-backed causal target proof"}\n', encoding="utf-8")
    store_path.write_text(causal_fixture_jsonl(proof_path), encoding="utf-8")
    source = causal_audit(
        scope=CAUSAL_SCOPE,
        query=CAUSAL_QUERY,
        max_nodes=12,
        max_edges=24,
        path=store_path,
    )
    source_output_path.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "case": CAUSAL_EVIDENCE_CASE,
        "behavior": "memory_fabric_causal_audit_causal_evidence_ledger",
        "claim_boundary": CLAIM_BOUNDARY,
        "fixture": {
            "store": str(store_path),
            "proof_path": str(proof_path),
            "scope": CAUSAL_SCOPE,
            "query": CAUSAL_QUERY,
            "source_node": CAUSAL_SOURCE_ID,
            "target_node": CAUSAL_TARGET_ID,
        },
        "source_output_json": str(source_output_path),
        "required_fields": CAUSAL_REQUIRED_FIELDS,
        "source_fields": CAUSAL_REQUIRED_FIELDS,
        "live_tool": "memory_fabric_causal_audit",
        "live_tool_args": {
            "store": str(store_path),
            "scope": CAUSAL_SCOPE,
            "query": CAUSAL_QUERY,
            "max_nodes": 12,
            "max_edges": 24,
        },
        "behavior_receipt_args": behavior_receipt_args(source_output_path),
        "source_summary": {
            "status": source["status"],
            "causal_path_count": source["causal_path_count"],
            "missing_evidence_node_count": source["missing_evidence_node_count"],
            "required_citation_paths": source["required_citation_paths"],
            "evidence_contract_version": source.get("evidence_contract_version", ""),
        },
    }


def causal_fixture_jsonl(proof_path: Path) -> str:
    records = [
        {
            "id": CAUSAL_SOURCE_ID,
            "tier": "work",
            "title": "Live causal weak source",
            "body": f"Caused by: {CAUSAL_TARGET_ID}",
            "scope": CAUSAL_SCOPE,
            "tags": ["causal", "live", "weak"],
            "provenance": {
                "type": "screen_observation",
                "detail": "live fixture context-only source",
                "evidence_path": "",
            },
            "confidence": "medium",
            "status": "active",
            "created_at": "2026-06-09T09:05:00Z",
            "verify_before_use": True,
        },
        {
            "id": CAUSAL_TARGET_ID,
            "tier": "knowledge",
            "title": "Live causal sourced target",
            "body": "Verified source-backed causal target.",
            "scope": CAUSAL_SCOPE,
            "tags": ["causal", "live", "weak"],
            "provenance": {
                "type": "source_file",
                "detail": "live fixture source-backed target",
                "evidence_path": str(proof_path),
            },
            "confidence": "high",
            "status": "active",
            "created_at": "2026-06-09T09:05:01Z",
            "verify_before_use": False,
        },
    ]
    return "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n"


def behavior_receipt_args(source_output_path: Path) -> dict[str, str]:
    fields = ",".join(CAUSAL_REQUIRED_FIELDS)
    return {
        "behavior": "memory_fabric_causal_audit_causal_evidence_ledger",
        "required_fields": fields,
        "source_json": str(source_output_path),
        "source_fields": fields,
    }
