from __future__ import annotations
import fnmatch
import shutil
from pathlib import Path
from typing import Any


IGNORE_NAMES = {".codex", ".git", ".plugin-eval", "__pycache__"}
IGNORE_PATTERNS = {"*.pyc", ".DS_Store", ".plugin-eval-analysis*"}


def copy_source(source: Path, target: Path) -> dict[str, Any]:
    tmp = target.with_name(target.name + ".tmp-sync")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, tmp, ignore=ignore)
    tmp.rename(target)
    return {"from": str(source), "to": str(target), "method": "copytree_tmp_rename"}


def ignore(directory: str, names: list[str]) -> set[str]:
    root = Path(directory)
    return {
        name
        for name in names
        if should_ignore(name) or (root / name).is_symlink()
    }


def should_ignore(name: str) -> bool:
    return name in IGNORE_NAMES or any(fnmatch.fnmatch(name, pattern) for pattern in IGNORE_PATTERNS)
