from __future__ import annotations
import importlib
import sys
from typing import Any, Callable


RELOAD_CONTRACT_VERSION = "mcp_runtime_reload.v2"
CLAIM_BOUNDARY = (
    "MCP runtime reload refreshes in-process Memory Fabric modules before dispatch when source drift is "
    "detected and exposes the last reload receipt; current-live proof still requires calling the live MCP "
    "tool and inspecting its response."
)
LAST_RELOAD_RECEIPT: dict[str, Any] = {
    "ok": None,
    "status": "not_observed",
    "contract_version": RELOAD_CONTRACT_VERSION,
    "reload_attempted": False,
    "before_status": "",
    "after_status": "",
    "before_stale_modules": [],
    "after_stale_modules": [],
    "reloaded_module_count": 0,
    "reloaded_modules": [],
    "claim_boundary": CLAIM_BOUNDARY,
}


def fresh_callable(module_name: str, attr: str) -> tuple[Callable[..., Any], dict[str, Any]]:
    receipt = reload_memory_fabric_modules_if_stale()
    module = importlib.import_module(module_name)
    return getattr(module, attr), receipt


def last_reload_receipt() -> dict[str, Any]:
    return dict(LAST_RELOAD_RECEIPT)


def reload_memory_fabric_modules_if_stale() -> dict[str, Any]:
    global LAST_RELOAD_RECEIPT
    runtime_module = importlib.import_module("memory_fabric_runtime_fingerprint")
    before = runtime_module.runtime_fingerprint()
    if before.get("ok"):
        LAST_RELOAD_RECEIPT = reload_receipt(
            before=before,
            after=before,
            reloaded_modules=[],
            reload_attempted=False,
        )
        return LAST_RELOAD_RECEIPT

    reloaded_modules: list[str] = []
    order_module = importlib.import_module("memory_fabric_mcp_reload_order")
    order_module = importlib.reload(order_module)
    for module_name in order_module.reload_order(runtime_module):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        importlib.reload(module)
        reloaded_modules.append(module_name)

    refreshed_runtime_module = importlib.import_module("memory_fabric_runtime_fingerprint")
    if hasattr(refreshed_runtime_module, "refresh_import_time_fingerprints"):
        refreshed_runtime_module.refresh_import_time_fingerprints()
    after = refreshed_runtime_module.runtime_fingerprint()
    LAST_RELOAD_RECEIPT = reload_receipt(
        before=before,
        after=after,
        reloaded_modules=reloaded_modules,
        reload_attempted=True,
    )
    return LAST_RELOAD_RECEIPT


def reload_receipt(
    before: dict[str, Any],
    after: dict[str, Any],
    reloaded_modules: list[str],
    reload_attempted: bool,
) -> dict[str, Any]:
    return {
        "ok": bool(after.get("ok")),
        "status": "runtime_imports_ready" if after.get("ok") else "runtime_imports_stale",
        "contract_version": RELOAD_CONTRACT_VERSION,
        "reload_attempted": reload_attempted,
        "before_status": before.get("status", ""),
        "after_status": after.get("status", ""),
        "before_stale_modules": before.get("stale_modules", []),
        "after_stale_modules": after.get("stale_modules", []),
        "reloaded_module_count": len(reloaded_modules),
        "reloaded_modules": reloaded_modules,
        "claim_boundary": CLAIM_BOUNDARY,
    }
