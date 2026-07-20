from __future__ import annotations
from typing import Any


def live_freshness_summary(
    release_version: str,
    current_live: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    if not behavior.get("checked"):
        return {
            "ok": None,
            "status": "live_freshness_unchecked",
            "tool_exposure_ok": current_live.get("ok"),
            "version_fresh": False,
        }
    current_versions = collect_versions(behavior, "current_live_plugin_version")
    expected_versions = collect_versions(behavior, "expected_plugin_version")
    if release_version and release_version not in expected_versions:
        expected_versions.append(release_version)
    version_fresh = bool(release_version and release_version in current_versions)
    behavior_stale = behavior.get("ok") is False
    tool_exposure_ok = current_live.get("ok") is True
    mixed = behavior_stale and (tool_exposure_ok or version_fresh)
    return {
        "ok": not mixed,
        "status": "mixed_live_freshness_stale_behavior" if mixed else "live_freshness_consistent",
        "tool_exposure_ok": tool_exposure_ok,
        "version_fresh": version_fresh,
        "expected_plugin_versions": expected_versions,
        "current_live_plugin_versions": current_versions,
        "stale_behaviors": behavior.get("stale_behaviors", []),
        "missing_current_live_fields": behavior.get("missing_current_live_fields", []),
        "mismatched_current_live_fields": behavior.get("mismatched_current_live_fields", []),
    }


def collect_versions(behavior: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    if behavior.get(key):
        values.append(str(behavior[key]))
    for receipt in behavior.get("receipts", []):
        value = receipt.get(key)
        if value:
            text = str(value)
            if text not in values:
                values.append(text)
    return values
