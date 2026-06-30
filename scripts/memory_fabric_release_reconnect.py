from __future__ import annotations
from memory_fabric_release_host_advertisement import stdio_complete_for_missing_tools


def reconnect_diagnosis(checks, current_live, behavior, local):
    process_state = local.get("processes", {}).get("state", "")
    reason = ""
    if checks.get("current_live_checked") and not checks.get("current_live_ok"):
        reason = missing_live_tools_reason(current_live)
    elif checks.get("current_live_behavior_checked") and not checks.get("current_live_behavior_ok"):
        reason = "live_behavior_stale"
    elif all(
        (
            checks.get("current_live_checked"),
            checks.get("current_live_ok"),
            process_state == "absent",
            not all((checks.get("current_live_behavior_checked"), checks.get("current_live_behavior_ok"))),
        )
    ):
        reason = "no_process_or_fresh_behavior"
    needed = bool(reason)
    return {
        "needed": needed,
        "status": "host_reconnect_required" if needed else "not_required",
        "reason": reason,
        "process_state": process_state,
        "live_status": current_live.get("status", ""),
        "behavior_status": behavior.get("status", ""),
        "post_reconnect_gates": "schema,brief,behavior,report" if needed else "",
    }


def missing_live_tools_reason(current_live):
    if stdio_complete_for_missing_tools(current_live):
        return "host_advertisement_stale_stdio_complete"
    return "live_missing_tools_or_transport_stale"
