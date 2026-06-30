from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

from memory_fabric_install_copy import should_ignore


def directory_fingerprint(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = list(fingerprint_files(root))
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"digest": digest.hexdigest(), "file_count": len(files)}


def fingerprint_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and not ignored(path, root))


def ignored(path: Path, root: Path) -> bool:
    return any(map(should_ignore, path.relative_to(root).parts))


def compare_directories(source: Path, target: Path) -> dict[str, Any]:
    source_fingerprint = directory_fingerprint(source)
    target_fingerprint = directory_fingerprint(target)
    return {
        "ok": source_fingerprint == target_fingerprint,
        "source": source_fingerprint,
        "target": target_fingerprint,
    }
