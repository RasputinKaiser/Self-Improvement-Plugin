from __future__ import annotations
from typing import Any


TOKEN_FIELDS = {
    "input_tokens": ("input_tokens", "prompt_tokens"),
    "output_tokens": ("output_tokens", "completion_tokens"),
    "total_tokens": ("total_tokens",),
}


def valid_usage(usage: Any) -> bool:
    if not isinstance(usage, dict):
        return False
    return any(first_int(usage, aliases) is not None for aliases in TOKEN_FIELDS.values())


def sample_from_usage(usage: dict[str, Any], source: str, kind: str) -> dict[str, Any]:
    tokens = {field: first_int(usage, aliases) or 0 for field, aliases in TOKEN_FIELDS.items()}
    return {"source": source, "kind": kind, **tokens}


def first_int(payload: dict[str, Any], aliases: tuple[str, ...]) -> int | None:
    for alias in aliases:
        value = payload.get(alias)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def token_totals(samples: list[dict[str, Any]]) -> dict[str, int]:
    return {field: sum(int(sample.get(field, 0)) for sample in samples) for field in TOKEN_FIELDS}


def token_averages(totals: dict[str, int], count: int) -> dict[str, float]:
    if not count:
        return {field: 0.0 for field in TOKEN_FIELDS}
    return {field: round(value / count, 2) for field, value in totals.items()}


def token_totals_report(values: dict[str, int | float]) -> dict[str, int | float]:
    return {
        "input": values["input_tokens"],
        "output": values["output_tokens"],
        "total": values["total_tokens"],
    }
