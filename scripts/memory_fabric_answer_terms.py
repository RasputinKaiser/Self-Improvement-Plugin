from __future__ import annotations
from typing import Any


def expected_terms(required_terms: str, brief: dict[str, Any]) -> list[str]:
    supplied = split_terms(required_terms)
    return supplied if supplied else derived_terms(brief)


def split_terms(value: str) -> list[str]:
    return [item.strip().lower() for item in value.replace("\n", ",").split(",") if item.strip()]


def derived_terms(brief: dict[str, Any]) -> list[str]:
    titles = [
        str(record.get("title", ""))
        for records in brief.get("sections", {}).values()
        for record in records
    ]
    return [term for term in unique_words(" ".join(titles)) if len(term) >= 4][:8]


def unique_words(value: str) -> list[str]:
    words = []
    for raw in value.lower().replace("_", " ").split():
        add_word(words, raw)
    return words


def add_word(words: list[str], raw: str) -> None:
    word = "".join(ch for ch in raw if ch.isalnum())
    if word and word not in words:
        words.append(word)
