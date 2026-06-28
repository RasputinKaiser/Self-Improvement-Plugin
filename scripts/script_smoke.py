#!/usr/bin/env python3
"""PostToolUse smoke test for ~/.ncode/scripts/*.py.

After any Edit/Write to a Python script under ~/.ncode/scripts/, run the
script's --help (or no-args) to catch syntax errors at edit time. Non-blocking
advisory feedback if the script is broken.

Advisory-only, silent on success.

Hook input:
  {"tool_name": "Edit|Write", "tool_input": {"file_path": "..."}, "tool_response": {...}}
Hook output: {} on success, {"decisionFeedback": {...}} on syntax error
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = str(Path.home() / ".ncode" / "scripts")


def emit_feedback(tips):
    sys.stdout.write(json.dumps({
        "decisionFeedback": {
            "classification": "broken-script",
            "tips": tips
        }
    }))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""

    if not path.endswith(".py"):
        return

    if not path.startswith(SCRIPTS_DIR):
        return

    if not os.path.exists(path):
        return

    try:
        r = subprocess.run(
            ["python3", path, "--help"],
            capture_output=True, text=True, timeout=5
        )
    except subprocess.TimeoutExpired:
        # --help might not exit cleanly for some scripts; try compile-only
        r2 = subprocess.run(
            ["python3", "-c", f"import py_compile; py_compile.compile({path!r}, doraise=True)"],
            capture_output=True, text=True, timeout=5
        )
        if r2.returncode != 0:
            err = r2.stderr.strip().split("\n")[-1][:300] if r2.stderr else "unknown error"
            emit_feedback([
                f"Syntax error in {os.path.basename(path)}:",
                err
            ])
        return
    except OSError:
        return

    # If --help exits non-zero, it's likely broken (not just missing argparse)
    if r.returncode != 0:
        # Check if it's just missing --help support (claim clean compile)
        try:
            r2 = subprocess.run(
                ["python3", "-c", f"import py_compile; py_compile.compile({path!r}, doraise=True)"],
                capture_output=True, text=True, timeout=5
            )
            if r2.returncode != 0:
                err = r2.stderr.strip().split("\n")[-1][:300] if r2.stderr else "syntax error"
                emit_feedback([
                    f"Syntax error in {os.path.basename(path)}:",
                    err,
                    "Fix before invoking — the script will not run."
                ])
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Coverage tip: does this script have any test cases in run_tests.py?
    run_tests_path = Path.home() / ".ncode" / "scripts" / "run_tests.py"
    if run_tests_path.exists() and path != str(run_tests_path):
        try:
            content = run_tests_path.read_text(errors="replace")
            script_name = Path(path).stem
            # Look for the script name referenced anywhere: test function or SUITES entry
            if script_name not in content and Path(path).name not in content:
                emit_feedback([
                    f"{os.path.basename(path)} has no test coverage in run_tests.py",
                    "Add at least one regression case before relying on this script."
                ])
        except OSError:
            pass


if __name__ == "__main__":
    main()
    sys.exit(0)