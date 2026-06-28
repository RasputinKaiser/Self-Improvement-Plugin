#!/usr/bin/env python3
"""Harness restore — restore a known-good snapshot of ~/.ncode/scripts/.

Usage:
  restore_harness.py <hash>      # restore <hash>
  restore_harness.py --latest    # restore most recent snapshot
  restore_harness.py --list       # list available snapshots (same as snapshot --list)
  restore_harness.py <hash> --dry-run
"""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NCODE_DIR = Path.home() / ".ncode"
SCRIPTS_DIR = NCODE_DIR / "scripts"
BACKUP_ROOT = NCODE_DIR / "backups" / "snapshots"


def list_snapshots():
    if not BACKUP_ROOT.is_dir():
        return []
    return sorted(
        (d for d in BACKUP_ROOT.iterdir() if d.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def restore(hash_str, dry_run=False):
    snapshot_dir = BACKUP_ROOT / hash_str
    if not snapshot_dir.is_dir():
        print(f"ERR: snapshot {hash_str} not found", file=sys.stderr)
        return 2

    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERR: missing manifest in {snapshot_dir}", file=sys.stderr)
        return 3

    manifest = json.loads(manifest_path.read_text())

    if dry_run:
        print(f"would restore from {snapshot_dir}")
        print(f"  hash: {manifest.get('hash')}")
        print(f"  reason: {manifest.get('reason')}")
        print(f"  files: {len(manifest.get('files', []))}")
        return 0

    # Take a pre-restore snapshot of current state so we can undo if needed
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pre_restore_dir = BACKUP_ROOT / f"pre-restore-{ts}"
    pre_restore_dir.mkdir(parents=True)
    if SCRIPTS_DIR.is_dir():
        for p in SCRIPTS_DIR.iterdir():
            if p.suffix in (".py", ".sh") and not p.name.startswith("."):
                shutil.copy2(p, pre_restore_dir / p.name)

    # Restore each file from snapshot
    restored = 0
    for entry in manifest.get("files", []):
        name = entry["name"]
        src = snapshot_dir / name
        dst = SCRIPTS_DIR / name
        if not src.exists():
            print(f"WARN: {name} missing from snapshot, skipping", file=sys.stderr)
            continue
        shutil.copy2(src, dst)
        restored += 1

    print(f"restored {restored} files from {snapshot_dir}")
    print(f"pre-restore saved at: {pre_restore_dir}")
    print("recommended: run 'python3 ~/.ncode/scripts/run_tests.py' to verify")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("hash", nargs="?", help="snapshot hash to restore")
    ap.add_argument("--latest", action="store_true", help="restore most recent snapshot")
    ap.add_argument("--list", action="store_true", help="list snapshots")
    ap.add_argument("--dry-run", action="store_true", help="plan only, no mutation")
    args = ap.parse_args()

    if args.list:
        snaps = list_snapshots()
        print(f"snapshots: {len(snaps)}")
        for d in snaps[:10]:
            print(f"  {d.name}")
        return 0

    if args.latest:
        snaps = list_snapshots()
        if not snaps:
            print("no snapshots available", file=sys.stderr)
            return 2
        args.hash = snaps[0].name
        print(f"using latest snapshot: {args.hash}")

    if not args.hash:
        print("ERR: hash required (or --latest)", file=sys.stderr)
        return 2

    return restore(args.hash, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())