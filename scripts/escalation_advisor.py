#!/usr/bin/env python3
"""Escalation advisor — PostToolUse hook (Edit|Write|MultiEdit).

Detects when the main thread is "stuck" on a scope from LIVE signals and
surfaces a `decisionFeedback` nudge suggesting /escalate. It does NOT escalate
on its own — escalation is a per-subtask delegation, so the human/agent must
confirm it. The trigger is deterministic Python, so you never spend a model
call to decide whether to delegate.

Stuck signals (any one, scoped to the file just edited):
  - 2+ failure-tagged Memory Fabric records on the same scope within the last
    24h, OR
  - a self_correct sweep in the last 7d named this file as a failure topic.

The suggested delegation runs on the SAME model (the escalate agent is
`model: inherit`) — the win is a fresh, bounded context window with minimal
tools and a forced LESSON line, not a model swap.

Advisory-only, non-blocking, silent on failure.

Hook input:
  {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {...}, ...}
Hook output:
  {"decisionFeedback": {"classification": "stuck", "tips": [...]}}  or {}
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
IMPROVEMENTS_PATH = Path.home() / ".ncode" / "improvements.md"

FAILURE_WINDOW_HOURS = 24


from sips_memory_fabric import find_memory_fabric_cli as find_cli


def emit_feedback(classification, tips):
    sys.stdout.write(json.dumps({
        "decisionFeedback": {"classification": classification, "tips": tips}
    }))
    sys.stdout.flush()


def count_recent_failures(mf, scope):
    try:
        r = subprocess.run(
            ["python3", mf, "search", "--query", "failure mistake broken wrong",
             "--tier", "learning", "--scope", scope, "--limit", "10"],
            capture_output=True, text=True, timeout=8
        )
        if r.returncode != 0 or not r.stdout.strip():
            return 0
        records = json.loads(r.stdout).get("records") or []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return 0
    threshold = datetime.now(timezone.utc) - timedelta(hours=FAILURE_WINDOW_HOURS)
    n = 0
    for rec in records:
        tags = rec.get("tags") or []
        if "failure" not in tags:
            continue
        ts = rec.get("created_at") or rec.get("updated_at") or ""
        try:
            rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if rec_dt >= threshold:
                n += 1
        except (ValueError, TypeError):
            n += 1  # un-dated failure records count conservatively
    return n


def named_in_improvements(scope):
    if not IMPROVEMENTS_PATH.exists():
        return False
    try:
        content = IMPROVEMENTS_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # only the latest self-correction entry matters
    marker = "## Self-correction"
    idx = content.rfind(marker)
    if idx < 0:
        return False
    latest = content[idx:]
    name = os.path.basename(scope)
    return bool(name) and name in latest and "failure" in latest.lower()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        return

    mf = find_cli()
    signals = []

    if mf:
        fails = count_recent_failures(mf, path)
        if fails >= 2:
            signals.append(f"{fails} failure records on this file in the last {FAILURE_WINDOW_HOURS}h")

    if named_in_improvements(path):
        signals.append("the latest self-correction sweep flagged this file as a failure topic")

    if not signals:
        return

    tips = [
        "Main thread appears stuck on this scope: " + "; ".join(signals) + ".",
        "Consider `/escalate <bounded subtask>` — delegates to a fresh, bounded context on the SAME model.",
        "The escalate agent returns a DIFF and a LESSON line; the LESSON gets recorded so this scope recalls it next time.",
        "Do not escalate the whole session — keep delegation to the single stuck subtask.",
    ]
    emit_feedback("stuck-scope", tips)


if __name__ == "__main__":
    main()
    sys.exit(0)
