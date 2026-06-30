from __future__ import annotations
from typing import Any

from memory_fabric_semantic_aliases import CLAIM_BOUNDARY, SEMANTIC_ALIASES
from memory_fabric_semantic_match import match_explanation, match_score



def query_profile(query: str | list[str]) -> dict[str, Any]:
    direct = query_terms(query)
    expansions = semantic_expansions(direct)
    expanded = sorted({term for values in expansions.values() for term in values})
    return {
        "direct_terms": direct,
        "expanded_terms": expanded,
        "expansions": expansions,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def query_terms(query: str | list[str]) -> list[str]:
    source = (str(query), " ".join(map(str, query)))[isinstance(query, list)]
    return source.lower().split()


def semantic_expansions(terms: list[str]) -> dict[str, list[str]]:
    expansions = {}
    for term in terms:
        aliases = SEMANTIC_ALIASES.get(term, [])
        if aliases:
            expansions[term] = aliases
    return expansions

