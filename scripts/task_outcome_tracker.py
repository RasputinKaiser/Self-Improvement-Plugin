#!/usr/bin/env python3
"""Task outcome tracker.

Records structured outcomes after tasks complete: tool call count, attempts,
duration, success/failure. Pairs with agent_patterns.py to aggregate trends.

Two modes:
  --record: read session activity from stdin JSON, write a learning-tier record
  --query: print recent outcomes as JSON for aggregation

Advisory-only, silent on failure.
"""
import json
import os
import re
import subprocess
import sys
import worktree_scope
from datetime import datetime, timezone
from pathlib import Path


from sips_memory_fabric import find_memory_fabric_cli as find_cli


def extract_outcome(transcript_path):
    """Parse transcript JSONL to extract outcome metrics."""
    tool_calls = 0
    edits = 0
    bash_runs = 0
    attempts = 0
    failures = 0
    files_changed = set()
    final_user_prompt = ""
    started_at = None
    ended_at = None

    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        size = os.path.getsize(transcript_path)
        if size > 5 * 1024 * 1024:
            return None
    except OSError:
        return None

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

                ts = entry.get("timestamp")
                if ts:
                    if not started_at:
                        started_at = ts
                    ended_at = ts

                data = entry.get("data") or entry
                role = data.get("role") or entry.get("type", "")

                if role == "user":
                    content = data.get("content", "")
                    if isinstance(content, str) and content and not content.startswith("<"):
                        if not content.startswith("{") and "tool_use_id" not in content:
                            final_user_prompt = content[:300]
                            attempts += 1

                tool_uses = data.get("toolUses") or []
                if isinstance(tool_uses, list):
                    for tu in tool_uses:
                        name = tu.get("name", "")
                        if name:
                            tool_calls += 1
                        if name in ("Edit", "Write", "MultiEdit"):
                            edits += 1
                            fp = tu.get("input", {}).get("file_path") or tu.get("input", {}).get("path") or ""
                            if fp:
                                files_changed.add(fp)
                        elif name == "Bash":
                            bash_runs += 1

                err = data.get("isApiErrorMessage") or ""
                if err and isinstance(err, str) and err.lower() not in ("false", ""):
                    failures += 1
                elif isinstance(data, dict) and data.get("type") == "error":
                    failures += 1
    except (OSError, IOError):
        return None

    if not final_user_prompt and tool_calls == 0:
        return None

    return {
        "tool_calls": tool_calls,
        "edits": edits,
        "bash_runs": bash_runs,
        "attempts": attempts,
        "failures": failures,
        "files_changed": sorted(files_changed),
        "final_prompt": final_user_prompt,
        "started_at": started_at,
        "ended_at": ended_at,
    }


def record_outcome(transcript_path, session_id, cwd):
    outcome = extract_outcome(transcript_path)
    if not outcome:
        return None

    # Derive success/failure signal
    success = outcome["failures"] == 0 and outcome["edits"] > 0

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = f"Outcome {session_id[:8]} — {'OK' if success else 'FAIL'} ({outcome['tool_calls']} calls, {outcome['edits']} edits)"

    body_parts = [
        f"session: {session_id}",
        f"cwd: {cwd}",
        f"started: {outcome['started_at']}",
        f"ended: {outcome['ended_at']}",
        f"success: {success}",
        f"tool_calls: {outcome['tool_calls']}",
        f"edits: {outcome['edits']}",
        f"bash_runs: {outcome['bash_runs']}",
        f"attempts: {outcome['attempts']}",
        f"failures: {outcome['failures']}",
        f"files_changed: {len(outcome['files_changed'])}",
    ]
    if outcome["final_prompt"]:
        body_parts.append(f"objective: {outcome['final_prompt']}")
    if outcome["files_changed"]:
        body_parts.append("files:")
        for fp in outcome["files_changed"][:5]:
            body_parts.append(f"  - {fp}")

    body = "\n".join(body_parts)
    mf = find_cli()
    if not mf:
        return None

    tags = "outcome,task-metrics," + ("success" if success else "failure")
    try:
        r = subprocess.run(
            ["python3", mf, "record",
             "--tier", "learning",
             "--title", title,
             "--body", body,
             "--scope", cwd,
             "--tags", tags,
             "--provenance-type", "source_backed_agent_run",
             "--provenance", f"transcript={transcript_path}; session_id={session_id}",
             "--evidence-path", transcript_path,
             "--confidence", "high" if success else "medium",
             "--status", "active"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            return d.get("record", {}).get("id")
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Task outcome tracker")
    ap.add_argument("--record", action="store_true",
                    help="record outcome from JSON on stdin")
    ap.add_argument("--query", action="store_true",
                    help="print recent outcome records as JSON")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    if args.query:
        mf = find_cli()
        if not mf:
            print("[]")
            return
        r = subprocess.run(
            ["python3", mf, "search",
             "--query", "outcome task-metrics",
             "--tier", "learning",
             "--limit", str(args.limit)],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            print(json.dumps(d.get("records", []), indent=2))
        return

    if args.record:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            return
        transcript = payload.get("transcript_path", "")
        session_id = payload.get("session_id", "unknown")
        cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())
        record_outcome(transcript, session_id, cwd)


if __name__ == "__main__":
    main()
    sys.exit(0)