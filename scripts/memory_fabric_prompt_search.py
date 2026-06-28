#!/usr/bin/env python3
"""Memory Fabric prompt-time search.

Fires on UserPromptSubmit. Extracts the user's prompt content and searches
the Memory Fabric store for prior learnings on the topic. Returns prior
records as additionalContext so the agent starts each task already informed
by past work.

Advisory-only, non-blocking, silent on failure.

Hook input:
  {"hook_event_name": "UserPromptSubmit", "cwd": "...", "prompt": "...", "session_id": "..."}
Hook output:
  {"additionalContext": "memory_fabric hits:\n..."}
"""
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)
LIMIT = 3
MAX_CHARS = 1500
MIN_QUERY_LEN = 4
MAX_QUERY_LEN = 200

STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "in", "on", "of", "for", "and", "or",
    "but", "with", "this", "that", "it", "we", "you", "i", "do", "does", "did",
    "what", "how", "why", "when", "where", "can", "could", "would", "should",
    "will", "may", "might", "please", "yes", "no", "ok", "okay",
}


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def extract_query(prompt):
    """Distill a meaningful search query from the user's free-form prompt."""
    if not prompt:
        return ""
    text = prompt.strip()
    # Strip XML-ish tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip command invocation prefixes
    text = re.sub(r"^/\S+\s*", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < MIN_QUERY_LEN:
        return ""
    # If short enough, use as-is
    if len(text) <= MAX_QUERY_LEN:
        return text
    # Otherwise extract keywords (skip stopwords)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text)
    keywords = [w for w in words if w.lower() not in STOPWORDS]
    if not keywords:
        return text[:MAX_QUERY_LEN]
    query = " ".join(keywords[:8])
    return query[:MAX_QUERY_LEN]


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

    cwd = payload.get("cwd") or os.getcwd()

    try:
        r = subprocess.run(
            ["python3", mf, "search",
             "--query", query,
             "--scope", cwd,
             "--limit", str(LIMIT)],
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

    # Detect prior failure patterns matching this prompt
    failure_keywords = ("failure", "failed", "mistake", "broken", "regress", "wrong", "bug")
    prompt_lower = query.lower()
    has_user_failure_mention = any(kw in prompt_lower for kw in failure_keywords)
    has_prior_failure_record = any(
        any(kw in (rec.get("title", "") + rec.get("body", "")).lower() for kw in failure_keywords)
        or "failure" in (rec.get("tags") or [])
        for rec in records
    )

    header = f"memory_fabric: prior records for query '{query[:60]}'"
    transferable = None
    if has_user_failure_mention or has_prior_failure_record:
        header = f"memory_fabric: PRIOR FAILURES on this query — avoid repeating past mistakes"
        # Find most recent success record as prescriptive guidance
        for rec in records:
            if "success" in (rec.get("tags") or []) or rec.get("confidence") == "high":
                transferable = rec
                break
    header += " (advisory — verify before relying on claims)."
    lines = [header]
    for rec in records:
        tier = rec.get("tier", "?")
        title = rec.get("title", "")
        body = (rec.get("body") or "").strip().replace("\n", " ")[:180]
        prov = (rec.get("provenance") or {}).get("type", "?")
        conf = rec.get("confidence")
        meta = f"[{tier}|{prov}|conf={conf}]"
        lines.append(f"- {meta} {title}: {body}")

    if transferable:
        body = (transferable.get("body") or "").strip().replace("\n", " ")[:250]
        lines.append(f"\n→ Last successful approach: {transferable.get('title', '?')}")
        if body:
            lines.append(f"  {body}")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...(truncated)"
    emit(text)


if __name__ == "__main__":
    main()
    sys.exit(0)