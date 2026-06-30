from __future__ import annotations
from typing import Any

from memory_fabric_semantic_aliases import CLAIM_BOUNDARY


def match_score(record: dict[str, Any], profile: dict[str, Any], fields: list[tuple[str, int]]) -> int:
    direct = sum(weighted_presence(term, fields, semantic=False) for term in profile["direct_terms"])
    semantic = sum(weighted_presence(term, fields, semantic=True) for term in profile["expanded_terms"])
    return max(1, direct + semantic)


def weighted_presence(term: str, fields: list[tuple[str, int]], *, semantic: bool) -> int:
    total = 0
    for text, weight in fields:
        base = max(1, weight // 2) if semantic else weight
        total += int(term in text) * base
    return total


def match_explanation(record: dict[str, Any], profile: dict[str, Any], fields: list[tuple[str, int]]) -> dict[str, Any]:
    direct = matching_terms(profile["direct_terms"], fields)
    semantic = matching_terms(profile["expanded_terms"], fields)
    return {
        "direct_matches": direct,
        "semantic_matches": semantic,
        "match_kind": match_kind(direct, semantic),
        "matched_expansions": matched_expansions(profile["expansions"], semantic),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def match_kind(direct: list[str], semantic: list[str]) -> str:
    if direct and semantic:
        return "direct_and_semantic"
    if direct:
        return "direct"
    if semantic:
        return "semantic_only"
    return "none"


def matching_terms(terms: list[str], fields: list[tuple[str, int]]) -> list[str]:
    return list(filter(lambda term: term_matches(term, fields), terms))


def term_matches(term: str, fields: list[tuple[str, int]]) -> bool:
    return any(map(lambda field: term in field[0], fields))


def matched_expansions(expansions: dict[str, list[str]], semantic_matches: list[str]) -> dict[str, list[str]]:
    matched = set(semantic_matches)
    return {
        source: [term for term in aliases if term in matched]
        for source, aliases in expansions.items()
        if any(term in matched for term in aliases)
    }
