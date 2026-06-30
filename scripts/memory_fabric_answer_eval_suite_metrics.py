from __future__ import annotations
from typing import Any


def minimum_metric(results: list[dict[str, Any]], key: str) -> int:
    values = [int(result[key]) for result in results]
    return min(values) if values else 0


def sum_metric(results: list[dict[str, Any]], key: str) -> int:
    return sum(int(result[key]) for result in results)
