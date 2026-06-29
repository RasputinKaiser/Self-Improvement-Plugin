#!/usr/bin/env python3
"""Session close hook (Stop event).

Fires when the NCode session is about to end. Records a work-tier Memory
Fabric entry summarizing the session's shipped artifacts so future sessions
can find what was done.

Reads transcript JSONL to extract:
- Files created or modified via Edit/Write
- Bash commands run
- Final objective (last user prompt)

Advisory-only, non-blocking, silent on failure.

Hook input:
  {"hook_event_name": "Stop", "cwd": "...", "session_id": "...", "transcript_path": "..."}
"""
import glob
import json
import os
import subprocess
import sys
import worktree_scope
from datetime import datetime, timezone
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)
MAX_FILES = 10
MAX_COMMANDS = 5
MAX_TRANSCRIPT_SIZE = 5 * 1024 * 1024  # 5MB


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def extract_session_activity(transcript_path):
    """Parse transcript JSONL for shipped artifacts."""
    files_changed = set()
    commands = []
    last_prompt = ""

    if not transcript_path or not os.path.exists(transcript_path):
        return files_changed, commands, last_prompt

    try:
        size = os.path.getsize(transcript_path)
        if size > MAX_TRANSCRIPT_SIZE:
            # Too large to parse safely — just record the path
            return files_changed, commands, last_prompt
    except OSError:
        return files_changed, commands, last_prompt

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
                        last_prompt = content[:300]

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
                            if cmd and len(commands) < MAX_COMMANDS:
                                commands.append(cmd[:120])
    except (OSError, IOError):
        pass

    return files_changed, commands, last_prompt


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    mf = find_cli()
    if not mf:
        return

    cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())
    session_id = payload.get("session_id") or "unknown"
    transcript = payload.get("transcript_path", "")

    files_changed, commands, last_prompt = extract_session_activity(transcript)

    if not files_changed and not commands:
        # Nothing to record — empty or read-only session
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = f"Session {session_id[:8]} closed — {ts}"

    parts = [f"cwd: {cwd}"]
    if last_prompt:
        parts.append(f"objective: {last_prompt}")
    if files_changed:
        parts.append(f"files changed ({len(files_changed)}):")
        for fp in sorted(files_changed)[:MAX_FILES]:
            parts.append(f"  - {fp}")
        if len(files_changed) > MAX_FILES:
            parts.append(f"  ...({len(files_changed) - MAX_FILES} more)")
    if commands:
        parts.append(f"recent commands ({len(commands)}):")
        for cmd in commands:
            parts.append(f"  - {cmd}")

    body = "\n".join(parts)

    try:
        subprocess.run(
            ["python3", mf, "record",
             "--tier", "work",
             "--title", title,
             "--body", body,
             "--scope", cwd,
             "--tags", "session,close,artifact-trail",
             "--provenance-type", "source_backed_agent_run",
             "--provenance", f"transcript={transcript}; session_id={session_id}",
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