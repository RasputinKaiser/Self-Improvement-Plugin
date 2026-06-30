from __future__ import annotations
from typing import Any


PROOF_BOUNDARY_TERMS = ["source", "evidence", "verify", "live", "cache", "proof", "boundary"]
EVIDENCE_MARKERS = ["evidence:", "proved by:", "receipt", "source:", ".json", ".txt", ".md"]


def answer_score(answer: str, required_terms: list[str]) -> dict[str, Any]:
    text = answer.lower()
    covered = covered_terms(text, required_terms)
    evidence_count = evidence_reference_count(text)
    boundary = proof_boundary_present(text)
    return {
        "score": len(covered) * 2 + evidence_count + int(boundary),
        "covered_terms": covered,
        "missing_terms": missing_terms(covered, required_terms),
        "coverage_ratio": coverage_ratio(covered, required_terms),
        "evidence_reference_count": evidence_count,
        "proof_boundary_present": boundary,
    }


def covered_terms(text: str, required_terms: list[str]) -> list[str]:
    return [term for term in required_terms if term in text]


def missing_terms(covered: list[str], required_terms: list[str]) -> list[str]:
    return [term for term in required_terms if term not in covered]


def coverage_ratio(covered: list[str], required_terms: list[str]) -> float:
    return round(len(covered) / max(1, len(required_terms)), 3)


def evidence_reference_count(text: str) -> int:
    return sum(marker in text for marker in EVIDENCE_MARKERS)


def proof_boundary_present(text: str) -> bool:
    return any(term in text for term in PROOF_BOUNDARY_TERMS)
