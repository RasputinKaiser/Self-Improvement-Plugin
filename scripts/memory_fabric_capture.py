from __future__ import annotations
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from memory_fabric_capture_ops import (
    project_work,
    record_learning,
    record_work,
    search_learning,
    source_backed_policy,
    weak_knowledge_policy,
)


def capture_representative_usage(output: str = "", store: str = "", min_scenarios: int = 3) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="memory-fabric-capture-") as tmp:
        store_path = Path(store).expanduser().resolve() if store else Path(tmp) / "memory.jsonl"
        projection_path = Path(tmp) / "projection.json"
        events = [
            capture_event("record-learning-memory", "record", lambda: record_learning(store_path)),
            capture_event("record-learning-memory", "search", lambda: search_learning(store_path)),
            capture_event("search-and-project-work-memory", "record", lambda: record_work(store_path)),
            capture_event(
                "search-and-project-work-memory",
                "project",
                lambda: project_work(store_path, projection_path),
            ),
            capture_event("proof-boundary-knowledge", "weak-evidence-policy", weak_knowledge_policy),
            capture_event("proof-boundary-knowledge", "source-backed-policy", source_backed_policy),
        ]
    return capture_report(events, output, min_scenarios)


def capture_event(scenario: str, operation: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    result = action()
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "type": "memory_fabric.operation.done",
        "scenario": scenario,
        "operation": operation,
        "ok": bool(result.get("ok")),
        "duration_ms": duration_ms,
        "result_summary": compact_result(result),
        "token_usage": None,
        "fabricated_token_telemetry": False,
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"ok": bool(result.get("ok"))}
    for key in ["count", "tier", "can_promote", "recommended_status", "verify_before_use", "output", "store"]:
        if key in result:
            summary[key] = result[key]
    if "record" in result:
        summary["record_tier"] = result["record"].get("tier")
        summary["record_title"] = result["record"].get("title")
    return summary


def capture_report(events: list[dict[str, Any]], output: str, min_scenarios: int) -> dict[str, Any]:
    scenarios = sorted({event["scenario"] for event in events})
    representative = len(scenarios) >= min_scenarios and all(event["ok"] for event in events)
    target = write_events(events, output) if output else ""
    return {
        "ok": representative,
        "status": "representative_operational_usage_captured" if representative else "operational_usage_incomplete",
        "fabricated": False,
        "token_telemetry_available": False,
        "plugin_eval_observed_usage_ready": False,
        "sample_count": len(events),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "minimums": {"scenarios": min_scenarios},
        "output": target,
        "events": events[:20],
        "claim_boundary": (
            "These are real operation traces with no model token telemetry; "
            "do not pass them to Plugin Eval as observed token usage."
        ),
    }


def write_events(events: list[dict[str, Any]], output: str) -> str:
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return str(target)
