from __future__ import annotations
PRICING_REQUIRED_CUES = ["candidate_match", "visual_comparison"]


def pricing_gate(rows):
    missing = [
        row["id"]
        for row in rows
        if row["id"] in PRICING_REQUIRED_CUES and row["status"] == "missing"
    ]
    if missing:
        return {
            "ok": False,
            "status": "price_after_candidate_match_and_visual_comparison",
            "blocked_by": missing,
        }
    return {"ok": True, "status": "pricing_context_ready", "blocked_by": []}
