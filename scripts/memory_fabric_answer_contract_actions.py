from __future__ import annotations
PRICE_TERMS = [
    "$",
    " price",
    " priced",
    " pricing",
    " worth",
    " value",
    " valued",
    " appraisal",
    " comparable sale",
    " comparable sales",
    " comp ",
    " comps",
    " sold for",
    " listing price",
]


def blocked_action_violations(answer: str, blocked_actions: list[str]) -> list[dict[str, str]]:
    text = f" {answer.lower()} "
    violations = []
    for action in blocked_actions:
        term = violating_term(text, action)
        if term:
            violations.append({"action": action, "matched_term": term})
    return violations


def violating_term(text: str, action: str) -> str:
    if action == "do_not_price_before_candidate_match_and_visual_comparison":
        return first_present(text, PRICE_TERMS)
    return ""


def first_present(text: str, terms: list[str]) -> str:
    for term in terms:
        if term in text:
            return term.strip()
    return ""
