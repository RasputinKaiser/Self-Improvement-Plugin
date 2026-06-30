from __future__ import annotations
from typing import Any


def score_terms(text: str, terms: list[str]) -> int:
    return sum(token in text for token in terms)


def classify_note(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    scores = {
        "work": score_terms(lowered, ["task", "next", "blocker", "decision", "active", "todo"]),
        "knowledge": score_terms(lowered, ["api", "research", "docs", "framework", "source", "domain"]),
        "learning": score_terms(lowered, ["symptom", "false lead", "fix", "lesson", "mistake", "works"]),
    }
    tier = max(scores, key=scores.get)
    if scores[tier] == 0:
        tier = "learning" if "proof" in lowered or "verified" in lowered else "work"
    return {
        "suggested_tier": tier,
        "scores": scores,
        "rationale": (
            "Learning Memory is for reusable verified fixes; Knowledge Memory is for source-backed facts; "
            "Work Memory is for current decisions and next actions."
        ),
    }
