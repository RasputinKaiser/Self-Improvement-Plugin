#!/usr/bin/env python3
"""Harness snapshot — writes a known-good backup of all ~/.ncode/scripts/*.py.

Used before risky self-modification batches. If run_tests.py regresses after
edits, the snapshot can be restored wholesale via restore_harness.py.

Snapshot contents:
  - All .py and .sh files in ~/.ncode/scripts/
  - manifest.json (hash, timestamp, file list, reason field)

Usage:
  snapshot_harness.py                                  # snapshot with default reason
  snapshot_harness.py --reason "before behavior-test edits"
  snapshot_harness.py --list                           # list snapshots
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import harness_home, harness_scripts_dir

NCODE_DIR = harness_home()
SCRIPTS_DIR = harness_scripts_dir()
BACKUP_ROOT = NCODE_DIR / "backups" / "snapshots"


def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_set(file_hashes):
    h = hashlib.sha256()
    for name, digest in sorted(file_hashes.items()):
        h.update(name.encode())
        h.update(b"\0")
        h.update(digest.encode())
        h.update(b"\0")
    return h.hexdigest()[:16]


def create_snapshot(reason, force=False):
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    if not SCRIPTS_DIR.is_dir():
        print("ERR: scripts dir not found", file=sys.stderr)
        return 2

    files = sorted(p for p in SCRIPTS_DIR.iterdir()
                   if p.suffix in (".py", ".sh") and not p.name.startswith("."))

    file_hashes = {p.name: hash_file(p) for p in files}
    set_hash = hash_set(file_hashes)
    snapshot_dir = BACKUP_ROOT / set_hash

    if snapshot_dir.exists() and not force:
        print(f"snapshot already exists: {snapshot_dir}")
        print("use --force to overwrite, or accept existing")
        return 0

    if snapshot_dir.exists() and force:
        shutil.rmtree(snapshot_dir)

    snapshot_dir.mkdir(parents=True)
    for p in files:
        shutil.copy2(p, snapshot_dir / p.name)

    manifest = {
        "hash": set_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "files": [{"name": p.name, "sha256": file_hashes[p.name]} for p in files],
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"snapshot created: {snapshot_dir}")
    print(f"hash: {set_hash}")
    print(f"files: {len(files)}")
    print(f"reason: {reason}")
    return 0


def list_snapshots():
    if not BACKUP_ROOT.is_dir():
        print("no snapshots")
        return 0
    snap_dirs = sorted(BACKUP_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"snapshots: {len(snap_dirs)}")
    for d in snap_dirs[:5]:
        manifest = d / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text())
                ts = m.get("created_at", "?")[:19]
                reason = m.get("reason", "?")
                files_n = len(m.get("files", []))
                print(f"  {d.name}  {ts}  ({files_n} files)  {reason[:80]}")
            except json.JSONDecodeError:
                print(f"  {d.name}  (no manifest)")
        else:
            print(f"  {d.name}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reason", default="manual snapshot", help="why this snapshot was taken")
    ap.add_argument("--list", action="store_true", help="list existing snapshots")
    ap.add_argument("--force", action="store_true", help="overwrite existing snapshot")
    args = ap.parse_args()

    if args.list:
        return list_snapshots()
    return create_snapshot(args.reason, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
