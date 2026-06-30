from __future__ import annotations
def mixed_freshness_attention(freshness):
    if freshness.get("status") != "mixed_live_freshness_stale_behavior":
        return {}
    return {
        "code": "current_live_mixed_freshness",
        "blocking": True,
        "message": "Current live version or tools look fresh while behavior receipts are stale.",
        "tool_exposure_ok": freshness.get("tool_exposure_ok"),
        "version_fresh": freshness.get("version_fresh"),
        "current_live_plugin_versions": freshness.get("current_live_plugin_versions", []),
        "expected_plugin_versions": freshness.get("expected_plugin_versions", []),
        "stale_behaviors": freshness.get("stale_behaviors", []),
        "missing_current_live_fields": freshness.get("missing_current_live_fields", []),
        "mismatched_current_live_fields": freshness.get("mismatched_current_live_fields", []),
    }
