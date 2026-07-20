from __future__ import annotations
def host_advertisement_stale_attention(current_live):
    if not stdio_complete_for_missing_tools(current_live):
        return {}
    return {
        "code": "current_host_advertisement_stale",
        "blocking": True,
        "message": "Stdio server exposes required tools, but the current Codex host does not advertise them.",
        "missing_tools": current_live.get("missing_tools", []),
        "stdio_status": current_live.get("stdio_status", ""),
        "stdio_tool_count": current_live.get("stdio_tool_count", 0),
        "next_check": (
            "Reconnect or restart the Codex host/plugin surface, then rerun schema, "
            "doctor, behavior, and release receipts."
        ),
    }


def stdio_complete_for_missing_tools(current_live):
    return all(
        (
            current_live.get("stdio_checked"),
            current_live.get("stdio_ok") is True,
            current_live.get("stdio_status") == "stdio_tools_complete",
            not current_live.get("stdio_missing_tools"),
        )
    )
