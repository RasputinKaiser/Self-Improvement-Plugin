from __future__ import annotations
from memory_fabric_search_filters import trust_status


CLAIM_BOUNDARY = "Path explanations describe retrieval trust; they do not prove causal truth."
PATH_USE_CONTRACT_VERSION = "path_use_ledger.v1"
PATH_USE_CLAIM_BOUNDARY = (
    "Path-use policy classifies how a graph path may guide an answer; it does not prove the claim."
)

CAUSAL_EDGE_TYPES = {
    "blocked_by",
    "blocks",
    "caused_by",
    "depends_on",
    "evidence_for",
    "fixes",
    "proved_by",
}

DECISION_EDGE_TYPES = {
    "alternative_to",
    "chosen_over",
    "decision_for",
    "rejected_for",
    "tradeoff_with",
}

TRUST_RANK = {
    "not_current": 0,
    "context_only": 1,
    "verify_before_use": 1,
    "usable": 2,
    "ready": 3,
}


def path_explanation(records_by_id, edge):
    source = records_by_id.get(str(edge.get("source", "")), {})
    target = records_by_id.get(str(edge.get("target", "")), {})
    source_trust = trust_status(source)
    target_trust = trust_status(target)
    edge_type = str(edge.get("type", ""))
    node_trusts = [source_trust["status"], target_trust["status"]]
    status = explanation_status(edge_type, node_trusts)
    return {
        "status": status,
        "edge_type": edge_type,
        "causal_edge": edge_type in CAUSAL_EDGE_TYPES,
        "decision_edge": edge_type in DECISION_EDGE_TYPES,
        "node_trusts": node_trusts,
        "trust_reasons": {
            "source": source_trust["reasons"],
            "target": target_trust["reasons"],
        },
        "evidence_by_node": {
            str(edge.get("source", "")): node_evidence(source, source_trust),
            str(edge.get("target", "")): node_evidence(target, target_trust),
        },
        "evidence_paths": evidence_paths(source, target),
        "path_use": path_use_policy(edge_type, node_trusts, status),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def explanation_status(edge_type, node_trusts):
    if edge_type in DECISION_EDGE_TYPES:
        return "decision_context"
    if edge_type not in CAUSAL_EDGE_TYPES:
        return "context_link"
    weakest = min(TRUST_RANK.get(status, 0) for status in node_trusts)
    if weakest >= TRUST_RANK["ready"]:
        return "ready_causal_context"
    if weakest >= TRUST_RANK["usable"]:
        return "usable_needs_verification"
    return "needs_verification"


def path_use_policy(edge_type, node_trusts, status):
    if edge_type in DECISION_EDGE_TYPES:
        return path_use_result(
            status="decision_context",
            usable_as="decision_context",
            proof_status="context_only",
            citation_allowed=False,
            blocks_answer=False,
            reasons=["decision_edge"],
            recommended_next_checks=[],
        )
    if edge_type not in CAUSAL_EDGE_TYPES:
        return path_use_result(
            status="context_link",
            usable_as="context_only",
            proof_status="context_only",
            citation_allowed=False,
            blocks_answer=False,
            reasons=["noncausal_edge"],
            recommended_next_checks=[],
        )
    if edge_type in {"blocked_by", "blocks"} and status == "ready_causal_context":
        return path_use_result(
            status="ready_blocker_context",
            usable_as="blocker_context",
            proof_status="ready",
            citation_allowed=True,
            blocks_answer=False,
            reasons=["blocker_edge", *trust_reasons(node_trusts)],
            recommended_next_checks=[],
        )
    if status == "ready_causal_context":
        return path_use_result(
            status="ready_causal_support",
            usable_as="causal_support",
            proof_status="ready",
            citation_allowed=True,
            blocks_answer=False,
            reasons=trust_reasons(node_trusts),
            recommended_next_checks=[],
        )
    if "not_current" in node_trusts:
        return path_use_result(
            status="blocked_not_current",
            usable_as="blocked",
            proof_status="blocked",
            citation_allowed=False,
            blocks_answer=True,
            reasons=trust_reasons(node_trusts),
            recommended_next_checks=["supersede_or_archive_stale_path_before_citing"],
        )
    return path_use_result(
        status="blocked_needs_verification",
        usable_as="causal_context_needs_verification",
        proof_status="needs_verification",
        citation_allowed=False,
        blocks_answer=True,
        reasons=trust_reasons(node_trusts),
        recommended_next_checks=["verify_or_downgrade_path_before_citing"],
    )


def path_use_result(
    *,
    status,
    usable_as,
    proof_status,
    citation_allowed,
    blocks_answer,
    reasons,
    recommended_next_checks,
):
    return {
        "contract_version": PATH_USE_CONTRACT_VERSION,
        "status": status,
        "usable_as": usable_as,
        "proof_status": proof_status,
        "citation_allowed": citation_allowed,
        "blocks_answer": blocks_answer,
        "reasons": list(dict.fromkeys(reasons)),
        "recommended_next_checks": recommended_next_checks,
        "claim_boundary": PATH_USE_CLAIM_BOUNDARY,
    }


def trust_reasons(node_trusts):
    return [f"node_trust:{trust}" for trust in node_trusts]


def evidence_paths(source, target):
    paths = [evidence_path(source), evidence_path(target)]
    return sorted({path for path in paths if path})


def evidence_path(record):
    return str(record.get("provenance", {}).get("evidence_path", "")).strip()


def node_evidence(record, trust):
    provenance = record.get("provenance", {})
    return {
        "title": str(record.get("title", "")),
        "tier": str(record.get("tier", "")),
        "trust_status": trust["status"],
        "evidence_path": evidence_path(record),
        "provenance_type": str(provenance.get("type", "")),
    }
