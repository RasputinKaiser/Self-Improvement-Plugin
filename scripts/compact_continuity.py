#!/usr/bin/env python3
"""Compact continuity packet for PreCompact/PostCompact hooks.

PreCompact: reads recent session activity, writes a structured continuity
packet to ~/.ncode/continuity/<session_id>.md so the compacted context
retains the thread. The packet captures: objective, changed files, evidence
paths, blockers, and the exact next command.

PostCompact: emits the continuity packet as additionalContext so the new
compacted context picks it up.

Advisory-only, non-blocking, silent on failure.

Hook input:
  {"cwd": "...", "session_id": "...", "transcript_path": "...", "trigger": "manual|auto"}
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTINUITY_DIR = Path.home() / ".ncode" / "continuity"
CONTINUITY_DIR.mkdir(parents=True, exist_ok=True)

MAX_RECENT_FILES = 15
MAX_RECENT_COMMANDS = 8


def emit(payload):
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def extract_recent_activity(transcript_path):
    """Parse transcript JSONL for recent file edits and bash commands."""
    files_changed = set()
    recent_commands = []
    last_objective = ""

    if not transcript_path or not os.path.exists(transcript_path):
        return files_changed, recent_commands, last_objective

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                data = entry.get("data") or entry
                role = data.get("role") or entry.get("type", "")

                if role == "user":
                    content = data.get("content", "")
                    if isinstance(content, str) and content and not content.startswith("<"):
                        last_objective = content[:200]

                tool_uses = data.get("toolUses") or []
                if isinstance(tool_uses, list):
                    for tu in tool_uses:
                        name = tu.get("name", "")
                        inp = tu.get("input", {})
                        if name in ("Edit", "Write", "MultiEdit"):
                            fp = inp.get("file_path") or inp.get("path") or ""
                            if fp:
                                files_changed.add(fp)
                        elif name == "Bash":
                            cmd = inp.get("command", "")
                            if cmd and len(recent_commands) < MAX_RECENT_COMMANDS:
                                recent_commands.append(cmd[:150])
    except (OSError, IOError):
        pass

    return files_changed, recent_commands, last_objective


def write_continuity_packet(session_id, cwd, files_changed, recent_commands, objective):
    """Write structured continuity packet to ~/.ncode/continuity/<id>.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    path = CONTINUITY_DIR / f"{session_id}.md"

    lines = [
        f"# Continuity — {session_id[:8]} ({ts})",
        "",
        f"**cwd**: `{cwd}`",
        "",
        "## Objective",
        objective or "(no objective captured — check session log)",
        "",
        f"## Changed files ({len(files_changed)})",
    ]
    for fp in sorted(files_changed)[-MAX_RECENT_FILES:]:
        lines.append(f"- `{fp}`")
    if len(files_changed) > MAX_RECENT_FILES:
        lines.append(f"- ...({len(files_changed) - MAX_RECENT_FILES} more)")

    lines.extend([
        "",
        f"## Recent commands ({len(recent_commands)})",
    ])
    for cmd in recent_commands:
        lines.append(f"- `{cmd}`")

    lines.extend([
        "",
        "## Blockers",
        "(none captured — verify no blockers exist before continuing)",
        "",
        "## Next",
        "Continue the objective. Re-read changed files before edits. Verify before claiming done.",
        "",
    ])

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    return path


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    event = payload.get("hook_event_name", "")
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id") or "unknown"
    transcript = payload.get("transcript_path", "")

    files_changed, recent_commands, objective = extract_recent_activity(transcript)

    if event == "PreCompact":
        path = write_continuity_packet(
            session_id, cwd, files_changed, recent_commands, objective
        )
        return

    if event == "PostCompact":
        path = CONTINUITY_DIR / f"{session_id}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            emit({"additionalContext": f"continuity packet:\n{content}"})
        return


if __name__ == "__main__":
    main()
    sys.exit(0)