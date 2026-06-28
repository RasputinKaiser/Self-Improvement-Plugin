#!/usr/bin/env python3
"""Memory Fabric thread-brief injector for PreCompact.

Before NCode compacts the conversation, inject a thread-brief so the compacted
context retains durable memory pointers. Advisory-only, non-blocking.

Hook input: {"cwd": "...", "transcript_path": "...", "trigger": "manual|auto"}
Hook output: {"additionalContext": "memory_fabric thread-brief:\n..."}
"""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)
MAX_TOTAL_CHARS = 2000


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def emit(context):
    sys.stdout.write(json.dumps({"additionalContext": context}))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    mf = find_cli()
    if not mf:
        return

    cwd = payload.get("cwd") or os.getcwd()

    try:
        r = subprocess.run(
            ["python3", mf, "thread-brief",
             "--scope", cwd,
             "--max-total-chars", str(MAX_TOTAL_CHARS)],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return
        data = json.loads(r.stdout) if r.stdout.strip() else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return

    counts = data.get("counts") or {}
    total = sum(counts.values()) if counts else 0
    if total == 0:
        return

    lines = [f"memory_fabric thread-brief ({total} records in scope={cwd}):"]
    for tier, n in counts.items():
        if n:
            lines.append(f"  {tier}: {n}")

    claim_boundary = data.get("claim_boundary")
    if claim_boundary:
        lines.append(f"(claim_boundary: {claim_boundary})")

    text = "\n".join(lines)
    if len(text) > MAX_TOTAL_CHARS:
        text = text[:MAX_TOTAL_CHARS] + "\n...(truncated)"
    emit(text)


if __name__ == "__main__":
    main()
    sys.exit(0)