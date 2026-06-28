#!/usr/bin/env python3
"""Improvement injector — SessionStart hook (loop closure).

The missing v1 read-back: self_correct.py WRITES ~/.ncode/improvements.md but
nothing reads it back into a session. This hook reads the latest self-correction
entry and injects it as additionalContext at SessionStart so the agent STARTS
knowing the open self-improvement items.

No model-tier logic — v2 has no model routing. The same summary runs on every
model. If the entry is stale (>14d) it is skipped so the context stays signal.

Advisory-only, non-blocking, silent on failure.

Hook input: {"hook_event_name": "SessionStart", "cwd": "...", ...}
Hook output: {"additionalContext": "..."}  or {}
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

IMPROVEMENTS_PATH = Path.home() / ".ncode" / "improvements.md"
MAX_AGE_DAYS = 14
MAX_LINES = 12


def emit(context):
    sys.stdout.write(json.dumps({"additionalContext": context}))
    sys.stdout.flush()


def latest_entry():
    if not IMPROVEMENTS_PATH.exists():
        return None, None
    try:
        content = IMPROVEMENTS_PATH.read_text(encoding="utf-8", errors="replace")
        mtime = IMPROVEMENTS_PATH.stat().st_mtime
    except OSError:
        return None, None
    age_days = (datetime.now(timezone.utc).timestamp() - mtime) / 86400
    if age_days >= MAX_AGE_DAYS:
        return None, age_days
    marker = "## Self-correction"
    idx = content.rfind(marker)
    if idx < 0:
        return None, age_days
    next_idx = content.find(marker, idx + len(marker))
    entry = content[idx:next_idx].strip() if next_idx > 0 else content[idx:].strip()
    return entry, age_days


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    entry, age_days = latest_entry()
    if not entry:
        return

    summary = "\n".join(entry.split("\n")[:MAX_LINES])
    emit(
        f"improvements.md: latest self-correction (age {int(age_days)}d). "
        f"Open items — act via /improve:\n{summary}"
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
