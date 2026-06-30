from __future__ import annotations
from memory_fabric_mixed_freshness_attention import mixed_freshness_attention
from memory_fabric_release_host_advertisement import host_advertisement_stale_attention
from memory_fabric_release_process_attention import (
    advertised_without_process_attention,
    duplicate_process_attention,
)


def release_attention(
    checks,
    current_live,
    local,
    behavior=None,
    freshness=None,
):
    behavior = behavior or {}
    freshness = freshness or {}
    return [
        item
        for item in [
            plugin_eval_attention(checks),
            truncated_live_surface_attention(current_live),
            missing_live_tools_attention(checks, current_live),
            stale_tool_schema_attention(checks, current_live),
            missing_behavior_attention(checks),
            stale_behavior_attention(checks, behavior),
            mixed_freshness_attention(freshness),
            duplicate_process_attention(local),
            advertised_without_process_attention(checks, local),
        ]
        if item
    ]


def plugin_eval_attention(checks):
    if checks.get("plugin_eval_ok"):
        return {}
    return {
        "code": "plugin_eval_gauge_attention",
        "blocking": False,
        "message": "Plugin Eval below threshold; keep capability and treat as measurement.",
    }


def missing_live_tools_attention(checks, current_live):
    if not all(
        (
            checks.get("current_live_checked"),
            not checks.get("current_live_ok"),
            current_live.get("missing_tools"),
        )
    ):
        return {}
    host_advertisement_attention = host_advertisement_stale_attention(current_live)
    if host_advertisement_attention:
        return host_advertisement_attention
    return {
        "code": "current_live_stale",
        "blocking": True,
        "message": "Current Codex host is stale or missing live tools.",
        "missing_tools": current_live.get("missing_tools", []),
    }


def truncated_live_surface_attention(current_live):
    if current_live.get("status") != "surface_truncated_unproven":
        return {}
    return {
        "code": "current_live_surface_truncated_unproven",
        "blocking": False,
        "message": "Current live discovery was capped; absent tools are unproven.",
        "advertised_count": current_live.get("advertised_count", 0),
        "unverified_tools": current_live.get("unverified_tools", []),
        "next_check": "Query suspected missing tools directly or provide a complete advertised surface.",
    }


def stale_tool_schema_attention(checks, current_live):
    if not all(
        (
            checks.get("current_live_checked"),
            current_live.get("status") == "stale_tool_schema",
        )
    ):
        return {}
    return {
        "code": "current_live_tool_schema_stale",
        "blocking": True,
        "message": "Current Codex host exposes tools with stale input schemas.",
        "missing_params": current_live.get("missing_params", {}),
        "unchecked_tools": current_live.get("unchecked_tools", []),
    }


def stale_behavior_attention(checks, behavior):
    if not all((checks.get("current_live_behavior_checked"), not checks.get("current_live_behavior_ok"))):
        return {}
    return {
        "code": "current_live_behavior_stale",
        "blocking": True,
        "message": "Current live tools are exposed but behavior receipts are stale.",
        "stale_behaviors": behavior.get("stale_behaviors", []),
        "missing_current_live_fields": behavior.get("missing_current_live_fields", []),
        "mismatched_current_live_fields": behavior.get("mismatched_current_live_fields", []),
    }


def missing_behavior_attention(checks):
    if not all(
        (
            checks.get("current_live_behavior_required"),
            not checks.get("current_live_behavior_checked"),
        )
    ):
        return {}
    return {
        "code": "current_live_behavior_missing",
        "blocking": True,
        "message": "Strict release requires a current-live behavior receipt.",
    }

