#!/usr/bin/env python3
from __future__ import annotations
"""Memory Fabric doctor + recent-work surfacing — SessionStart hook.

Does two things:
1. Read-only integrity check of the Memory Fabric store (silent on clean,
   surfaces issues as additionalContext when broken).
2. Pulls the 3 most recent work-tier records and injects them as
   additionalContext so the agent starts each session knowing what was done
   recently. Solves the cold-start problem.

Advisory-only, non-blocking, silent on failure.

Hook input: {"hook_event_name": "SessionStart", "cwd": "...", ...}
Hook output:
  {} on clean + no recent work
  {"additionalContext": "..."} on issues or recent work
"""
import json
import os
import subprocess
import sys
import worktree_scope
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import improvements_path

IMPROVEMENTS_PATH = improvements_path()
MAX_WORK_RECORDS = 3
MAX_CHARS = 1800
IMPROVEMENTS_MAX_AGE_DAYS = 14


from sips_memory_fabric import find_memory_fabric_cli as find_cli


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

    cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())

    # 1. Doctor check
    doctor_issues = []
    try:
        r = subprocess.run(
            ["python3", mf, "doctor"],
            capture_output=True, text=True, timeout=8
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            issues = data.get("issues") or data.get("errors") or []
            store_ok = data.get("ok", True)
            if not store_ok or issues:
                doctor_issues = issues[:3]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass

    # 2. Recent work records
    recent_work = []
    try:
        r = subprocess.run(
            ["python3", mf, "search",
             "--query", "session work compact close",
             "--tier", "work",
             "--scope", cwd,
             "--limit", str(MAX_WORK_RECORDS)],
            capture_output=True, text=True, timeout=8
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            recent_work = data.get("records") or []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass

    # Build output
    lines = []
    if doctor_issues:
        lines.append("memory_fabric doctor: store has issues — verify before relying on records.")
        for issue in doctor_issues:
            if isinstance(issue, dict):
                lines.append(f"- {issue.get('severity','?')}: {issue.get('message','?')}")
            else:
                lines.append(f"- {issue}")
        lines.append("")

    if recent_work:
        lines.append(f"memory_fabric: {len(recent_work)} most recent work records (advisory).")
        for rec in recent_work:
            title = rec.get("title", "")
            body = (rec.get("body") or "").strip().replace("\n", " ")[:200]
            ts = rec.get("created_at") or rec.get("updated_at") or ""
            if ts:
                ts = ts[:16]
            lines.append(f"- [{ts}] {title}")
            if body:
                lines.append(f"    {body}")

    # 3. Latest improvements.md entry (from weekly self-correction sweep)
    if IMPROVEMENTS_PATH.exists():
        try:
            mtime = IMPROVEMENTS_PATH.stat().st_mtime
            age_days = (datetime.now(timezone.utc).timestamp() - mtime) / 86400
            if age_days < IMPROVEMENTS_MAX_AGE_DAYS:
                content = IMPROVEMENTS_PATH.read_text(encoding="utf-8", errors="replace")
                # Find the most recent ## Self-correction entry
                marker = "## Self-correction"
                idx = content.rfind(marker)
                if idx >= 0:
                    # Find next ## Self-correction after this one (or EOF)
                    next_idx = content.find(marker, idx + len(marker))
                    latest = content[idx:next_idx].strip() if next_idx > 0 else content[idx:].strip()
                    # Surface first ~10 lines
                    summary_lines = latest.split("\n")[:10]
                    summary = "\n".join(summary_lines)
                    lines.append("")
                    lines.append(f"improvements.md: latest self-correction (age {int(age_days)}d, {IMPROVEMENTS_PATH.relative_to(Path.home())}):")
                    lines.append(summary)
        except (OSError, IOError):
            pass

    if not lines:
        return

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...(truncated)"
    emit(text)


if __name__ == "__main__":
    main()
    sys.exit(0)
