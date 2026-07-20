from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "retry_lesson_reminder.py"


def run_hook(payload: dict, home: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SIPS_HOME"] = str(home)
    return subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(ROOT),
        env=env,
    )


def test_failed_then_related_working_retry_emits_one_line_reminder(tmp_path):
    failed = {
        "hook_event_name": "PostToolUse",
        "session_id": "retry-test",
        "tool_name": "Bash",
        "tool_input": {"command": "python3 scripts/check.py --scope repo"},
        "tool_response": {"is_error": True, "stderr": "missing dependency"},
    }
    worked = {
        **failed,
        "tool_input": {"command": "python3 scripts/check.py --scope repo --install"},
        "tool_response": {"exit_code": 0, "stdout": "passed"},
    }

    first = run_hook(failed, tmp_path)
    second = run_hook(worked, tmp_path)
    third = run_hook(worked, tmp_path)

    assert first.returncode == 0
    assert first.stdout == ""
    assert second.returncode == 0
    reminder = json.loads(second.stdout)
    assert reminder["additionalContext"].startswith("SIPS retry detected for Bash:")
    assert "homebase_record" in reminder["additionalContext"]
    assert third.stdout == ""


def test_unrelated_success_is_silent_and_bad_input_is_nonblocking(tmp_path):
    failed = {
        "session_id": "unrelated-test",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/one.py"},
        "tool_response": {"is_error": True},
    }
    unrelated = {
        **failed,
        "tool_input": {"file_path": "/tmp/two.py"},
        "tool_response": {"status": "success"},
    }

    assert run_hook(failed, tmp_path).stdout == ""
    assert run_hook(unrelated, tmp_path).stdout == ""
    malformed = subprocess.run(
        ["python3", str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(ROOT),
        env={**os.environ, "SIPS_HOME": str(tmp_path)},
    )
    assert malformed.returncode == 0
    assert malformed.stdout == ""
