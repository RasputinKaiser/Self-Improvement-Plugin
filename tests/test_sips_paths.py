from __future__ import annotations

import importlib
from pathlib import Path

import sips_paths


def test_harness_home_prefers_sips_home(monkeypatch, tmp_path):
    sips_home = tmp_path / "sips-home"
    ncode_home = tmp_path / "ncode-home"
    monkeypatch.setenv("SIPS_HOME", str(sips_home))
    monkeypatch.setenv("NCODE_HOME", str(ncode_home))

    importlib.reload(sips_paths)

    assert sips_paths.harness_home() == sips_home.resolve()


def test_harness_home_falls_back_to_ncode_home(monkeypatch, tmp_path):
    ncode_home = tmp_path / "ncode-home"
    monkeypatch.delenv("SIPS_HOME", raising=False)
    monkeypatch.setenv("NCODE_HOME", str(ncode_home))

    importlib.reload(sips_paths)

    assert sips_paths.harness_home() == ncode_home.resolve()


def test_plugin_root_prefers_explicit_env(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugin-root"
    monkeypatch.setenv("SIPS_PLUGIN_ROOT", str(plugin_root))

    importlib.reload(sips_paths)

    assert sips_paths.plugin_root() == plugin_root.resolve()
    assert sips_paths.scripts_dir() == plugin_root.resolve() / "scripts"


def test_derived_paths_are_under_harness_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SIPS_HOME", str(tmp_path))

    importlib.reload(sips_paths)

    assert sips_paths.hook_events_path() == tmp_path.resolve() / "hook_events.jsonl"
    assert sips_paths.hook_errors_path() == tmp_path.resolve() / "logs" / "hook_errors.jsonl"
    assert sips_paths.goal_state_path() == tmp_path.resolve() / "goal_state.json"
    assert sips_paths.continuity_dir() == tmp_path.resolve() / "continuity"


def teardown_module():
    importlib.reload(sips_paths)
