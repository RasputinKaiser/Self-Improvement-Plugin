from __future__ import annotations
from collections import Counter
from typing import Any


CONTEXT_ONLY_TRUST = {"context_only"}
VERIFY_TRUST = {"not_current", "usable", "verify_before_use"}
OVERCLAIM_MARKERS = [
    "confirmed",
    "definitely",
    "external truth",
    "proves",
    "proved",
    "proof of",
    "verified",
]
BOUNDARY_MARKERS = [
    "cannot prove",
    "context only",
    "context, not proof",
    "does not prove",
    "may be stale",
    "needs verification",
    "not proof",
    "not proven",
    "unverified",
    "verify",
]
CLAIM_BOUNDARY = (
    "Proof-boundary checks compare selected memory trust labels with answer wording; "
    "they do not verify external truth."
)


def proof_boundary_status(answer: str, brief: dict[str, Any]) -> dict[str, Any]:
    records = selected_records(brief)
    text = answer.lower()
    overclaims = matched_terms(text, OVERCLAIM_MARKERS)
    boundary_terms = matched_terms(text, BOUNDARY_MARKERS)
    trust_counts = Counter(map(record_trust, records))
    trust_ids = ids_by_trust(records)
    context_only_ids = trust_ids["context_only"]
    verify_ids = trust_ids["verify"]
    reasons = proof_boundary_reasons(
        context_only_ids=context_only_ids,
        verify_ids=verify_ids,
        overclaims=overclaims,
        boundary_terms=boundary_terms,
    )
    return {
        "ok": not reasons,
        "status": ["proof_boundary_preserved", "proof_boundary_blur_detected"][bool(reasons)],
        "reasons": reasons,
        "selected_trust_counts": dict(sorted(trust_counts.items())),
        "context_only_record_ids": context_only_ids,
        "verify_record_ids": verify_ids,
        "overclaim_markers": overclaims,
        "boundary_markers": boundary_terms,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def selected_records(brief: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    sections = filter(lambda item: isinstance(item, list), brief.get("sections", {}).values())
    for section in sections:
        records.extend(filter(lambda item: isinstance(item, dict), section))
    return records


def ids_by_trust(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = {"context_only": [], "verify": []}
    for record in records:
        trust = record_trust(record)
        if trust in CONTEXT_ONLY_TRUST:
            ids["context_only"].append(record_id(record))
        if trust in VERIFY_TRUST:
            ids["verify"].append(record_id(record))
    return ids


def record_trust(record: dict[str, Any]) -> str:
    return str(record.get("trust", {}).get("status", "unknown")).strip().lower() or "unknown"


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("id", "")).strip()


def matched_terms(text: str, markers: list[str]) -> list[str]:
    return list(filter(lambda marker: marker in text, markers))


def proof_boundary_reasons(
    *,
    context_only_ids: list[str],
    verify_ids: list[str],
    overclaims: list[str],
    boundary_terms: list[str],
) -> list[str]:
    reasons = []
    if proof_blur(context_only_ids, overclaims, boundary_terms):
        reasons.append("context_only_memory_presented_as_proof")
    if proof_blur(verify_ids, overclaims, boundary_terms):
        reasons.append("verification_required_memory_presented_as_proof")
    return reasons


def proof_blur(record_ids: list[str], overclaims: list[str], boundary_terms: list[str]) -> bool:
    return bool(record_ids) * bool(overclaims) * (not bool(boundary_terms))
