from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_jsonl import append_record
from memory_fabric_projection import project
from memory_fabric_promotion import assess_promotion
from memory_fabric_records import make_record
from memory_fabric_search import search_records


def record_learning(store_path: Path) -> dict[str, Any]:
    record = make_record(
        tier="learning",
        title="Measurement plans must not stand in for telemetry",
        body="Symptom: proof drift. Fix: separate capture plan from usage data. Proof: capture runner emits no tokens.",
        scope="codex-memory-fabric",
        tags="capture learning",
        provenance_type="source_backed_agent_run",
        evidence_path=str(store_path),
        confidence="high",
    )
    return append_record(record, store_path)


def search_learning(store_path: Path) -> dict[str, Any]:
    return search_records(query="proof drift telemetry", tier="learning", scope="codex-memory-fabric", path=store_path)


def record_work(store_path: Path) -> dict[str, Any]:
    record = make_record(
        tier="work",
        title="Representative capture runner",
        body="Build operational traces for record, search, project, and policy paths.",
        scope=str(Path.home() / "Downloads/CodexSupreme"),
        tags="capture work",
        provenance_type="source_backed_agent_run",
        evidence_path=str(store_path),
        confidence="high",
    )
    return append_record(record, store_path)


def project_work(store_path: Path, projection_path: Path) -> dict[str, Any]:
    return project(
        scope=str(Path.home() / "Downloads/CodexSupreme"),
        output=str(projection_path),
        path=store_path,
    )


def weak_knowledge_policy() -> dict[str, Any]:
    return assess_promotion(
        tier="knowledge",
        text="Screen context says the tool is live.",
        provenance_type="screen_observation",
    )


def source_backed_policy() -> dict[str, Any]:
    return assess_promotion(
        tier="knowledge",
        text="Plugin source exports the capture command.",
        provenance_type="source_file",
        evidence_path=str(Path.home() / "plugins/codex-memory-fabric/scripts/memory_fabric_capture.py"),
        confidence="high",
    )
