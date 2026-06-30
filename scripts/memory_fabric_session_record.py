#!/usr/bin/env python3
from __future__ import annotations
"""Memory Fabric session recorder for PostCompact.

After NCode compacts the conversation, record a work-tier memory capturing the
session's shipped artifacts. Evidence path points to the transcript.

Advisory-only, non-blocking, silent on any failure.

Hook input: {"cwd": "...", "transcript_path": "...", "trigger": "manual|auto"}
Writes a JSON record to the Memory Fabric store. Idempotent per session_id.
"""
import hashlib
import json
import os
import subprocess
import sys
import worktree_scope
from datetime import datetime, timezone
from pathlib import Path


from sips_memory_fabric import find_memory_fabric_cli as find_cli


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    mf = find_cli()
    if not mf:
        return

    cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())
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