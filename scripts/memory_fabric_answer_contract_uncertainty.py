from __future__ import annotations
UNCERTAINTY_TERMS = [
    "unverified",
    "not verified",
    "not proved",
    "not proven",
    "needs verification",
    "verify before",
    "cannot verify",
    "should verify",
    "needs source",
]


def uncertainty_ok(answer: str, required: bool) -> bool:
    if not required:
        return True
    text = answer.lower()
    return any(term in text for term in UNCERTAINTY_TERMS)
