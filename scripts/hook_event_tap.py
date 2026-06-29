#!/usr/bin/env python3
"""Hook event tap — runs a wrapped hook command, writes a JSON line to
~/.ncode/hook_events.jsonl, passes stdout through unchanged.

The tap is transparent to the hook protocol: Claude Code sees the exact same
stdout/stderr/exit-code as if the wrapped hook ran directly. Only addition
is the side log, tailed by HarnessApp's HookEventStore.

Usage:
  hook_event_tap.py --event <Event> --script <name> [--timeout <sec>] -- <command...>

Example (wrap inside hooks.json):
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hook_event_tap.py \\
    --event PreToolUse \\
    --script autonomy_gate.py \\
    -- python3 ${CLAUDE_PLUGIN_ROOT}/scripts/autonomy_gate.py

Set HARNESS_APP_NO_TAP=1 to bypass the tap entirely (the wrapped command
runs directly without the tap, and no JSONL line is written).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

LOG_PATH = os.path.expanduser("~/.ncode/hook_events.jsonl")
MAX_PREVIEW = 400


def classify_outcome(exit_code, stdout_bytes, stderr_bytes):
    """Map exit code + stdout JSON to a coarse outcome label."""
    if exit_code != 0:
        return "fail"
    try:
        d = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        # Hook emitted no JSON (silent success path) — still counts as fire
        return "fire"
    decision = d.get("decision", "")
    if decision == "block":
        return "block"
    if "decisionFeedback" in d:
        return "feedback"
    if decision == "approve":
        return "fire"
    if "additionalContext" in d or "systemMessage" in d:
        return "fire"
    return "skip"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--event", required=True, help="Hook event name (PreToolUse, etc.)")
    ap.add_argument("--script", required=True, help="Wrapped script name for display")
    ap.add_argument("--timeout", type=float, default=None, help="Optional timeout seconds")
    ap.add_argument("command", nargs=argparse.REMAINDER, help="Wrapped command (after --)")
    args = ap.parse_args()

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("ERR: no command to wrap (expected `-- <cmd...>`)", file=sys.stderr)
        sys.exit(2)

    env = dict(os.environ)
    env["HARNESS_APP_TAPPED"] = "1"

    stdin_data = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""

    # Parse stdin to extract tool_name and tool_input (for PreToolUse hooks,
    # this tells us WHAT tool the agent is about to call — including MCP tools
    # like mcp__mac-cua__click)
    tool_name = None
    tool_input_preview = None
    try:
        stdin_json = json.loads(stdin_data.decode("utf-8"))
        tool_name = stdin_json.get("tool_name")
        tool_input = stdin_json.get("tool_input", {})
        if tool_input:
            tool_input_preview = json.dumps(tool_input)[:MAX_PREVIEW]
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    start = time.time()
    try:
        r = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            timeout=args.timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        event = {
            "id": f"{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex[:6]}",
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": args.event,
            "script": args.script,
            "toolName": tool_name,
            "toolInputPreview": tool_input_preview,
            "exitCode": -1,
            "durationMs": int((time.time() - start) * 1000),
            "outcome": "timeout",
            "stdoutPreview": "",
            "stderrPreview": f"timeout after {args.timeout}s",
        }
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass
        # Pass through any output we did get
        sys.stdout.flush()
        sys.exit(124)
    except Exception as e:
        event = {
            "id": f"{int(time.time() * 1000)}-{os.getpid()}",
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": args.event,
            "script": args.script,
            "toolName": tool_name,
            "toolInputPreview": tool_input_preview,
            "exitCode": -1,
            "durationMs": int((time.time() - start) * 1000),
            "outcome": "error",
            "stdoutPreview": "",
            "stderrPreview": f"tap exception: {e}",
        }
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass
        sys.exit(1)

    # Pass through stdout (the hook's JSON additionalContext, if any)
    sys.stdout.buffer.write(r.stdout)
    sys.stdout.buffer.flush()
    # Pass through stderr too — Claude Code may surface warnings
    sys.stderr.buffer.write(r.stderr)
    sys.stderr.buffer.flush()

    outcome = classify_outcome(r.returncode, r.stdout, r.stderr)
    event = {
        "id": f"{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex[:6]}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": args.event,
        "script": args.script,
        "toolName": tool_name,
        "toolInputPreview": tool_input_preview,
        "exitCode": r.returncode,
        "durationMs": int((time.time() - start) * 1000),
        "outcome": outcome,
        "stdoutPreview": r.stdout.decode("utf-8", errors="replace")[:MAX_PREVIEW],
        "stderrPreview": r.stderr.decode("utf-8", errors="replace")[:MAX_PREVIEW],
    }
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass  # never break the wrapped hook with a logging failure

    sys.exit(r.returncode)


if __name__ == "__main__":
    main()