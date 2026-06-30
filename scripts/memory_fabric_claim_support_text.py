from __future__ import annotations
from typing import Any


CAUSAL_TERMS = {"because", "causal", "cause", "caused", "blocked", "depends", "led", "therefore"}
STOP_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "for",
    "has",
    "is",
    "it",
    "no",
    "of",
    "or",
    "that",
    "the",
    "to",
    "with",
}
MIN_CLAIM_COVERAGE = 0.75


def is_causal_claim(claim: str) -> bool:
    terms = {part.strip(".,;:!?()[]{}").lower() for part in claim.split()}
    return bool(terms & CAUSAL_TERMS)


def support_candidates(claim: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for record in records:
        coverage = claim_match_coverage(claim, record)
        if coverage["ratio"] >= MIN_CLAIM_COVERAGE:
            candidates.append({**record, "claim_match_coverage": coverage})
    return candidates


def claim_match_coverage(claim: str, record: dict[str, Any]) -> dict[str, Any]:
    terms = meaningful_terms(claim)
    matched = set(record.get("retrieval", {}).get("direct_matches", []))
    matched.update(record.get("retrieval", {}).get("semantic_matches", []))
    covered = sorted(term for term in terms if term in matched)
    ratio = (len(covered) / len(terms)) if terms else 0.0
    return {
        "policy": f"meaningful_claim_term_coverage_at_least_{MIN_CLAIM_COVERAGE}",
        "ratio": round(ratio, 3),
        "covered_terms": covered,
        "missing_terms": sorted(set(terms) - set(covered)),
    }


def meaningful_terms(value: str) -> list[str]:
    return [
        term
        for term in [part.strip(".,;:!?()[]{}").lower() for part in value.split()]
        if term and term not in STOP_TERMS
    ]


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
