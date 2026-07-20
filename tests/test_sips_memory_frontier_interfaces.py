from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

from sips_runtime.memory_frontier import compatibility_graph


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "memory_fabric.py"


def _record(number: int, *, body: str = "Indexed frontier needle") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "id": f"mem_{number:016x}",
        "tier": "learning",
        "title": f"Frontier note {number}",
        "body": body,
        "scope": "project/frontier",
        "tags": ["frontier"],
        "provenance": {"type": "source_file", "evidence_path": "evidence/frontier.md"},
        "confidence": "high",
        "verify_before_use": False,
        "status": "active",
        "created_at": f"2026-01-01T00:00:{number:02d}+00:00",
    }


def _write_store(path: Path, records: list[dict[str, object]]) -> None:
    contents = "".join(json.dumps(item, sort_keys=True) + "\n" for item in records)
    path.write_text(contents, encoding="utf-8")


def test_cli_indexed_frontier_executes_with_explicit_scope_query_and_caps(tmp_path):
    store = tmp_path / "memory.jsonl"
    _write_store(store, [_record(1), _record(2)])
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--store",
            str(store),
            "indexed-frontier",
            "--scope",
            "project/frontier",
            "--query",
            "needle",
            "--seed-limit",
            "1",
            "--fanout",
            "1",
            "--max-depth",
            "0",
            "--max-nodes",
            "1",
            "--max-edges",
            "1",
            "--max-paths",
            "1",
            "--token-budget",
            "80",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONPATH=str(ROOT / "scripts")),
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema"] == "memory.frontier.v1"
    assert payload["scope"] == "project/frontier"
    assert payload["query"] == "needle"
    assert payload["limits"] == {
        "seed_limit": 1,
        "fanout": 1,
        "max_depth": 0,
        "max_nodes": 1,
        "max_edges": 1,
        "max_paths": 1,
        "token_budget": 80,
    }
    assert payload["node_count"] == 1


def test_cli_indexed_frontier_requires_scope_and_query():
    completed = subprocess.run(
        [sys.executable, str(CLI), "indexed-frontier"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONPATH=str(ROOT / "scripts")),
    )
    assert completed.returncode != 0
    assert "--scope" in completed.stderr and "--query" in completed.stderr


def test_cli_graph_command_keeps_legacy_shape(tmp_path):
    store = tmp_path / "memory.jsonl"
    _write_store(store, [_record(1)])
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--store",
            str(store),
            "graph",
            "--scope",
            "project/frontier",
            "--query",
            "needle",
            "--max-nodes",
            "1",
            "--max-edges",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONPATH=str(ROOT / "scripts")),
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["node_count"] == 1
    assert payload["source_of_truth"].startswith("append-only")


def test_mcp_indexed_frontier_exposes_caps_and_uses_fresh_runtime(monkeypatch, tmp_path):
    class FakeFastMCP:
        instances: list["FakeFastMCP"] = []

        def __init__(self, *args, **kwargs):
            del args, kwargs
            self.tools: list[object] = []
            self.__class__.instances.append(self)

        def tool(self):
            return lambda function: (self.tools.append(function), function)[1]

    fake_mcp = types.ModuleType("mcp")
    fake_server = types.ModuleType("mcp.server")
    fake_fastmcp = types.ModuleType("mcp.server.fastmcp")
    fake_fastmcp.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", fake_mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", fake_server)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fake_fastmcp)

    module = importlib.import_module("memory_fabric_mcp")
    module = importlib.reload(module)
    frontier_tool = next(
        function
        for function in FakeFastMCP.instances[-1].tools
        if function.__name__ == "memory_fabric_indexed_frontier"
    )
    calls: dict[str, object] = {}

    def fake_call_fresh(
        module_name: str, attr: str, *args: object, **kwargs: object
    ) -> dict[str, object]:
        calls.update(module_name=module_name, attr=attr, args=args, kwargs=kwargs)
        return {"ok": True, "limits": {"max_depth": kwargs["max_depth"]}}

    monkeypatch.setattr(module, "call_fresh", fake_call_fresh)
    payload = json.loads(
        frontier_tool(
            scope="project/frontier",
            query="needle",
            max_depth=1,
            max_nodes=2,
            max_edges=3,
            max_paths=2,
            token_budget=100,
            store=str(tmp_path / "memory.jsonl"),
        )
    )
    assert payload == {"ok": True, "limits": {"max_depth": 1}}
    assert calls["module_name"] == "sips_runtime.memory_frontier"
    assert calls["attr"] == "query_frontier"
    assert calls["kwargs"]["scope"] == "project/frontier"
    assert calls["kwargs"]["query"] == "needle"
    assert calls["kwargs"]["max_nodes"] == 2
    assert calls["kwargs"]["max_edges"] == 3
    assert calls["kwargs"]["max_paths"] == 2
    assert calls["kwargs"]["token_budget"] == 100


def test_compatibility_graph_keeps_default_trusted_frontier_and_enforces_filters(tmp_path):
    trusted = _record(1)
    low_confidence = deepcopy(trusted)
    low_confidence["id"] = "mem_low_confidence"
    low_confidence["confidence"] = "low"
    context_only = deepcopy(trusted)
    context_only["id"] = "mem_context_only"
    context_only["provenance"] = {
        "type": "live_ui",
        "evidence_path": "evidence/ui.png",
    }
    needs_verification = deepcopy(trusted)
    needs_verification["id"] = "mem_verify"
    needs_verification["verify_before_use"] = True
    store = tmp_path / "memory.jsonl"
    _write_store(store, [trusted, low_confidence, context_only, needs_verification])

    default = compatibility_graph(
        scope="project/frontier",
        query="needle",
        path=store,
        max_nodes=24,
        max_edges=80,
    )
    assert default["selected_ids"] == [trusted["id"]]
    assert default["compatibility"]["applied_filters"]["all_filters_enforced"] is True

    by_confidence = compatibility_graph(
        scope="project/frontier",
        query="needle",
        confidence="low",
        path=store,
    )
    assert by_confidence["selected_ids"] == [low_confidence["id"]]

    by_provenance = compatibility_graph(
        scope="project/frontier",
        query="needle",
        provenance_type="live_ui",
        path=store,
    )
    assert by_provenance["selected_ids"] == [context_only["id"]]

    by_verify = compatibility_graph(
        scope="project/frontier",
        query="needle",
        verify_before_use="true",
        path=store,
    )
    assert by_verify["selected_ids"] == [needs_verification["id"]]
    assert by_verify["compatibility"]["applied_filters"]["verify_before_use"] is True

    # Post-filtering must not leave topology pointing at records removed by a
    # compatibility filter.
    allowed = set(by_provenance["selected_ids"])
    assert all(
        edge["source"] in allowed and edge["target"] in allowed
        for edge in by_provenance["edges"]
    )


def test_compatibility_filters_apply_before_seed_limit(tmp_path):
    records = []
    for number in range(1, 10):
        item = _record(number)
        item["confidence"] = "high"
        records.append(item)
    target = _record(0)
    target["confidence"] = "low"
    target["created_at"] = "2025-01-01T00:00:00+00:00"
    records.append(target)
    store = tmp_path / "memory.jsonl"
    _write_store(store, records)

    result = compatibility_graph(
        scope="project/frontier",
        query="needle",
        confidence="low",
        seed_limit=8,
        max_depth=0,
        path=store,
    )

    assert result["status"] == "ready"
    assert result["selected_ids"] == [target["id"]]
    assert result["compatibility"]["applied_filters"]["all_filters_enforced"] is True


def test_compatibility_filter_cannot_resurrect_superseded_record(tmp_path):
    superseded = _record(1)
    superseded["confidence"] = "low"
    superseder = _record(2)
    superseder["confidence"] = "high"
    superseder["body"] = f"Replacement supersedes: {superseded['id']}"
    store = tmp_path / "memory.jsonl"
    _write_store(store, [superseded, superseder])

    result = compatibility_graph(
        scope="project/frontier",
        query="needle",
        confidence="low",
        path=store,
    )

    assert result["status"] == "empty"
    assert result["selected_ids"] == []


@pytest.mark.parametrize("value", ["maybe", "TRUE-ish", "2"])
def test_compatibility_graph_rejects_invalid_verify_filter(tmp_path, value):
    with pytest.raises(ValueError, match="verify_before_use expects true/false"):
        compatibility_graph(
            scope="project/frontier",
            query="needle",
            verify_before_use=value,
            path=tmp_path / "memory.jsonl",
        )


@pytest.mark.parametrize("value", ["candidate", "superseded", "archived"])
def test_compatibility_graph_rejects_unsupported_status(tmp_path, value):
    with pytest.raises(ValueError, match="supports status=active only"):
        compatibility_graph(
            scope="project/frontier",
            query="needle",
            status=value,
            path=tmp_path / "memory.jsonl",
        )
