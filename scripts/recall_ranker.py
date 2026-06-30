#!/usr/bin/env python3
"""Recall ranker — scoped UserPromptSubmit hook.

Replaces the raw memory_fabric_prompt_search at the UserPromptSubmit slot.
Searches Memory Fabric for the user's prompt, scoped to the current working
directory, then RANKS the results so the most actionable lessons surface first:

  1. failure-tagged records (⚠ PRIOR FAILURE) — the single most valuable signal,
     surfaced first with a marker.
  2. success-tagged / high-confidence records (✓ prior success) — prescriptive:
     the last known-good approach.
  3. everything else, most recent first.

Same depth on every model — v2 has no model routing. The harness's versatility
comes from delegation (fresh-context subagents) and forced lesson capture, not
from tuning recall depth per model.

Advisory-only, non-blocking, silent on failure.

Hook input:
  {"hook_event_name": "UserPromptSubmit", "cwd": "...", "prompt": "...", ...}
Hook output:
  {"additionalContext": "scoped recall:\n..."}  or {} on no hits
"""
import json
import os
import re
import subprocess
import sys
import worktree_scope
from datetime import datetime, timezone
from pathlib import Path
LIMIT = 4
MAX_CHARS = 1800
MIN_QUERY_LEN = 4
MAX_QUERY_LEN = 200

STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "in", "on", "of", "for", "and", "or",
    "but", "with", "this", "that", "it", "we", "you", "i", "do", "does", "did",
    "what", "how", "why", "when", "where", "can", "could", "would", "should",
    "will", "may", "might", "please", "yes", "no", "ok", "okay",
}


from sips_memory_fabric import find_memory_fabric_cli as find_cli


def extract_query(prompt):
    if not prompt:
        return ""
    text = prompt.strip()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^/\S+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < MIN_QUERY_LEN:
        return ""
    if len(text) <= MAX_QUERY_LEN:
        return text
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text)
    keywords = [w for w in words if w.lower() not in STOPWORDS]
    if not keywords:
        return text[:MAX_QUERY_LEN]
    return " ".join(keywords[:8])[:MAX_QUERY_LEN]


def _recent_failed_eval_cases(max_age_seconds=7 * 86400):
    """Return set of caseIds whose latest run failed within max_age_seconds.

    Empty set if results.jsonl is missing or no recent failures.
    """
    path = Path.home() / ".ncode" / "eval" / "results.jsonl"
    if not path.exists():
        return set()
    try:
        with open(path, encoding="utf-8") as fp:
            lines = [ln.strip() for ln in fp if ln.strip()]
    except OSError:
        return set()

    runs_by_case = {}
    now = datetime.now(timezone.utc).timestamp()
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
        if now - ts > max_age_seconds:
            continue
        cid = r.get("caseId", "")
        if cid:
            runs_by_case.setdefault(cid, []).append(r)

    failed = set()
    for cid, runs in runs_by_case.items():
        runs.sort(key=lambda x: x.get("finishedAtISO", ""))
        if runs[-1].get("errorMessage"):
            continue  # didn't really run, don't boost
        if not runs[-1].get("passed"):
            failed.add(cid)
    return failed


def rank(records):
    """Failure first, then eval-adjacent boosts, then success/high-confidence, then rest."""
    failed_eval_cases = _recent_failed_eval_cases()

    def key(rec):
        tags = rec.get("tags") or []
        conf = rec.get("confidence") or ""
        ts = rec.get("created_at") or rec.get("updated_at") or ""
        body = rec.get("body") or ""

        # Eval-adjacent: tags or body mention a recently-failed caseId
        if any(cid in tags or cid in body for cid in failed_eval_cases):
            return (-1, ts)
        if "failure" in tags:
            return (0, ts)
        if "success" in tags or conf == "high":
            return (1, ts)
        return (2, ts)
    return sorted(records, key=key)


def emit(context):
    sys.stdout.write(json.dumps({"additionalContext": context}))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    prompt = payload.get("prompt") or ""
    query = extract_query(prompt)
    if not query:
        return

    mf = find_cli()
    if not mf:
        return

    cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())
    try:
        r = subprocess.run(
            ["python3", mf, "search",
             "--query", query, "--scope", cwd, "--limit", str(LIMIT)],
            capture_output=True, text=True, timeout=8
        )
        if r.returncode != 0:
            return
        data = json.loads(r.stdout) if r.stdout.strip() else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return

    records = data.get("records") or []
    if not records:
        return

    ranked = rank(records)
    header = (f"scoped recall: query '{query[:60]}' "
              f"(advisory — verify before relying on claims).")
    lines = [header]

    for rec in ranked:
        tags = rec.get("tags") or []
        title = rec.get("title", "")
        body = (rec.get("body") or "").strip().replace("\n", " ")[:200]
        conf = rec.get("confidence")
        marker = ""
        if "failure" in tags:
            marker = "⚠ PRIOR FAILURE  "
        elif "success" in tags or conf == "high":
            marker = "✓ prior success  "
        lines.append(f"- {marker}[{rec.get('tier','?')}|conf={conf}] {title}: {body}")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...(truncated)"
    emit(text)


if __name__ == "__main__":
    if "--query" in sys.argv:
        # /recall command mode — emit JSON to stdout for the command wrapper
        mf = find_cli()
        if not mf:
            print("[]")
            sys.exit(0)
        idx = sys.argv.index("--query")
        q = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        cwd = worktree_scope.resolve_scope(os.getcwd())
        try:
            r = subprocess.run(
                ["python3", mf, "search", "--query", q, "--scope", cwd,
                 "--limit", str(LIMIT)],
                capture_output=True, text=True, timeout=8
            )
            data = json.loads(r.stdout) if r.stdout.strip() else {}
        except Exception:
            data = {}
        print(json.dumps({"records": data.get("records", [])}, indent=2))
        sys.exit(0)
    main()
    sys.exit(0)
