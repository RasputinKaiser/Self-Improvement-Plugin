from __future__ import annotations
from typing import Any

from memory_fabric_frontier_common import gate


def live_gate(release: dict[str, Any], schema: dict[str, Any], required: bool) -> dict[str, Any]:
    schema_fingerprint = schema.get("runtime_fingerprint", {}) if schema else {}
    release_live = release.get("current_live", {}) if release else {}
    release_behavior = release.get("current_live_behavior", {}) if release else {}
    release_ready = release_live_ready(release, release_live, release_behavior)
    ok = release_ready if required else True
    return gate(
        ok,
        "live_freshness_ready" if ok else "live_freshness_attention",
        live_summary(ok),
        live_gate_details(required, schema_fingerprint, release, release_live, release_behavior),
    )


def live_summary(ok: bool) -> str:
    if ok:
        return "Current-live behavior is fresh enough for a frontier completion claim."
    return "Current-live runtime/schema remains stale or unproven."


def release_live_ready(
    release: dict[str, Any],
    release_live: dict[str, Any],
    release_behavior: dict[str, Any],
) -> bool:
    behavior_ready = bool(release_behavior.get("checked")) and release_behavior.get("ok") is True
    return bool(release_live.get("ok")) and release.get("status") == "release_ready" and behavior_ready


def live_gate_details(
    required: bool,
    schema_fingerprint: dict[str, Any],
    release: dict[str, Any],
    release_live: dict[str, Any],
    release_behavior: dict[str, Any],
) -> dict[str, Any]:
    return {
        "required": bool(required),
        "schema_runtime_status": schema_fingerprint.get("status", ""),
        "schema_runtime_ok": schema_fingerprint.get("ok"),
        "stale_module_count": schema_fingerprint.get("stale_module_count", 0),
        "release_status": release.get("status", "") if release else "",
        "current_live_ok": release_live.get("ok"),
        "current_live_behavior_checked": release_behavior.get("checked"),
        "current_live_behavior_ok": release_behavior.get("ok"),
    }
