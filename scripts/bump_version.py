#!/usr/bin/env python3
"""Atomically bump SIPS source manifests and verify the resulting source tree.

This helper intentionally stops before cache refresh, commit, push, or publish.
Run ``codex plugin add harness-self-improvement@harness-local`` separately only
after reviewing the verified source diff.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "harness-self-improvement"
SEMVER_IDENTIFIER = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    rf"(?:-({SEMVER_IDENTIFIER}(?:\.{SEMVER_IDENTIFIER})*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
VERSION_PATHS = (
    Path(".codex-plugin/plugin.json"),
    Path(".ncode-plugin/marketplace.json"),
    Path("pyproject.toml"),
)


def validate_version(version: str) -> str:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"version must be SemVer without a v prefix: {version!r}")
    return version


def _semver_key(version: str) -> tuple[tuple[int, int, int], tuple]:
    match = SEMVER_RE.fullmatch(validate_version(version))
    assert match is not None
    core = tuple(int(part) for part in match.groups()[:3])
    prerelease = match.group(4)
    if prerelease is None:
        return core, (1,)
    identifiers = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in prerelease.split(".")
    )
    return core, (0, identifiers)


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def _replace_json_version(text: str, current: str, new_version: str, path: Path) -> str:
    pattern = re.compile(rf'("version"\s*:\s*)"{re.escape(current)}"')
    updated, count = pattern.subn(rf'\g<1>"{new_version}"', text, count=1)
    if count != 1:
        raise ValueError(f"expected one version field in {path}, replaced {count}")
    return updated


def _project_version(text: str, path: Path) -> str:
    project = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project.group(1)) if project else None
    if not match:
        raise ValueError(f"missing [project] version in {path}")
    return match.group(1)


def _replace_project_version(text: str, current: str, new_version: str, path: Path) -> str:
    project = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    if not project:
        raise ValueError(f"missing [project] table in {path}")
    body = project.group(1)
    updated_body, count = re.subn(
        rf'(?m)^(version\s*=\s*)"{re.escape(current)}"\s*$',
        rf'\g<1>"{new_version}"',
        body,
        count=1,
    )
    if count != 1:
        raise ValueError(f"expected one [project] version in {path}, replaced {count}")
    return text[: project.start(1)] + updated_body + text[project.end(1) :]


def build_updates(root: Path, new_version: str) -> tuple[str, dict[Path, str]]:
    validate_version(new_version)
    plugin_path = root / VERSION_PATHS[0]
    marketplace_path = root / VERSION_PATHS[1]
    pyproject_path = root / VERSION_PATHS[2]

    plugin = _read_json(plugin_path)
    marketplace = _read_json(marketplace_path)
    current = str(plugin.get("version") or "")
    validate_version(current)
    if _semver_key(new_version) <= _semver_key(current):
        raise ValueError(f"new version {new_version} must be greater than current version {current}")

    plugins = marketplace.get("plugins") or []
    matches = [item for item in plugins if isinstance(item, dict) and item.get("name") == PLUGIN_ID]
    if len(matches) != 1:
        raise ValueError(f"expected one {PLUGIN_ID} entry in {marketplace_path}, found {len(matches)}")
    marketplace_version = str(matches[0].get("version") or "")
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    pyproject_version = _project_version(pyproject_text, pyproject_path)
    if {current, marketplace_version, pyproject_version} != {current}:
        raise ValueError(
            "source versions disagree before bump: "
            f"plugin={current}, marketplace={marketplace_version}, pyproject={pyproject_version}"
        )

    plugin_text = plugin_path.read_text(encoding="utf-8")
    marketplace_text = marketplace_path.read_text(encoding="utf-8")
    return current, {
        plugin_path: _replace_json_version(plugin_text, current, new_version, plugin_path),
        marketplace_path: _replace_json_version(
            marketplace_text, current, new_version, marketplace_path
        ),
        pyproject_path: _replace_project_version(
            pyproject_text, current, new_version, pyproject_path
        ),
    }


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.sips-version-{os.getpid()}.tmp")
    try:
        temporary.write_bytes(data)
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _run(command: Sequence[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _gate(command: Sequence[str], root: Path) -> bool:
    completed = _run(command, root)
    label = " ".join(command)
    if completed.returncode == 0:
        print(f"PASS: {label}")
        return True
    print(f"FAIL: {label} (exit {completed.returncode})", file=sys.stderr)
    if completed.stdout:
        print(completed.stdout.rstrip(), file=sys.stderr)
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return False


def apply_bump(root: Path, new_version: str) -> int:
    current, updates = build_updates(root, new_version)
    preflight = [sys.executable, "scripts/validate_v2.py", "--check-eval"]
    if not _gate(preflight, root):
        print("No files changed because the pre-bump source was not coherent.", file=sys.stderr)
        return 1

    eval_path = root / "EVAL.md"
    tracked = set(updates) | {eval_path}
    originals = {path: path.read_bytes() if path.exists() else None for path in tracked}
    try:
        for path, text in updates.items():
            _atomic_write(path, text.encode("utf-8"))
        gates = (
            [sys.executable, "scripts/validate_v2.py", "--write-eval"],
            [sys.executable, "scripts/run_tests.py"],
            [sys.executable, "-m", "pytest", "-q"],
        )
        for command in gates:
            if not _gate(command, root):
                raise RuntimeError("version-bump verification failed")
    except (OSError, RuntimeError) as exc:
        for path, data in originals.items():
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                _atomic_write(path, data)
        print(f"ROLLED BACK: {exc}", file=sys.stderr)
        return 1

    print(f"BUMPED: {current} -> {new_version}")
    print("Source verification passed. Cache/install/publish were not changed.")
    print("Next after review: codex plugin add harness-self-improvement@harness-local")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("new_version", help="new SemVer, for example 0.4.0 or 0.4.0-rc.1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show the three source files without writing or running gates",
    )
    args = parser.parse_args(argv)
    try:
        current, updates = build_updates(ROOT, args.new_version)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"DRY RUN: {current} -> {args.new_version}")
        for path in updates:
            print(path.relative_to(ROOT))
        print("No files changed. Cache/install/publish are outside this helper.")
        return 0
    return apply_bump(ROOT, args.new_version)


if __name__ == "__main__":
    raise SystemExit(main())
