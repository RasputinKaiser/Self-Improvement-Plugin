from __future__ import annotations
from typing import Any

from memory_fabric_claim_support_text import is_causal_claim


READY_STATUS = "causal_hypotheses_ready"
CLAIM_BOUNDARY = (
    "Causal-answer policy checks answer wording against ready causal hypotheses; "
    "it does not prove causal truth."
)


def causal_answer_policy(answer: str, brief: dict[str, Any]) -> dict[str, Any]:
    causal = is_causal_claim(answer)
    status = str(brief.get("causal_hypotheses", {}).get("status", ""))
    reasons = causal_answer_reasons(causal, status)
    return {
        "ok": not reasons,
        "status": "causal_answer_ready" if not reasons else "causal_answer_needs_verification",
        "answer_contains_causal_claim": causal,
        "causal_hypotheses_status": status,
        "reasons": reasons,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def causal_answer_reasons(causal: bool, status: str) -> list[str]:
    if causal and status != READY_STATUS:
        return ["require_ready_causal_hypotheses_before_causal_answer"]
    return []
