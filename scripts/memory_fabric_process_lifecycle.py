from __future__ import annotations
SAFE_ACTIONS = {
    "absent": (
        "Reconnect or restart the Codex host/plugin surface so it owns a fresh "
        "Memory Fabric MCP stdio transport."
    ),
    "single": (
        "Leave host-owned stdio alone; verify schema/brief/graph/report receipts."
    ),
    "duplicate": (
        "Do not kill duplicate stdio MCP PIDs by age; active transport is not "
        "proved by start time. Prefer host/plugin reconnect."
    ),
}


def process_state(count: int) -> str:
    if count == 0:
        return "absent"
    if count == 1:
        return "single"
    return "duplicate"


def process_lifecycle(count: int) -> dict[str, object]:
    state = process_state(count)
    return {
        "state": state,
        "host_owned": True,
        "manual_pid_cleanup_safe": False,
        "safety_rule": "Never infer the active Codex MCP stdio transport from PID age/count.",
        "next_safe_action": SAFE_ACTIONS[state],
    }
