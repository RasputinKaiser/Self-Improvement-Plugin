from __future__ import annotations
def duplicate_process_attention(local):
    processes = local.get("processes", {})
    if processes.get("count", 0) <= 1:
        return {}
    lifecycle = processes.get("lifecycle", {})
    return {
        "code": "duplicate_live_server_processes",
        "blocking": False,
        "message": "Duplicate live servers.",
        "count": processes.get("count"),
        "pids": processes.get("pids", []),
        "lineage_status": processes.get("lineage_status", ""),
        "active_transport_proved": processes.get("active_transport_proved", False),
        "candidate_truncated": processes.get("candidate_truncated", False),
        "candidates": processes.get("candidates", []),
        "manual_pid_cleanup_safe": lifecycle.get("manual_pid_cleanup_safe", False),
        "safety_rule": lifecycle.get("safety_rule", ""),
        "next_safe_action": lifecycle.get("next_safe_action", ""),
    }


def advertised_without_process_attention(checks, local):
    processes = local.get("processes", {})
    if not advertised_without_process(checks, processes):
        return {}
    lifecycle = processes.get("lifecycle", {})
    return {
        "code": "advertised_tools_no_process",
        "blocking": False,
        "message": "Live tools advertised but no server; verify or reconnect.",
        "count": 0,
        "manual_pid_cleanup_safe": lifecycle.get("manual_pid_cleanup_safe", False),
        "next_safe_action": lifecycle.get("next_safe_action", ""),
    }


def advertised_without_process(checks, processes):
    return all(
        (
            checks.get("current_live_checked"),
            checks.get("current_live_ok"),
            processes.get("state") == "absent",
        )
    )
