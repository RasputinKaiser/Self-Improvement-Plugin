from __future__ import annotations

from types import SimpleNamespace

import fan_out


def test_legacy_text_parser_fails_closed_when_required_blocks_are_missing() -> None:
    parsed = fan_out.parse_agent_response("SLICE: delivered something")

    assert parsed["malformed"] is True
    assert parsed["blocked"] is False


def test_fan_out_lessons_start_as_verify_before_use_candidates(monkeypatch) -> None:
    captured: list[str] = []

    monkeypatch.setattr(fan_out, "find_memory_fabric_cli", lambda: "/tmp/memory_fabric.py")

    def fake_run(command, **_kwargs):
        captured.extend(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(fan_out.subprocess, "run", fake_run)

    ok = fan_out.record_lesson(
        {"id": "run-1", "parent": "parent"},
        {"id": "slice_1", "description": "slice"},
        "lesson",
    )

    assert ok is True
    assert captured[captured.index("--status") + 1] == "candidate"
    assert "--verify-before-use" in captured
    assert captured[captured.index("--provenance-type") + 1] == "user_or_agent_observation"


def test_fan_out_lesson_capture_reports_writer_failure(monkeypatch) -> None:
    monkeypatch.setattr(fan_out, "find_memory_fabric_cli", lambda: "/tmp/memory_fabric.py")
    monkeypatch.setattr(
        fan_out.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )

    assert fan_out.record_lesson(
        {"id": "run-1", "parent": "parent"},
        {"id": "slice_1", "description": "slice"},
        "lesson",
    ) is False
