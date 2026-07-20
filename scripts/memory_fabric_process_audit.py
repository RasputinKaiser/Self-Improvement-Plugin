from __future__ import annotations
import subprocess
from pathlib import Path

from memory_fabric_process_lifecycle import process_lifecycle, process_state


def process_audit(root: Path, lines=None) -> dict:
    script = root / "scripts" / "memory_fabric.py"
    candidates = process_candidates(script, lines if lines is not None else ps_lines())
    pids = [int(candidate["pid"]) for candidate in candidates]
    report = {
        "status": "duplicate_live_servers" if len(pids) > 1 else "clear",
        "state": process_state(len(pids)),
        "count": len(pids),
        "pids": pids[:8],
        "candidates": candidates[:8],
        "candidate_limit": 8,
        "candidate_truncated": len(candidates) > 8,
        "active_transport_proved": len(pids) == 1,
        "lineage_status": process_lineage_status(len(pids)),
        "lifecycle": process_lifecycle(len(pids)),
    }
    if len(pids) != 1:
        report["transport_hint"] = "no_process" if not pids else "duplicate"
    return report


def process_candidates(script: Path, lines) -> list[dict]:
    candidates = []
    for index, line in enumerate(lines):
        parsed = parse_process_line(line, index)
        if parsed and process_matches_script(parsed, script):
            candidates.append(parsed)
    return candidates


def process_matches_script(process: dict, script: Path) -> bool:
    command = str(process.get("command", ""))
    return str(script) in command and "serve" in command


def parse_process_line(line: str, index: int) -> dict | None:
    text = line.strip()
    if not text:
        return None
    parts = text.split(None, 1)
    if not parts or not parts[0].isdigit():
        return None
    return {
        "pid": int(parts[0]),
        "command": parts[1] if len(parts) > 1 else "",
        "line_index": index,
    }


def process_lineage_status(count: int) -> str:
    if count == 0:
        return "no_live_server_process"
    if count == 1:
        return "single_candidate_transport"
    return "duplicate_transport_ambiguous"


def ps_lines():
    try:
        return subprocess.check_output(
            ["ps", "-axo", "pid,command"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=1,
        ).splitlines()[1:]
    except Exception:
        return []
