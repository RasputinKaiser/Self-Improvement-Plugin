from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def behavior_receipt(path: str) -> dict[str, Any]:
    if not path:
        return {"ok": None, "status": "behavior_not_supplied", "checked": False}
    data = read_json(path)
    status = data.get("status", "")
    ok = data.get("ok")
    return {
        "ok": (
            status != "current_live_behavior_stale"
            if ok is None
            else bool(ok) and status != "current_live_behavior_stale"
        ),
        "checked": True,
        "status": status,
        "behavior": data.get("behavior", ""),
        "expected_contract_version": data.get("expected_contract_version", ""),
        "current_live_contract_version": data.get("current_live_contract_version", ""),
        "expected_plugin_version": data.get("expected_plugin_version", ""),
        "current_live_plugin_version": data.get("current_live_plugin_version", ""),
        "missing_current_live_fields": data.get("missing_current_live_fields", []),
        "mismatched_current_live_fields": data.get("mismatched_current_live_fields", []),
        "path": path,
    }


def behavior_receipts(path_list: str) -> dict[str, Any]:
    paths = split_paths(path_list)
    if not paths:
        return behavior_receipt("")
    receipts = [behavior_receipt(path) for path in paths]
    stale = [item for item in receipts if item.get("ok") is False]
    first = receipts[0]
    return {
        "ok": not stale,
        "checked": True,
        "status": "current_live_behavior_stale" if stale else "current_live_behavior_ready",
        "behavior": first.get("behavior", ""),
        "expected_contract_version": first.get("expected_contract_version", ""),
        "current_live_contract_version": first.get("current_live_contract_version", ""),
        "expected_plugin_version": first.get("expected_plugin_version", ""),
        "current_live_plugin_version": first.get("current_live_plugin_version", ""),
        "receipt_count": len(receipts),
        "stale_count": len(stale),
        "stale_behaviors": [item.get("behavior", "") for item in stale],
        "missing_current_live_fields": collect_fields(stale, "missing_current_live_fields"),
        "mismatched_current_live_fields": collect_fields(stale, "mismatched_current_live_fields"),
        "receipts": receipts,
        "paths": paths,
    }


def split_paths(value: str) -> list[str]:
    paths: list[str] = []
    for item in value.replace("\n", ",").split(","):
        path = item.strip()
        if path and path not in paths:
            paths.append(path)
    return paths


def collect_fields(receipts: list[dict[str, Any]], key: str) -> list[str]:
    return sorted(
        {
            str(field)
            for receipt in receipts
            for field in receipt.get(key, [])
        }
    )


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
