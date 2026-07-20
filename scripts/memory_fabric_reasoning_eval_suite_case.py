from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_reasoning_eval import reasoning_eval


def case_result(
    index: int,
    case: dict[str, Any],
    *,
    defaults: dict[str, Any],
    path: str | Path | None,
) -> dict[str, Any]:
    case_id = str(case.get("id") or f"case_{index + 1}")
    result = reasoning_eval(path=path, **case_kwargs(case, defaults))
    evidence = result["reasoning_evidence"]
    compliance = result.get("answer_contract_compliance", {})
    attribution = result.get("memory_attribution", {})
    reasoning_brief = result.get("reasoning_brief", {})
    return {
        "case_id": case_id,
        "ok": result["ok"],
        "status": result["status"],
        "reasoning_status": result["reasoning_status"],
        "answer_eval_status": result["answer_eval_status"],
        "proof_boundary_status": result["proof_boundary_status"]["status"],
        "causal_answer_status": result["causal_answer_policy"]["status"],
        "memory_attribution_status": attribution.get("status", ""),
        "memory_attribution_kind": attribution.get("attribution_kind", ""),
        "memory_attribution_ok": bool(attribution.get("ok", False)),
        "answer_contract_status": compliance.get("status", ""),
        "answer_contract_blocked_action_count": len(compliance.get("blocked_action_violations", [])),
        "active_superseded_count": int(reasoning_brief.get("active_superseded_count", 0)),
        "active_contradiction_count": int(reasoning_brief.get("active_contradiction_count", 0)),
        "causal_evidence_status": str(reasoning_brief.get("causal_evidence_status", "")),
        "causal_evidence_path_count": int(reasoning_brief.get("causal_evidence_path_count", 0)),
        "causal_evidence_missing_node_count": int(reasoning_brief.get("causal_evidence_missing_node_count", 0)),
        "causal_evidence_required_citation_count": int(
            reasoning_brief.get("causal_evidence_required_citation_count", 0)
        ),
        "ready_for_answer": result["ready_for_answer"],
        "score_delta": result["improvement"]["score_delta"],
        "cited_evidence_count": evidence["cited_evidence_count"],
        "missing_evidence_count": len(evidence["missing_evidence_paths"]),
        "recommended_next_checks": result["recommended_next_checks"],
    }


def case_kwargs(case: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    values = {key: case.get(key, defaults[key]) for key in defaults}
    values["claims_json"] = case_claims_json(case)
    values["baseline_answer"] = str(case.get("baseline_answer", ""))
    values["memory_answer"] = str(case.get("memory_answer", ""))
    values["required_terms"] = str(case.get("required_terms", ""))
    for key in ["per_tier", "max_body_chars", "max_total_chars", "max_nodes", "max_edges"]:
        values[key] = int(values[key])
    return {key: str(value) if key in STRING_FIELDS else value for key, value in values.items()}


STRING_FIELDS = {
    "claims_json",
    "scope",
    "query",
    "baseline_answer",
    "memory_answer",
    "required_terms",
    "status",
    "confidence",
    "provenance_type",
    "verify_before_use",
}


def case_claims_json(case: dict[str, Any]) -> str:
    if "claims_json" in case:
        return str(case.get("claims_json") or "")
    if "claims" not in case:
        return ""
    claims = case["claims"]
    return json.dumps({"claims": claims if isinstance(claims, list) else [claims]})
