#!/usr/bin/env python3
"""Autonomy gate — PreToolUse risk classifier.

Generalizes the .env blocker to a broader set of critical paths and commands.
Blocking only on critical risk; high risk emits decisionFeedback (advisory)
so bypassPermissions mode isn't disrupted.

Critical (block):
  Edit/Write to: settings.json (global), ~/.local/ncode-builds/*, credential paths
  Bash: rm -rf /, git push --force, git reset --hard, sudo rm

High (advisory feedback, no block):
  Edit/Write to: ~/.ncode/scripts/* (self-modification), ~/.ncode/agents/*
  Bash: git push, gh pr create/merge, launchctl, sudo (non-rm)

Hook input:
  {"tool_name": "Edit|Write|Bash|...", "tool_input": {...}, "cwd": "..."}

Hook output:
  {"decision": "block"|"approve", "reason": "..."}  on critical
  {"decisionFeedback": {"classification": "...", "tips": [...]}}  on high
  {} (empty) on low — silent approve
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import harness_scripts_dir, script_backups_dir, scripts_dir

BACKUP_DIR = script_backups_dir()
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CRITICAL_PATH_PATTERNS = [
    r"settings\.json$",  # global settings (settings.local.json is OK)
    r"\.local/ncode-builds/.*",  # binaries
    r"(?i)(credential|token|secret)",  # sensitive filenames
    r"\.env(\.|$)",  # env files (already blocked, kept for safety)
]

CRITICAL_BASH_PATTERNS = [
    r"\brm\s+-rf\s+/(?:\s|$)",  # rm -rf /
    r"\bgit\s+push\s+(?:--force|-f)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bsudo\s+rm\b",
    r"\bmkfs\b",
    r"\bdd\s+if=/dev/[a-z]+\s+of=/dev/",  # disk overwrite
]

HIGH_PATH_PATTERNS = [
    r"\.ncode/scripts/.*\.py$",  # self-modification
    r"\.ncode/agents/.*\.md$",
    r"\.ncode/commands/.*\.md$",
]

HIGH_BASH_PATTERNS = [
    r"\bgit\s+push\b",
    r"\bgh\s+pr\s+(create|merge|close|edit)\b",
    r"\bgh\s+issue\s+(close|edit|create)\b",
    r"\blaunchctl\s+(load|unload|start|stop)\b",
    r"\bsudo\b(?!.*\brm\b)",
    r"\bbrew\s+(uninstall|remove)\b",
    r"\bpip\s+uninstall\b",
    r"\bnpm\s+uninstall\b",
]


def classify_path(path):
    for pat in CRITICAL_PATH_PATTERNS:
        if re.search(pat, path):
            return "critical", f"matches critical pattern: {pat}"
    for pat in HIGH_PATH_PATTERNS:
        if re.search(pat, path):
            return "high", f"self-modification: {pat}"
    return "low", ""


def classify_command(cmd):
    for pat in CRITICAL_BASH_PATTERNS:
        if re.search(pat, cmd):
            return "critical", f"matches critical bash pattern: {pat}"
    for pat in HIGH_BASH_PATTERNS:
        if re.search(pat, cmd):
            return "high", f"high-risk command: {pat}"
    return "low", ""


def emit_block(reason):
    sys.stdout.write(json.dumps({
        "decision": "block",
        "reason": f"Autonomy gate: {reason}. Confirm explicitly with the user before proceeding."
    }))
    sys.stdout.flush()


def emit_feedback(classification, tips):
    sys.stdout.write(json.dumps({
        "decisionFeedback": {
            "classification": classification,
            "tips": tips
        }
    }))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    path = ""
    cmd = ""

    if tool_name in ("Edit", "Write", "MultiEdit"):
        path = tool_input.get("file_path") or tool_input.get("path") or ""
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
    elif tool_name == "apply_patch":
        # Patch may contain multiple paths — check the patch content
        patch = tool_input.get("patch", "") or ""
        for line in patch.split("\n"):
            if line.startswith("+++ ") or line.startswith("--- "):
                p = line[4:].split("\t")[0].strip()
                if p and p != "/dev/null":
                    level, reason = classify_path(p)
                    if level == "critical":
                        emit_block(f"path {p}: {reason}")
                        return
                    if level == "high":
                        emit_feedback("self-modification", [
                            "Editing harness internals — verify rollback path exists",
                            "Record change in trace-logbook after completion"
                        ])
                        return
        return
    else:
        return

    if path:
        level, reason = classify_path(path)
        if level == "critical":
            emit_block(f"path {path}: {reason}")
            return
        if level == "high":
            # Snapshot the script before edit so it can be restored if tests regress
            snapshot_path = None
            snapshot_roots = (str(harness_scripts_dir()), str(scripts_dir()))
            if any(path.startswith(root) for root in snapshot_roots) and os.path.exists(path):
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                snap_name = f"{Path(path).stem}.{ts}.py"
                snapshot_path = BACKUP_DIR / snap_name
                try:
                    shutil.copy2(path, snapshot_path)
                except OSError:
                    snapshot_path = None

            tips = [
                f"Editing {path} — harness internals",
                "Run: python3 scripts/run_tests.py before AND after this edit",
                "Verify rollback path exists (backups/ under the resolved SIPS harness home)",
                "If tests regress, restore from the snapshot below",
            ]
            if snapshot_path:
                tips.append(f"Snapshot: {snapshot_path}")
            emit_feedback("self-modification", tips)
            return

    if cmd:
        level, reason = classify_command(cmd)
        if level == "critical":
            emit_block(f"command `{cmd[:80]}`: {reason}")
            return
        if level == "high":
            emit_feedback("high-risk-command", [
                f"Command `{cmd[:60]}` is high-risk ({reason})",
                "Confirm scope before executing",
                "User has bypassPermissions — not blocking, but verify intent"
            ])
            return


if __name__ == "__main__":
    main()
    sys.exit(0)
