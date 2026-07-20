from __future__ import annotations
from typing import Any

from memory_fabric_schema import CONTEXT_ONLY_PROVENANCE, STRONG_PROVENANCE, normalize_confidence
from memory_fabric_schema import normalize_provenance_type, normalize_tier


def assess_promotion(
    *,
    tier: str,
    text: str,
    provenance_type: str = "user_or_agent_observation",
    evidence_path: str = "",
    confidence: str = "medium",
) -> dict[str, Any]:
    normalized_tier = normalize_tier(tier)
    normalized_confidence = normalize_confidence(confidence)
    provenance = normalize_provenance_type(provenance_type)
    reasons: list[str] = []
    required: list[str] = []
    can_promote = True

    can_promote = apply_context_only_policy(normalized_tier, provenance, reasons, required, can_promote)
    can_promote = apply_knowledge_policy(normalized_tier, provenance, evidence_path, reasons, required, can_promote)
    can_promote = apply_learning_policy(normalized_tier, text, reasons, required, can_promote)

    verify_before_use = verify_policy(can_promote, normalized_confidence)
    return {
        "ok": True,
        "tier": normalized_tier,
        "confidence": normalized_confidence,
        "can_promote": can_promote,
        "recommended_status": {True: "active", False: "candidate"}[can_promote],
        "verify_before_use": verify_before_use,
        "reasons": reasons or ["Promotion policy passed."],
        "required_evidence": required,
        "provenance_type": provenance,
    }


def apply_context_only_policy(
    tier: str,
    provenance: str,
    reasons: list[str],
    required: list[str],
    can_promote: bool,
) -> bool:
    if provenance not in CONTEXT_ONLY_PROVENANCE:
        return can_promote
    reasons.append(f"{provenance} is context-only, not durable proof.")
    required.append("Add command, file, source, or explicit user evidence before durable promotion.")
    return tier == "work"


def apply_knowledge_policy(
    tier: str,
    provenance: str,
    evidence_path: str,
    reasons: list[str],
    required: list[str],
    can_promote: bool,
) -> bool:
    if tier != "knowledge" or source_backed(provenance, evidence_path):
        return can_promote
    reasons.append("Knowledge Memory needs source-backed evidence.")
    required.append("Provide a source file, document URL, command receipt, or user instruction.")
    return False


def apply_learning_policy(
    tier: str,
    text: str,
    reasons: list[str],
    required: list[str],
    can_promote: bool,
) -> bool:
    if tier != "learning":
        return can_promote
    missing = missing_learning_markers(text)
    if not missing:
        return can_promote
    reasons.append(f"Learning Memory is missing reusable fix markers: {', '.join(missing)}.")
    required.append("Capture symptom, fix, and proof before promoting.")
    return False


def source_backed(provenance: str, evidence_path: str) -> bool:
    return provenance in STRONG_PROVENANCE and bool(evidence_path.strip())


def missing_learning_markers(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [marker for marker in ["symptom", "fix", "proof"] if marker not in lowered]


def verify_policy(can_promote: bool, confidence: str) -> bool:
    if not can_promote:
        return True
    return confidence in {"low", "unknown"}
