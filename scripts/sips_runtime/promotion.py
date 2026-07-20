"""Lesson promotion policy for graph runtime receipts."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Mapping


def _existing_promotion(**kwargs: Any) -> dict[str, Any]:
    for module_name in ("memory_fabric_promotion", "scripts.memory_fabric_promotion"):
        try:
            module = importlib.import_module(module_name)
            function = getattr(module, "assess_promotion", None)
            if callable(function):
                return dict(function(**kwargs))
        except Exception:
            continue
    # The runtime remains usable in an isolated checkout where Memory Fabric
    # is not importable; this fallback preserves the same proof boundary.
    return {
        "ok": True,
        "can_promote": False,
        "recommended_status": "candidate",
        "verify_before_use": True,
        "reasons": ["existing promotion audit unavailable"],
        "required_evidence": ["run the Memory Fabric promotion audit"],
    }


def _conflict_audit(lesson: Mapping[str, Any], audit: Callable[..., Any] | None = None) -> dict[str, Any]:
    if audit is not None:
        try:
            result = audit(dict(lesson))
            return dict(result) if isinstance(result, Mapping) else {"ok": result is True}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    supplied = lesson.get("conflict_audit", lesson.get("conflicts"))
    if isinstance(supplied, Mapping):
        result = dict(supplied)
        receipt_digest = str(lesson.get("receipt_digest", ""))
        if (
            result.get("source")
            not in {"graph_receipt", "graph_receipt_and_memory_store"}
            or not receipt_digest
            or str(result.get("receipt_digest", "")) != receipt_digest
        ):
            return {
                "ok": False,
                "error": "authoritative receipt-bound conflict audit required",
            }
        return result
    if supplied:
        return {"ok": False, "conflicts": list(supplied) if not isinstance(supplied, str) else [supplied]}
    return {"ok": False, "error": "authoritative conflict audit required"}


def promote_lesson(
    lesson: Mapping[str, Any] | None = None,
    *,
    tier: str = "learning",
    text: str = "",
    provenance_type: str = "user_or_agent_observation",
    evidence_path: str = "",
    confidence: str = "medium",
    conflict_audit: Callable[..., Any] | None = None,
    activate: bool = False,
) -> dict[str, Any]:
    """Return a candidate lesson; never forces active status by default."""
    if type(activate) is not bool:
        raise ValueError("activate must be a boolean")
    data = dict(lesson or {})
    if "activate" in data:
        raise ValueError("lesson.activate is not allowed; use the explicit activate argument")
    tier = str(data.get("tier", tier))
    text = str(data.get("text", data.get("body", text)))
    promotion = _existing_promotion(
        tier=tier,
        text=text,
        provenance_type=str(data.get("provenance_type", provenance_type)),
        evidence_path=str(data.get("evidence_path", evidence_path)),
        confidence=str(data.get("confidence", confidence)),
    )
    conflicts = _conflict_audit(data, conflict_audit)
    references = data.get("references", data.get("refs", ()))
    if isinstance(references, Mapping):
        references = [references]
    known_ids = {str(value) for value in data.get("known_record_ids", ())}
    dangling = sorted(
        str(reference.get("target_id", reference.get("id", "")))
        for reference in (references or ())
        if isinstance(reference, Mapping)
        and reference.get("target_id", reference.get("id"))
        and str(reference.get("target_id", reference.get("id"))) not in known_ids
    )
    evidence_value = str(data.get("evidence_path", evidence_path)).strip()
    evidence_ok = bool(evidence_value) and (
        evidence_value.startswith(("http://", "https://"))
        or Path(evidence_value).expanduser().exists()
    )
    provenance_value = str(data.get("provenance_type", provenance_type)).strip()
    provenance_ok = bool(provenance_value) and bool(
        data.get("run_id") or data.get("provenance") or provenance_value == "user_instruction"
    )
    supersession_ok = not bool(
        data.get("superseded")
        or data.get("superseded_by")
        or str(data.get("status", "")).lower() == "superseded"
    )
    usage = data.get("usage") if isinstance(data.get("usage"), Mapping) else {}
    usage_ok = (
        usage.get("source") == "graph_receipt"
        and str(usage.get("receipt_digest", ""))
        == str(data.get("receipt_digest", ""))
        and usage.get("efficiency_claim_eligible") is True
        and not bool(usage.get("unknown_dimensions"))
    )
    audits = {
        "contradiction": conflicts,
        "supersession": {"ok": supersession_ok},
        "dangling_references": {"ok": not dangling, "dangling": dangling},
        "provenance": {"ok": provenance_ok, "type": provenance_value},
        "evidence_path": {"ok": evidence_ok, "path": evidence_value},
        "usage": {"ok": usage_ok, "unknown_dimensions": list(usage.get("unknown_dimensions", ()))},
    }
    audit_ok = all(item.get("ok") is True for item in audits.values())
    # Candidate is the safe default even when an old audit recommends active.
    requested_active = activate
    status = "active" if requested_active and promotion.get("can_promote") is True and audit_ok else "candidate"
    result = {
        **data,
        "tier": tier,
        "text": text,
        "status": status,
        "verify_before_use": status != "active",
        "promotion_audit": promotion,
        "conflict_audit": conflicts,
        "audits": audits,
        "can_promote": promotion.get("can_promote") is True and audit_ok,
        "activation_requested": requested_active,
        "activation_forced": False,
    }
    return result


def promotion_candidate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("activate", False)
    return promote_lesson(*args, **kwargs)


promote = promote_lesson

__all__ = ["promote_lesson", "promotion_candidate", "promote"]
