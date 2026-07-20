from __future__ import annotations
from typing import Any


def gate(ok: bool, status: str, summary: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "status": status,
        "summary": summary,
        "details": details or {},
    }


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
