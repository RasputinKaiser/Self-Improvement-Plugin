from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import bump_version


ROOT = Path(__file__).resolve().parents[1]


def write_version_fixture(root: Path) -> None:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".ncode-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "harness-self-improvement", "version": "0.3.1"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / ".ncode-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "harness-self-improvement", "version": "0.3.1"}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sips-harness"\nversion = "0.3.1"\n\n[tool.pytest.ini_options]\n',
        encoding="utf-8",
    )


def test_build_updates_changes_only_three_authoritative_version_files(tmp_path):
    write_version_fixture(tmp_path)

    current, updates = bump_version.build_updates(tmp_path, "0.4.0-rc.1")

    assert current == "0.3.1"
    assert {path.relative_to(tmp_path).as_posix() for path in updates} == {
        ".codex-plugin/plugin.json",
        ".ncode-plugin/marketplace.json",
        "pyproject.toml",
    }
    assert json.loads(updates[tmp_path / ".codex-plugin" / "plugin.json"])["version"] == "0.4.0-rc.1"
    assert json.loads(updates[tmp_path / ".ncode-plugin" / "marketplace.json"])["plugins"][0]["version"] == "0.4.0-rc.1"
    assert 'version = "0.4.0-rc.1"' in updates[tmp_path / "pyproject.toml"]
    assert 'version = "0.3.1"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")


@pytest.mark.parametrize("version", ["1", "v1.2.3", "1.02.3", "1.2.3-01", "1.2.3 bad", ""])
def test_validate_version_rejects_non_semver(version):
    with pytest.raises(ValueError):
        bump_version.validate_version(version)


@pytest.mark.parametrize("version", ["0.3.1", "0.3.0", "0.3.1-rc.1"])
def test_build_updates_rejects_non_increasing_versions(tmp_path, version):
    write_version_fixture(tmp_path)

    with pytest.raises(ValueError, match="must be greater"):
        bump_version.build_updates(tmp_path, version)


def test_apply_bump_restores_exact_bytes_when_a_gate_fails(tmp_path, monkeypatch):
    write_version_fixture(tmp_path)
    eval_path = tmp_path / "EVAL.md"
    eval_path.write_text("preexisting generated receipt\n", encoding="utf-8")
    paths = [tmp_path / path for path in bump_version.VERSION_PATHS] + [eval_path]
    before = {path: path.read_bytes() for path in paths}
    gate_results = iter([True, True, False])
    monkeypatch.setattr(bump_version, "_gate", lambda command, root: next(gate_results))

    returncode = bump_version.apply_bump(tmp_path, "0.4.0")

    assert returncode == 1
    assert {path: path.read_bytes() for path in paths} == before


def test_cli_dry_run_lists_only_manifests_and_preserves_source_bytes():
    paths = [ROOT / path for path in bump_version.VERSION_PATHS]
    before = {path: path.read_bytes() for path in paths}
    current = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    core = current.split("+", 1)[0].split("-", 1)[0]
    major, minor, patch = (int(part) for part in core.split("."))
    next_version = core if "-" in current else f"{major}.{minor}.{patch + 1}"

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "bump_version.py"), next_version, "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert ".codex-plugin/plugin.json" in completed.stdout
    assert ".ncode-plugin/marketplace.json" in completed.stdout
    assert "pyproject.toml" in completed.stdout
    assert "Cache/install/publish are outside this helper" in completed.stdout
    assert {path: path.read_bytes() for path in paths} == before
