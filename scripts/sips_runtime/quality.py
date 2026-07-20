"""Lexicographic quality gates for graph receipts and promotions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


GATE_ORDER = ("integrity", "correctness", "regression", "resource", "benefit")
HIGH_IMPACT = {"high", "critical", "p0", "p1"}
HIGH_IMPACT_RISK_TAGS = {
    "permissions", "persistence", "authentication", "money", "schema_migration", "destructive", "destructive_action", "external_write"
}
BAD_EVIDENCE_MARKERS = {
    "unknown",
    "missing",
    "contradictory",
    "contradiction",
    "conflict",
    "failed",
    "failure",
    "rejected",
    "invalid",
    "zero",
    "zero_case",
    "no_cases",
    "unverified",
}
GOOD_EVIDENCE_MARKERS = {
    "passed",
    "pass",
    "verified",
    "supported",
    "ready",
    "active",
    "ok",
    "success",
    "succeeded",
    "approved",
}
EVIDENCE_ANCHOR_KEYS = {
    "evidence_path",
    "path",
    "digest",
    "receipt_digest",
    "artifact_id",
    "command",
    "uri",
    "source_id",
}
EVIDENCE_COUNT_KEYS = {
    "count",
    "case_count",
    "scenario_count",
    "total_cases",
    "total",
    "tests_run",
    "test_count",
    "sample_count",
}


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    evidence: tuple[Any, ...] = ()
    reasons: tuple[str, ...] = ()
    reviewer_tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "evidence": list(self.evidence),
            "reasons": list(self.reasons),
            "reviewer_tags": list(self.reviewer_tags),
        }


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        output = value.to_dict()
        if isinstance(output, Mapping):
            return dict(output)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _evidence(value: Any) -> list[Any]:
    if value is None or value is False:
        return []
    if isinstance(value, Mapping):
        values = value.get("evidence", value.get("proof", value.get("items", [])))
        if values is None:
            values = []
        if isinstance(values, (str, bytes)):
            return [values]
        return list(values) if isinstance(values, Iterable) else [values]
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _gate_ok(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, Mapping):
        return value.get("ok", value.get("passed", value.get("pass", False))) is True
    return False


def validate_evidence_items(
    values: Iterable[Any], *, allow_plain_references: bool = False
) -> tuple[bool, list[str]]:
    """Validate proof objects shared by gates, claims, acceptance, and review."""
    reasons: list[str] = []
    for item in values:
        if isinstance(item, Mapping):
            if not item:
                reasons.append("evidence_unsubstantiated")
                continue
            marker = str(item.get("status", item.get("outcome", item.get("result", "")))).strip().lower()
            if marker in BAD_EVIDENCE_MARKERS:
                reasons.append(f"evidence_{marker}")
            if item.get("contradictory") is True or item.get("conflict") is True:
                reasons.append("evidence_contradictory")
            explicitly_positive = marker in GOOD_EVIDENCE_MARKERS
            for boolean_key in ("ok", "passed", "pass"):
                if boolean_key not in item:
                    continue
                boolean_value = item[boolean_key]
                if type(boolean_value) is not bool:
                    reasons.append("evidence_invalid_boolean")
                elif boolean_value:
                    explicitly_positive = True
                else:
                    reasons.append("evidence_failed")
            positive_count = False
            count_keys = sorted(
                {
                    key
                    for key in item
                    if key in EVIDENCE_COUNT_KEYS or str(key).endswith("_count")
                }
            )
            for count_key in count_keys:
                if count_key not in item:
                    continue
                count = item[count_key]
                if not isinstance(count, int) or isinstance(count, bool):
                    reasons.append("evidence_invalid_count")
                elif count <= 0:
                    reasons.append("evidence_zero_case")
                else:
                    positive_count = True
            anchored = any(
                key in item and item[key] not in (None, "", [], {})
                for key in EVIDENCE_ANCHOR_KEYS
            )
            if marker and marker not in GOOD_EVIDENCE_MARKERS | BAD_EVIDENCE_MARKERS:
                reasons.append("evidence_unverified_status")
            if not anchored:
                reasons.append("evidence_missing_anchor")
            if not explicitly_positive:
                reasons.append("evidence_missing_positive_outcome")
            if not positive_count:
                reasons.append("evidence_missing_case_count")
        else:
            marker = str(item).strip().lower()
            if not marker:
                reasons.append("evidence_unsubstantiated")
            elif marker in BAD_EVIDENCE_MARKERS:
                reasons.append(f"evidence_{marker}")
            elif not allow_plain_references:
                reasons.append("evidence_reference_unresolved")
    return not reasons, sorted(set(reasons))


def evaluate_gates(
    gates: Mapping[str, Any] | None = None,
    *,
    evidence: Mapping[str, Any] | None = None,
    impact: str = "normal",
    reviewer_tags: Iterable[str] | None = None,
    risk_tags: Iterable[str] | None = None,
    require_evidence: bool = True,
    required_reviewer_tags: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Evaluate gates in strict integrity→benefit order.

    A failed earlier gate does not hide later results; all are returned in the
    stable order so operators can fix several independent gaps at once.  Each
    gate is evidence-bearing by default.  High-impact changes additionally need
    reviewer tags, with the default requirement being ``reviewer``.
    """
    if type(require_evidence) is not bool:
        raise TypeError("require_evidence must be a boolean")
    supplied = dict(gates or {})
    evidence_map = dict(evidence or {})
    tags = {str(tag).strip().lower() for tag in (reviewer_tags or ()) if str(tag).strip()}
    risks = {str(tag).strip().lower() for tag in (risk_tags or ()) if str(tag).strip()}
    normalized_impact = str(impact or "normal").strip().lower()
    required_tags = {str(tag).strip().lower() for tag in (required_reviewer_tags or ("reviewer",)) if str(tag).strip()}
    results: list[GateResult] = []
    for name in GATE_ORDER:
        raw = supplied.get(name, False)
        raw_map = _mapping(raw)
        ev = _evidence(raw_map if raw_map else evidence_map.get(name, raw if raw is not True else None))
        reasons: list[str] = []
        ok = _gate_ok(raw)
        if require_evidence and not ev:
            ok = False
            reasons.append("evidence_required")
        evidence_ok, evidence_reasons = validate_evidence_items(ev)
        if not evidence_ok:
            ok = False
            reasons.extend(evidence_reasons)
        if not ok and not reasons:
            reasons.append("gate_failed")
        gate_tags = set(str(tag).lower() for tag in raw_map.get("reviewer_tags", ()))
        results.append(GateResult(name, ok, tuple(ev), tuple(reasons), tuple(sorted(gate_tags))))

    reviewer_missing: list[str] = []
    reviewer_required = normalized_impact in HIGH_IMPACT or bool(risks.intersection(HIGH_IMPACT_RISK_TAGS))
    if reviewer_required:
        reviewer_present = any(
            tag == "reviewer" or tag.startswith("reviewer:") or tag in {"approved", "high-impact-reviewer"}
            for tag in tags
        )
        reviewer_missing = [] if reviewer_present else sorted(required_tags)
        if reviewer_missing:
            # Keep the quality gate list unchanged; reviewer approval is a
            # separate explicit blocker in the receipt.
            pass
    ok = all(result.ok for result in results) and not reviewer_missing
    return {
        "ok": ok,
        "gate_order": list(GATE_ORDER),
        "gates": [result.to_dict() for result in results],
        "failed_gates": [result.name for result in results if not result.ok],
        "impact": normalized_impact,
        "risk_tags": sorted(risks),
        "reviewer_tags": sorted(tags),
        "required_reviewer_tags": sorted(required_tags) if reviewer_required else [],
        "missing_reviewer_tags": reviewer_missing,
        "high_impact_reviewer_required": reviewer_required,
        "evidence_required": require_evidence,
    }


def quality_gates(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return evaluate_gates(*args, **kwargs)


check_gates = evaluate_gates
evaluate_quality = evaluate_gates


def gate_passed(result: Mapping[str, Any], name: str) -> bool:
    return any(item.get("name") == name and item.get("ok") is True for item in result.get("gates", ()))


__all__ = ["GATE_ORDER", "GateResult", "evaluate_gates", "quality_gates", "check_gates", "evaluate_quality", "gate_passed", "validate_evidence_items"]
