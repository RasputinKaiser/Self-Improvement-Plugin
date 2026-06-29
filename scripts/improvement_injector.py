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
EVAL_RESULTS_PATH = Path.home() / ".ncode" / "eval" / "results.jsonl"
MAX_AGE_DAYS = 14
MAX_LINES = 12
EVAL_STALE_SECONDS = 7 * 86400


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


def latest_eval_summary():
    """One-line eval brief from ~/.ncode/eval/results.jsonl.

    Returns None if no runs in the last EVAL_STALE_SECONDS or on any error.
    Format: "Last eval: 12/15 cases passed. Regressed: qual-x (0.4→0.9)."
    """
    if not EVAL_RESULTS_PATH.exists():
        return None
    try:
        with open(EVAL_RESULTS_PATH, encoding="utf-8") as fp:
            lines = [ln.strip() for ln in fp if ln.strip()]
    except OSError:
        return None

    now = datetime.now(timezone.utc).timestamp()
    runs_by_case = {}
    latest_ts = 0.0
    for line in lines:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ft = r.get("finishedAtISO", "")
        try:
            ts = datetime.fromisoformat(ft.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            continue
        if now - ts > EVAL_STALE_SECONDS:
            continue
        cid = r.get("caseId", "")
        if not cid:
            continue
        runs_by_case.setdefault(cid, []).append((ts, r))
        latest_ts = max(latest_ts, ts)

    if not runs_by_case:
        return None

    # Use the latest run per case
    latest_runs = []
    for cid, runs in runs_by_case.items():
        runs.sort(key=lambda x: x[0])
        latest_runs.append(runs[-1][1])

    total = len(latest_runs)
    passed = sum(1 for r in latest_runs if r.get("passed"))

    # Detect regressions: latest score < (median - 0.2)
    regressed = []
    for cid, runs in runs_by_case.items():
        if len(runs) < 4:
            continue
        history = [r for _, r in runs[:-1] if not r.get("errorMessage")]
        if len(history) < 3:
            continue
        scores = sorted(float(r.get("score") or 0.0) for r in history)
        mid = len(scores) // 2
        baseline = scores[mid] if len(scores) % 2 == 1 else (scores[mid-1] + scores[mid]) / 2
        latest_score = float(runs[-1][1].get("score") or 0.0)
        if latest_score < baseline - 0.2:
            regressed.append(f"{cid} ({latest_score:.2f}→{baseline:.2f})")

    brief = f"Last eval: {passed}/{total} cases passed."
    if regressed:
        brief += f" Regressed: {', '.join(regressed[:3])}."
    return brief


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    parts = []

    entry, age_days = latest_entry()
    if entry:
        summary = "\n".join(entry.split("\n")[:MAX_LINES])
        parts.append(
            f"improvements.md: latest self-correction (age {int(age_days)}d). "
            f"Open items — act via /improve:\n{summary}"
        )

    eval_brief = latest_eval_summary()
    if eval_brief:
        parts.append(f"eval: {eval_brief}")

    if parts:
        emit("\n\n".join(parts))


if __name__ == "__main__":
    main()
    sys.exit(0)
