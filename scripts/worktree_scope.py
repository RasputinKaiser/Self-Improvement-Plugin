#!/usr/bin/env python3
"""worktree_scope.py — resolve cwd to a stable canonical Memory Fabric scope.

Memory Fabric records are scoped to cwd. In a linked worktree, `cwd` is the throwaway worktree path, so records become
invisible to future sessions in the main repo. This module maps worktree paths
back to the canonical main-repo root so scopes remain stable across worktree
and non-worktree sessions.

Detection uses `git rev-parse --absolute-git-dir`:
  - In a normal repo:    returns `<repo>/.git`
  - In a linked worktree: returns `<repo>/.git/worktrees/<name>`

If the git-dir path contains the `.git/worktrees/` marker, the cwd is
inside a linked worktree and resolve_scope() returns the main-repo root.

Escape hatch: set HARNESS_NO_WORKTREE_REMAP=1 to make resolve_scope() a
strict identity (always returns the input resolved), for rollback / debug.

Tested by run_tests.py — the `worktree` suite. The resolver is pure given
an injectable git runner, so it is unit-testable without spawning a real
git worktree.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

_NO_REMAP_ENV = "HARNESS_NO_WORKTREE_REMAP"
_CACHE_TTL_SECONDS = 60.0


def _default_runner(cwd, *args):
    """Run `git -C <cwd> <args...>` and return CompletedProcess."""
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        timeout=5,
    )


class _TTLCache:
    def __init__(self, ttl=_CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._store = {}

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key, value):
        self._store[key] = (time.monotonic(), value)

    def clear(self):
        self._store.clear()


_cache = _TTLCache()


def is_worktree(cwd, runner=_default_runner):
    # type: (str, object) -> bool
    """True if `cwd` is inside a git linked worktree (not the main one)."""
    return _main_root_for(cwd, runner) is not None


def worktree_main_root(cwd, runner=_default_runner):
    # type: (str, object) -> Optional[Path]
    """Return the main-repo root if `cwd` is in a linked worktree, else None."""
    return _main_root_for(cwd, runner)


def resolve_scope(cwd, runner=_default_runner):
    # type: (str, object) -> str
    """Resolve `cwd` to its canonical Memory Fabric scope.

    - If HARNESS_NO_WORKTREE_REMAP=1, returns the input resolved (escape hatch).
    - If `cwd` is inside a linked git worktree, returns the main-repo root.
    - Otherwise returns `Path(cwd).resolve()` (stable absolute path).
    """
    cwd_str = str(cwd)
    if os.environ.get(_NO_REMAP_ENV) == "1":
        return str(Path(cwd_str).resolve())

    cached = _cache.get(cwd_str)
    if cached is not None:
        return cached

    main_root = _main_root_for(cwd_str, runner)
    if main_root is not None:
        result = str(main_root)
    else:
        try:
            result = str(Path(cwd_str).resolve())
        except (OSError, RuntimeError):
            result = cwd_str
    _cache.set(cwd_str, result)
    return result


def clear_cache():
    # type: () -> None
    """Test helper — drop all cached resolutions."""
    _cache.clear()


def _main_root_for(cwd, runner):
    """Return main-repo root if cwd is in a linked worktree, else None.

    Pure FP given a deterministic `runner` — unit-testable without
    spawning a real worktree.
    """
    cwd_str = str(cwd)
    try:
        result = runner(cwd_str, "rev-parse", "--absolute-git-dir")
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    git_dir_raw = result.stdout.strip()
    if not git_dir_raw:
        return None

    git_path = Path(git_dir_raw)
    if not git_path.is_absolute():
        git_path = Path(cwd_str) / git_path
    try:
        git_path = git_path.resolve()
    except (OSError, RuntimeError):
        return None

    parts = git_path.parts
    # Look for .../<main>/.git/worktrees/<name>
    for i in range(len(parts) - 1):
        if parts[i] == ".git" and parts[i + 1] == "worktrees" and i >= 1:
            return Path(*parts[:i]).resolve()
    return None


if __name__ == "__main__":
    # Manual smoke: print resolution for argv[1] or cwd
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    print("cwd:        ", target)
    print("resolved:   ", resolve_scope(target))
    print("is_worktree:", is_worktree(target))
    if is_worktree(target):
        print("main_root:  ", worktree_main_root(target))