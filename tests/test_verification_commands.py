from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )


def test_eval_md_is_in_sync_with_validator_output():
    proc = run_command("python3", "scripts/validate_v2.py", "--check-eval")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "checks passed" in proc.stdout


def test_hook_contract_suite_passes():
    proc = run_command("python3", "scripts/run_tests.py", "hook_contract", "--verbose")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 pass, 0 fail" in proc.stdout
