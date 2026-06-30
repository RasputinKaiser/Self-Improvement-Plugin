from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_projection_audit_checks import projection_violations, recent_count

CLAIM_BOUNDARY = (
    "Projection audit checks compact JSON hygiene only; "
    "the append-only memory fabric store remains authoritative."
)


def audit_projection(
    input_path: str,
    max_bytes: int = 20000,
    max_recent: int = 12,
) -> dict[str, Any]:
    path = Path(input_path).expanduser().resolve()
    loaded = load_projection(path)
    if loaded["error"]:
        return audit_result(path, False, [loaded["error"]], max_bytes, max_recent, loaded["byte_count"])

    projection = loaded["projection"]
    violations = projection_violations(projection, loaded["byte_count"], max_bytes, max_recent)
    return audit_result(
        path,
        not violations,
        violations,
        max_bytes,
        max_recent,
        byte_count=loaded["byte_count"],
        recent_count=recent_count(projection),
        source_of_truth=projection.get("source_of_truth"),
        memory_fabric_store=projection.get("memory_fabric_store"),
    )


def load_projection(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"projection": {}, "byte_count": 0, "error": "projection_file_missing"}
    byte_count = path.stat().st_size
    try:
        projection = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"projection": {}, "byte_count": byte_count, "error": "projection_json_invalid"}
    if not isinstance(projection, dict):
        return {"projection": {}, "byte_count": byte_count, "error": "projection_not_object"}
    return {"projection": projection, "byte_count": byte_count, "error": ""}


def audit_result(
    path: Path,
    ok: bool,
    violations: list[str],
    max_bytes: int,
    max_recent: int,
    byte_count: int = 0,
    recent_count: int = 0,
    source_of_truth: Any = None,
    memory_fabric_store: Any = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": "projection_compact" if ok else "projection_audit_failed",
        "input": str(path),
        "byte_count": byte_count,
        "max_bytes": max_bytes,
        "recent_count": recent_count,
        "max_recent": max_recent,
        "source_of_truth": source_of_truth,
        "memory_fabric_store": memory_fabric_store,
        "violations": violations,
        "claim_boundary": CLAIM_BOUNDARY,
    }
