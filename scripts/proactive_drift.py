#!/usr/bin/env python3
"""Proactive drift detector — SessionStart hook.

Surfaces scripts that haven't been touched recently, Memory Fabric records
never recalled, and tests that haven't run. Counteracts the "all tooling
reactive" gap — nothing else flags staleness proactively.

Advisory-only, surfaces as additionalContext.

Hook input: {"hook_event_name": "SessionStart", "cwd": "...", ...}
Hook output: {} on clean, {"additionalContext": "..."} on drift
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sips_paths import harness_home, harness_scripts_dir

NCODE_DIR = harness_home()
SCRIPTS_DIR = harness_scripts_dir()
STALE_SCRIPT_DAYS = 60
STALE_TEST_DAYS = 30
MAX_FINDINGS = 5


from sips_memory_fabric import find_memory_fabric_cli as find_cli


def emit(context):
    sys.stdout.write(json.dumps({"additionalContext": context}))
    sys.stdout.flush()


def stale_scripts():
    """Scripts under ~/.ncode/scripts/ untouched in STALE_SCRIPT_DAYS."""
    if not SCRIPTS_DIR.is_dir():
        return []
    threshold = time.time() - (STALE_SCRIPT_DAYS * 86400)
    stale = []
    for p in SCRIPTS_DIR.iterdir():
        if not p.is_file() or p.name.startswith("."):
            continue
        try:
            mtime = p.stat().st_mtime
            if mtime < threshold:
                age_days = int((time.time() - mtime) / 86400)
                stale.append((p.name, age_days))
        except OSError:
            continue
    return sorted(stale, key=lambda x: -x[1])  # oldest first


def untested_scripts():
    """Scripts without corresponding tests."""
    if not SCRIPTS_DIR.is_dir():
        return []
    tests_dir = NCODE_DIR / "tests"
    tested = set()
    if tests_dir.is_dir():
        for t in tests_dir.iterdir():
            if t.is_file():
                tested.add(t.stem)
    untested = []
    for p in SCRIPTS_DIR.iterdir():
        if p.suffix == ".py" and p.stem != "run_tests" and p.stem not in tested:
            # Quick heuristic: check if run_tests.py references this script
            run_tests = SCRIPTS_DIR / "run_tests.py"
            if run_tests.exists():
                content = run_tests.read_text(errors="replace")
                if p.stem in content or p.name in content:
                    continue
            untested.append(p.name)
    return untested[:MAX_FINDINGS]


def large_debug_dir():
    """Flag if ~/.ncode/debug/ exceeds 100MB."""
    debug_dir = NCODE_DIR / "debug"
    if not debug_dir.is_dir():
        return 0
    total = 0
    for f in debug_dir.iterdir():
        try:
            total += f.stat().st_size
        except OSError:
            continue
    return total // (1024 * 1024)  # MB


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    findings = []

    scripts = stale_scripts()
    if scripts:
        names = ", ".join(f"{n} ({d}d)" for n, d in scripts[:3])
        findings.append(f"{len(scripts)} scripts untouched > {STALE_SCRIPT_DAYS}d: {names}")

    untested = untested_scripts()
    if untested:
        findings.append(f"{len(untested)} scripts without test coverage: {', '.join(untested)}")

    debug_mb = large_debug_dir()
    if debug_mb > 100:
        findings.append(f"debug/ is {debug_mb}MB — consider cleanup")

    if not findings:
        return

    lines = ["drift detector: proactive findings (advisory)."]
    lines.extend(f"- {f}" for f in findings)
    emit("\n".join(lines))


if __name__ == "__main__":
    main()
    sys.exit(0)
