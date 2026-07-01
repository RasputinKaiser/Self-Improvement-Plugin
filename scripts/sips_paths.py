#!/usr/bin/env python3
"""Shared path resolution for SIPS scripts.

Resolution order is intentionally simple and portable:

1. ``SIPS_HOME``
2. ``NCODE_HOME``
3. ``~/.ncode``

Plugin-root resolution follows the host-provided plugin root when present,
then falls back to the source checkout that owns this file.
"""
from __future__ import annotations

import os
from pathlib import Path


def _expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


def harness_home() -> Path:
    for key in ("SIPS_HOME", "NCODE_HOME"):
        value = os.environ.get(key)
        if value:
            return _expand(value)
    return Path.home() / ".ncode"


def plugin_root() -> Path:
    for key in ("SIPS_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        value = os.environ.get(key)
        if value:
            return _expand(value)
    return Path(__file__).resolve().parents[1]


def scripts_dir() -> Path:
    return plugin_root() / "scripts"


def harness_scripts_dir() -> Path:
    return harness_home() / "scripts"


def logs_dir() -> Path:
    return harness_home() / "logs"


def hook_events_path() -> Path:
    return harness_home() / "hook_events.jsonl"


def hook_errors_path() -> Path:
    return logs_dir() / "hook_errors.jsonl"


def improvements_path() -> Path:
    return harness_home() / "improvements.md"


def eval_results_path() -> Path:
    return harness_home() / "eval" / "results.jsonl"


def goal_state_path() -> Path:
    return harness_home() / "goal_state.json"


def continuity_dir() -> Path:
    return harness_home() / "continuity"


def script_backups_dir() -> Path:
    return harness_home() / "backups" / "scripts"
