"""Tests for scripts/inline_widget.py — SIPS inline chat-widget rendering."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "inline_widget.py"

spec = importlib.util.spec_from_file_location("inline_widget", SCRIPT)
inline_widget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inline_widget)


@pytest.fixture(autouse=True)
def isolated_widget_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("SIPS_HOME", str(tmp_path / "sips"))
    stream = tmp_path / "hooks.jsonl"
    stream.write_text(json.dumps({"tool_name": "fixture_tool", "status": "ok",
                                 "session_id": "fixture-session", "ts": "2026-01-01T00:00:00+00:00"}) + "\n")
    monkeypatch.setenv("SIPS_HOOK_EVENTS", str(stream))
    memory = tmp_path / "memory.jsonl"
    memory.write_text("")
    monkeypatch.setenv("CODEX_MEMORY_FABRIC_STORE", str(memory))


def test_render_board_includes_status_progress_and_tasks():
    board = {
        "schema": "sips.runtime.campaign-board.v1",
        "status": "running",
        "objective": "Test objective",
        "revision": 7,
        "run_id": "r1",
        "progress": {"complete": 2, "total": 4, "ratio": 0.5},
        "counts": {"queued": 1, "running": 1},
        "tasks": [
            {
                "id": "t1",
                "title": "Task one",
                "phase": "verify",
                "status": "running",
                "attempts": 2,
            },
            {"id": "t2", "title": "Task two", "phase": "record", "status": "queued"},
        ],
    }
    html = inline_widget.render_board(board)
    assert "Test objective" in html
    assert "2/4 tasks (50%)" in html
    assert "rev 7" in html
    assert "Task one" in html
    assert "1 queued · 1 running" in html
    assert "try 2" in html
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "background: transparent" in html
    assert "var(--foreground" in html  # theme-var contract
    assert 'data-hermes-send="' in html  # interactive reply wiring


def test_render_board_escapes_html_in_titles():
    board = {
        "status": "active",
        "objective": "<script>alert(1)</script>",
        "progress": {"complete": 0, "total": 1, "ratio": 0},
        "counts": {},
        "tasks": [{"id": "t", "title": "<img src=x>", "phase": "plan", "status": "queued"}],
    }
    html = inline_widget.render_board(board)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x>" not in html


def test_render_board_caps_task_list_with_more_note():
    tasks = [{"id": f"t{i}", "title": f"T{i}", "phase": "plan", "status": "queued"} for i in range(12)]
    board = {
        "status": "running",
        "objective": "obj",
        "progress": {"complete": 0, "total": 12, "ratio": 0},
        "counts": {"queued": 12},
        "tasks": tasks,
    }
    html = inline_widget.render_board(board)
    assert "+4 more task(s)" in html
    assert "T11" not in html


def test_cli_writes_html_and_prints_media_path(tmp_path):
    out = tmp_path / "widget.html"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "board", "--out", str(out)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == f"MEDIA:{out}"
    written = out.read_text(encoding="utf-8")
    assert written.lstrip().startswith("<!DOCTYPE html>")
    # The generated widget must embed real board JSON fields, not placeholder data.
    assert "SIPS Goal Board" in written


def test_cli_json_board_round_trip_matches_goal_state_schema():
    """The loader must consume the real goal_state.py board JSON unchanged."""
    setup = subprocess.run(
        [sys.executable, str(SCRIPT.parent / "goal_state.py"), "set", "Widget fixture goal"],
        capture_output=True, text=True, timeout=60,
    )
    assert setup.returncode == 0, setup.stderr
    proc = subprocess.run(
        [sys.executable, str(SCRIPT.parent / "goal_state.py"), "board"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    board = json.loads(proc.stdout)
    assert board["schema"] == "sips.runtime.campaign-board.v1"
    html = inline_widget.render_board(board)
    assert "SIPS Goal Board" in html


# ------------------------------------------------------------- lifecycle ----

def test_load_lifecycle_reads_recorded_hook_stream():
    data = inline_widget.load_lifecycle()
    assert data["tools"] == {"fixture_tool": 1}
    assert data["sessions"] == 1
    assert len(data["buckets"]) == 1


def test_render_lifecycle_includes_bars_spark_and_statuses():
    data = {
        "tools": {"terminal": 10, "patch": 5, "read_file": 2},
        "statuses": {"ok": 15, "blocked": 2},
        "buckets": {1000000: 4, 10021600: 8, 10043200: 5},
        "sessions": 3,
        "window": {"first": 1000000.0, "last": 10043200.0},
    }
    html = inline_widget.render_lifecycle(data)
    assert "terminal" in html
    assert "10" in html
    assert "2 blocked" in html
    assert "3 sessions" in html
    assert "<polyline" in html  # sparkline path
    assert "events per 6h" in html


def test_sparkline_scales_to_bucket_max():
    svg = inline_widget._sparkline_svg({0: 1, 1: 10, 2: 4})
    assert svg.startswith("<svg")
    assert "polyline" in svg


# ---------------------------------------------------------------- memory ----

def test_trust_status_normalizes_both_schemas():
    assert inline_widget.trust_status({"trust": {"status": "ready"}}) == "ready"
    assert inline_widget.trust_status({"verify_before_use": True}) == "verify_before_use"
    assert inline_widget.trust_status({"verify_before_use": False}) == "ready"
    assert inline_widget.trust_status({}) == "ready"


def test_render_memory_shows_trust_split_and_donut():
    data = {
        "total": 6,
        "trust": {"ready": 4, "verify_before_use": 2},
        "tiers": {"learning": 3, "work": 2, "knowledge": 1},
        "recent": [
            {"title": "Rec <b>one</b>", "body": "body text", "trust": {"status": "ready"}},
            {"title": "Rec two", "body": "body two", "verify_before_use": True},
        ],
    }
    html = inline_widget.render_memory(data)
    assert "4 ready" in html
    assert "2 verify_before_use" in html
    assert "Rec &lt;b&gt;one&lt;/b&gt;" in html  # escaped
    assert "learning" in html
    assert "<circle" in html  # donut segments
    assert "2588" not in html  # no placeholder/live leakage in synthetic render


def test_cli_lifecycle_and_memory_kinds(tmp_path):
    for kind in ("lifecycle", "memory"):
        out = tmp_path / f"{kind}.html"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), kind, "--out", str(out)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert out.exists()
        assert "SIPS" in out.read_text(encoding="utf-8")
