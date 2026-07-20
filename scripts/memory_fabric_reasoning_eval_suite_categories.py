from __future__ import annotations
from typing import Any

from memory_fabric_reasoning_eval_suite_category_checks import category_checks


def suite_next_checks(results: list[dict[str, Any]]) -> list[str]:
    checks = [
        check
        for result in results
        if not result["ok"]
        for check in result.get("recommended_next_checks", [])
    ]
    checks.extend(category_checks(results))
    return list(dict.fromkeys(str(check) for check in checks if str(check).strip()))
