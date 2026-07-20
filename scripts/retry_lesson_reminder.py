#!/usr/bin/env python3
"""Deterministic PostToolUse reminder for failed-to-working retry chains.

The hook keeps only the first failed input for each tool in the current
session. A later related success consumes that pending failure and emits one
line asking the agent to record the lesson through ``homebase_record``.

Hook input:
  {"hook_event_name": "PostToolUse", "tool_name": "Bash",
   "tool_input": {"command": "..."}, "tool_response": {...},
   "session_id": "..."}
Hook output:
  {"additionalContext": "..."} or empty stdout.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from sips_paths import harness_home, hook_errors_path


def debug_enabled() -> bool:
    return os.environ.get("SIPS_DEBUG") in {"1", "true", "TRUE", "yes", "YES"}


def debug_error(error: Exception) -> None:
    if not debug_enabled():
        return
    try:
        path = hook_errors_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": "retry_lesson_reminder", "error": str(error)}) + "\n")
    except OSError:
        pass


def sig_text(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, dict):
        if "file_path" in value:
            return "FP:" + str(value["file_path"])
        for key in ("cmd", "command", "expression", "text", "query", "old_string"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value, sort_keys=True)
    return str(value)


def related(name: str, first: Any, second: Any) -> bool:
    del name  # kept compatible with the retro miner's pairing helper
    first_text, second_text = sig_text(first), sig_text(second)
    if first_text.startswith("FP:") or second_text.startswith("FP:"):
        return first_text == second_text
    first_tokens = set(re.findall(r"\w+", first_text[:500]))
    second_tokens = set(re.findall(r"\w+", second_text[:500]))
    if not first_tokens or not second_tokens:
        return False
    jaccard = len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
    return jaccard >= 0.5 or difflib.SequenceMatcher(
        None, first_text[:400], second_text[:400]
    ).ratio() >= 0.6


def is_failure(payload: dict[str, Any]) -> bool:
    if payload.get("is_error") is True or payload.get("error"):
        return True
    for key in ("exit_code", "exitCode", "returncode", "return_code"):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value != 0:
            return True
    response = payload.get("tool_response")
    if isinstance(response, dict):
        if response.get("is_error") is True or response.get("error"):
            return True
        for key in ("exit_code", "exitCode", "returncode", "return_code"):
            value = response.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value != 0:
                return True
        status = str(response.get("status") or "").strip().lower()
        if status in {"error", "failed", "failure"}:
            return True
    return False


def state_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    return harness_home() / "retry_state" / f"{digest}.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"failures": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"failures": {}}
    except (OSError, json.JSONDecodeError):
        return {"failures": {}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    failures = state.get("failures") or {}
    if not failures:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"failures": failures}, sort_keys=True), encoding="utf-8")


def emit_reminder(tool_name: str) -> None:
    message = (
        f"SIPS retry detected for {tool_name}: record the failed symptom and working fix "
        "via homebase_record."
    )
    sys.stdout.write(json.dumps({"additionalContext": message}, separators=(",", ":")))
    sys.stdout.flush()


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        session_id = str(payload.get("session_id") or "").strip()
        tool_name = str(payload.get("tool_name") or "").strip()
        tool_input = payload.get("tool_input")
        if not session_id or not tool_name or not isinstance(tool_input, (dict, list, str)):
            return
        path = state_path(session_id)
        state = load_state(path)
        failures = state.setdefault("failures", {})
        if is_failure(payload):
            failures.setdefault(tool_name, {"input": tool_input, "count": 0})["count"] += 1
            save_state(path, state)
            return
        pending = failures.get(tool_name)
        if not isinstance(pending, dict) or not related(tool_name, pending.get("input"), tool_input):
            save_state(path, state)
            return
        del failures[tool_name]
        save_state(path, state)
        emit_reminder(tool_name)
    except Exception as error:  # hooks must never turn a reminder into a tool failure
        debug_error(error)


if __name__ == "__main__":
    main()
    sys.exit(0)
