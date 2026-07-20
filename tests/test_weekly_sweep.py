from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import weekly_sweep


def option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


def test_memory_record_command_marks_failed_critical_sweep_for_verification(monkeypatch, tmp_path):
    monkeypatch.setenv("SIPS_MEMORY_SCOPE", str(tmp_path))

    command = weekly_sweep.memory_record_command(
        {
            "snapshot_pre": True,
            "tests": False,
            "eval": True,
            "self_correct": True,
            "snapshot_post": True,
        },
        {"ran": 3, "passed": 2, "failed": 1, "errors": 0},
        "2026-07-14T10:00:00+00:00",
        "2026-07-14T10:05:00+00:00",
        tmp_path / "receipt.json",
    )

    assert command[1].endswith("memory_fabric.py")
    assert option(command, "--tier") == "learning"
    assert option(command, "--scope") == str(tmp_path)
    assert option(command, "--status") == "candidate"
    assert option(command, "--confidence") == "medium"
    assert "tests=failed" in option(command, "--body")
    assert "eval=2/3 passed" in option(command, "--body")
    assert "--verify-before-use" in command


def test_weekly_sweep_treats_failed_memory_capture_as_critical(monkeypatch):
    calls = []

    def fake_run_step(name, command, cwd=None, timeout=300):
        calls.append((name, command))
        if name == "eval_harness.py":
            return True, json.dumps({"ran": 2, "passed": 2, "failed": 0, "errors": 0})
        if name == "memory_fabric record":
            return False, ""
        return True, ""

    monkeypatch.setattr(weekly_sweep, "run_step", fake_run_step)
    monkeypatch.setattr(weekly_sweep, "rotate_logs", lambda: None)
    monkeypatch.setattr(weekly_sweep, "prune_old_snapshots", lambda: (0, 0))
    monkeypatch.setattr(
        weekly_sweep,
        "write_sweep_receipt",
        lambda results, eval_summary, started_at, finished_at: Path("/tmp/weekly-receipt.json"),
        raising=False,
    )

    returncode = weekly_sweep.main([])

    assert any(name == "memory_fabric record" for name, _ in calls)
    assert returncode == 1


def test_write_sweep_receipt_creates_source_backed_json(monkeypatch, tmp_path):
    monkeypatch.setenv("SIPS_HOME", str(tmp_path))
    results = {
        "snapshot_pre": True,
        "tests": True,
        "eval": True,
        "self_correct": True,
        "snapshot_post": True,
    }

    path = weekly_sweep.write_sweep_receipt(
        results,
        {"ran": 2, "passed": 2, "failed": 0, "errors": 0},
        "2026-07-14T10:00:00+00:00",
        "2026-07-14T10:05:00+00:00",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.parent == tmp_path / "receipts" / "weekly_sweep"
    assert payload["schema"] == "sips.weekly_sweep.v1"
    assert payload["results"] == results
    assert payload["critical_ok"] is True


def test_clean_weekly_summary_writes_active_memory_with_existing_receipt(monkeypatch, tmp_path):
    sips_home = tmp_path / "sips"
    store = tmp_path / "memory.jsonl"
    scope = tmp_path / "source"
    monkeypatch.setenv("SIPS_HOME", str(sips_home))
    monkeypatch.setenv("SIPS_MEMORY_SCOPE", str(scope))
    results = {
        "snapshot_pre": True,
        "tests": True,
        "eval": True,
        "self_correct": True,
        "snapshot_post": True,
    }
    started = "2026-07-14T10:00:00+00:00"
    finished = "2026-07-14T10:05:00+00:00"
    receipt = weekly_sweep.write_sweep_receipt(
        results,
        {"ran": 2, "passed": 2, "failed": 0, "errors": 0},
        started,
        finished,
    )
    results["sweep_receipt"] = True
    command = weekly_sweep.memory_record_command(
        results,
        {"ran": 2, "passed": 2, "failed": 0, "errors": 0},
        started,
        finished,
        receipt,
    )
    env = dict(os.environ)
    env["CODEX_MEMORY_FABRIC_STORE"] = str(store)

    completed = subprocess.run(command, capture_output=True, text=True, env=env, timeout=10)
    assert completed.returncode == 0, completed.stderr
    record = json.loads(store.read_text(encoding="utf-8").strip())
    assert record["tier"] == "learning"
    assert record["status"] == "active"
    assert record["confidence"] == "high"
    assert record["verify_before_use"] is False
    assert record["scope"] == str(scope)
    assert Path(record["provenance"]["evidence_path"]).exists()
