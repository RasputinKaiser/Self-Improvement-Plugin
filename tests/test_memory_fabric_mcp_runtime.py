from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import memory_fabric_mcp_reload_order as reload_order
import memory_fabric_mcp_runtime as runtime


def test_reload_order_pins_runtime_foundations_and_mcp_edges(monkeypatch):
    watched = [
        "memory_fabric_cycle_alpha.py",
        "memory_fabric_mcp.py",
        "memory_fabric_schema.py",
        "memory_fabric_runtime_fingerprint.py",
        "memory_fabric_mcp_runtime.py",
    ]
    for name in [path.removesuffix(".py") for path in watched]:
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setattr(
        reload_order,
        "unwatched_memory_modules",
        lambda _watched: ["memory_fabric_cycle_extra"],
    )

    order = reload_order.reload_order(SimpleNamespace(WATCHED_MODULES=watched))

    assert order == [
        "memory_fabric_runtime_fingerprint",
        "memory_fabric_schema",
        "memory_fabric_cycle_extra",
        "memory_fabric_cycle_alpha",
        "memory_fabric_mcp",
    ]
    assert "memory_fabric_mcp_runtime" not in order


def test_reload_receipt_preserves_stale_to_ready_proof(monkeypatch):
    states = iter(
        [
            {"ok": False, "status": "runtime_imports_stale", "stale_modules": ["memory_fabric_schema"]},
            {"ok": True, "status": "runtime_imports_match_source", "stale_modules": []},
        ]
    )
    fingerprint = SimpleNamespace(
        runtime_fingerprint=lambda: next(states),
        refresh_import_time_fingerprints=lambda: None,
    )
    ordering = SimpleNamespace(reload_order=lambda _runtime: [])

    def import_module(name: str):
        if name == "memory_fabric_runtime_fingerprint":
            return fingerprint
        if name == "memory_fabric_mcp_reload_order":
            return ordering
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(runtime.importlib, "import_module", import_module)
    monkeypatch.setattr(runtime.importlib, "reload", lambda module: module)

    receipt = runtime.reload_memory_fabric_modules_if_stale()

    assert receipt["ok"] is True
    assert receipt["status"] == "runtime_imports_ready"
    assert receipt["reload_attempted"] is True
    assert receipt["before_stale_modules"] == ["memory_fabric_schema"]
    assert receipt["after_stale_modules"] == []
    assert receipt["reloaded_module_count"] == 0
    assert "current-live proof" in receipt["claim_boundary"]
