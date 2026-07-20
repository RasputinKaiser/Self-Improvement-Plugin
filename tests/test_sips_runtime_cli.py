from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sips_runtime.py"


def test_cli_read_compact_default():
    completed = subprocess.run([sys.executable, str(CLI), "read", "--op", "status"], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True and payload["operation"] == "status"
    assert "data" not in payload


def test_cli_write_requires_idempotency_and_revision():
    completed = subprocess.run([sys.executable, str(CLI), "write", "--op", "create", "--detail", "full"], capture_output=True, text=True)
    assert completed.returncode != 0
    assert json.loads(completed.stdout)["error"] == "idempotency_key_required"


def test_cli_json_stdin_full_detail():
    with tempfile.TemporaryDirectory() as root:
        environment = dict(os.environ, SIPS_HOME=root)
        completed = subprocess.run(
            [sys.executable, str(CLI), "write", "--op", "create", "--stdin", "--detail", "full"],
            input=json.dumps({"idempotency_key": "cli-1", "expected_revision": 0, "tasks": [{"id": "task-1"}]}),
            capture_output=True,
            text=True,
            env=environment,
        )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True and payload["operation"] == "create"
    assert "data" in payload
