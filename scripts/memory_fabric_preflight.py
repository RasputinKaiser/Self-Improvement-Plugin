#!/usr/bin/env python3
"""Memory Fabric preflight hook.

Reads PreToolUse hook input from stdin (Edit/Write/MultiEdit), extracts the
target file path, and queries the Memory Fabric store for prior learning on
that file/scope. Returns a non-blocking additionalContext blob so the agent
sees relevant lessons before writing.

Advisory-only. Never blocks. Silent on any failure.

Hook input (from NCode):
  {
    "cwd": "...",
    "hook_event_name": "PreToolUse",
    "tool_name": "Edit",
    "tool_input": {"file_path": "/abs/path" | "path": "/abs/path"}
  }

Hook output (to NCode):
  {"additionalContext": "memory_fabric hits:\n..."}
"""
import glob
import json
import os
import subprocess
import sys
import worktree_scope
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)
LIMIT = 3
MAX_CHARS = 1500


def find_memory_fabric_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    if not candidates:
        return None
    return candidates[-1]


def emit(context):
    sys.stdout.write(json.dumps({"additionalContext": context}))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        return

    mf = find_memory_fabric_cli()
    if not mf:
        return

    cwd = worktree_scope.resolve_scope(payload.get("cwd") or os.getcwd())
    name = os.path.basename(path) or path

    try:
        r = subprocess.run(
            ["python3", mf, "search",
             "--query", name,
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

    # Stronger warning if any prior records have failure/mistake tags
    failure_keywords = ("failure", "failed", "mistake", "broken", "regress", "wrong", "bug")
    has_failure_record = any(
        any(kw in (rec.get("title", "") + rec.get("body", "")).lower() for kw in failure_keywords)
        or "failure" in (rec.get("tags") or [])
        for rec in records
    )

    header = "memory_fabric: prior records for this file/scope"
    if has_failure_record:
        header = f"memory_fabric: PRIOR FAILURE on this file — re-read before editing"
    header += " (advisory — verify before relying on claims)."
    lines = [header]
    for rec in records:
        tier = rec.get("tier", "?")
        title = rec.get("title", "")
        body = (rec.get("body") or "").strip().replace("\n", " ")[:200]
        prov = (rec.get("provenance") or {}).get("type", "?")
        conf = rec.get("confidence")
        scope_tag = rec.get("scope", "?")
        if scope_tag and scope_tag != cwd:
            scope_tag = f"scope={scope_tag}"
        else:
            scope_tag = ""
        meta = f"[{tier}|{prov}|conf={conf}]"
        if scope_tag:
            meta = f"{meta} {scope_tag}"
        lines.append(f"- {meta} {title}: {body}")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...(truncated)"
    emit(text)


if __name__ == "__main__":
    main()
    sys.exit(0)