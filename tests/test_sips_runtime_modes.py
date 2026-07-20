from __future__ import annotations

import json
from pathlib import Path

import fan_out
import goal_state


def test_mode_defaults_to_legacy_and_honors_environment(monkeypatch) -> None:
    monkeypatch.delenv("SIPS_RUNTIME_MODE", raising=False)
    assert fan_out.resolve_mode() == "legacy"
    assert goal_state.resolve_mode() == "legacy"
    monkeypatch.setenv("SIPS_RUNTIME_MODE", "shadow")
    assert fan_out.resolve_mode() == "shadow"
    assert goal_state.resolve_mode() == "shadow"


def test_fan_out_shadow_projects_without_runtime_control(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(fan_out, "FAN_OUT_DIR", tmp_path / "fan_out")
    assert fan_out.cmd_prepare("parent", ["first", "second"], mode="shadow") == 0
    output = json.loads(capsys.readouterr().out)
    state = json.loads(Path(output["statePath"]).read_text())

    runtime = state["runtime"]
    assert runtime["mode"] == "shadow"
    assert runtime["raw_hash"]
    assert runtime["migration_id"].startswith("fan-out-migration-")
    assert runtime["projection"]["graph"]["ok"] is True
    assert runtime["projection"]["read_only"] is True
    assert runtime["run_id"] is None
    assert not (tmp_path / "runtime").exists()


def test_goal_shadow_projection_does_not_mutate_legacy_fields(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "goal_state.json"
    monkeypatch.setattr(goal_state, "STATE_PATH", state_path)
    goal_state.cmd_set("document the migration", mode="shadow")
    state = json.loads(state_path.read_text())

    assert state["objective"] == "document the migration"
    assert state["status"] == "active"
    assert state["runtime"]["mode"] == "shadow"
    assert state["runtime"]["projection"]["graph"]["ok"] is True
    assert state["runtime"]["projection"]["write_performed"] is False


def test_runtime_mode_creates_plan_but_fails_closed_for_legacy_execution(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SIPS_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fan_out, "FAN_OUT_DIR", tmp_path / "fan_out")
    assert fan_out.cmd_prepare("parent", ["first"], mode="runtime") == 0
    output = json.loads(capsys.readouterr().out)
    runtime = output["runtime"]

    assert runtime["run_id"].startswith("fan-out-")
    assert runtime["authority"] == "runtime-plan"
    assert runtime["execution"] == "blocked"
    assert "lease/fencing" in runtime["blocker"]
    assert list((tmp_path / "home" / "runtime" / "v1" / "runs").iterdir())


def test_goal_runtime_attaches_controller_run_and_transition_blocker(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SIPS_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(goal_state, "STATE_PATH", tmp_path / "goal_state.json")
    goal_state.cmd_set("run safely", mode="dual")
    response = json.loads(capsys.readouterr().out)
    runtime = response["runtime"]

    assert response["mode"] == "dual"
    assert runtime["run_id"].startswith("goal-")
    assert runtime["authority"] == "runtime-plan"
    assert runtime["execution"] == "blocked"
    assert "lease/fencing" in runtime["blocker"]
