from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_behavior_receipts import behavior_receipts
from memory_fabric_install import doctor


def plugin_eval_receipt(path: str, min_score: int) -> dict[str, Any]:
    if not path:
        return {"ok": False, "status": "plugin_eval_not_supplied", "min_score": min_score}
    data = read_json(path)
    summary = data.get("summary", data)
    score = int(summary.get("score", 0) or 0)
    return {
        "ok": score >= min_score,
        "status": "plugin_eval_ready" if score >= min_score else "plugin_eval_below_threshold",
        "score": score,
        "grade": summary.get("grade", ""),
        "risk": summary.get("riskLevel", summary.get("risk", "")),
        "min_score": min_score,
        "path": path,
    }


def benchmark_receipt(path: str) -> dict[str, Any]:
    if not path:
        return {"ok": False, "status": "benchmark_not_supplied"}
    data = read_json(path)
    ok = bool(data.get("ok")) and int(data.get("failed", 0) or 0) == 0
    return {
        "ok": ok,
        "status": "benchmark_ready" if ok else "benchmark_failed",
        "passed": data.get("passed", 0),
        "failed": data.get("failed", 0),
        "scenario_count": data.get("scenario_count", 0),
        "path": path,
    }


def current_live_summary(
    current_doctor_json: str,
    advertised_tools: list[str] | None,
    advertised_surface: dict[str, Any] | None,
    advertised_truncated: bool,
    plugin_root: str | Path | None,
    marketplace_path: str | Path | None,
    cache_root: str | Path | None,
) -> dict[str, Any]:
    if current_doctor_json:
        return doctor_receipt(current_doctor_json)
    if advertised_tools or advertised_surface:
        report = doctor(
            plugin_root=plugin_root,
            marketplace_path=marketplace_path,
            cache_root=cache_root,
            check_cli_surface=False,
            advertised_tools=advertised_tools,
            advertised_surface=advertised_surface,
            advertised_truncated=advertised_truncated,
        )
        summary = doctor_summary(report)
        summary["source"] = "inline_doctor"
        return summary
    return doctor_receipt("")


def doctor_receipt(path: str) -> dict[str, Any]:
    if not path:
        return {"ok": None, "status": "doctor_not_supplied", "tool_exposure_checked": False}
    summary = doctor_summary(read_json(path))
    summary["path"] = path
    return summary


def doctor_summary(data: dict[str, Any]) -> dict[str, Any]:
    live = data.get("live", {})
    surface = live.get("surface", {})
    stdio = data.get("stdio", {})
    return {
        "ok": live.get("ok"),
        "status": live.get("status", data.get("status", "")),
        "tool_exposure_checked": bool(live.get("tool_exposure_checked")),
        "partial_tool_exposure_checked": bool(live.get("partial_tool_exposure_checked")),
        "advertised_count": live.get("advertised_count", 0),
        "advertised_truncated": bool(live.get("advertised_truncated")),
        "missing_tools": live.get("missing_tools", []),
        "unverified_tools": live.get("unverified_tools", []),
        "exact_missing_tools": live.get("exact_missing_tools", []),
        "aliased_tools": live.get("aliased_tools", {}),
        "surface_checked": bool(live.get("surface_checked") or surface.get("surface_checked")),
        "missing_params": surface.get("missing_params", {}),
        "unchecked_tools": surface.get("unchecked_tools", []),
        "stdio_checked": bool(stdio and not stdio.get("skipped")),
        "stdio_ok": stdio.get("ok"),
        "stdio_status": stdio.get("status", ""),
        "stdio_tool_count": stdio.get("tool_count", 0),
        "stdio_required_tool_count": stdio.get("required_tool_count", 0),
        "stdio_missing_tools": stdio.get("missing_tools", []),
    }


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
