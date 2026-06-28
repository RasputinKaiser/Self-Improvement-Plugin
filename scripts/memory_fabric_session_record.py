#!/usr/bin/env python3
"""Memory Fabric session recorder for PostCompact.

After NCode compacts the conversation, record a work-tier memory capturing the
session's shipped artifacts. Evidence path points to the transcript.

Advisory-only, non-blocking, silent on any failure.

Hook input: {"cwd": "...", "transcript_path": "...", "trigger": "manual|auto"}
Writes a JSON record to the Memory Fabric store. Idempotent per session_id.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    mf = find_cli()
    if not mf:
        return

    cwd = payload.get("cwd") or os.getcwd()
    transcript = payload.get("transcript_path") or ""
    session_id = payload.get("session_id") or ""

    if not transcript or not os.path.exists(transcript):
        return

    try:
        stat = os.stat(transcript)
        size_kb = stat.st_size // 1024
    except OSError:
        size_kb = 0

    title = f"Session {session_id[:8]} compacted — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    body = (
        f"Context compaction triggered for cwd={cwd}. "
        f"Transcript size: {size_kb}KB at {transcript}. "
        f"Subject: NCode harness self-improvement session. "
        f"Verify transcript for shipped artifacts — scripts, hooks, and patches."
    )

    try:
        r = subprocess.run(
            ["python3", mf, "record",
             "--tier", "work",
             "--title", title,
             "--body", body,
             "--scope", cwd,
             "--tags", "session,compact,harness",
             "--provenance-type", "source_backed_agent_run",
             "--provenance", f"transcript={transcript}",
             "--evidence-path", transcript,
             "--confidence", "medium",
             "--status", "active"],
            capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, OSError):
        return


if __name__ == "__main__":
    main()
    sys.exit(0)