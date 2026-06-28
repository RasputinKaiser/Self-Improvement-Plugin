#!/usr/bin/env python3
"""Harness garbage collector for ~/.ncode/.

Read-only drift report. Does NOT delete or mutate anything.

Reports:
- Stale backups older than 90 days (suggestion only)
- Orphan presence/cache files not referenced anywhere
- CSI trace artifacts accumulated under ~/.ncode/csi/
- Duplicate settings backups
- Large files that may bloat context
- (optional --deep) CSI host surface audit: plugin drift, broken refs, MCP errors

Usage:
  harness_gc.py                # basic drift report
  harness_gc.py --deep         # adds CSI host surface audit
"""
import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

NCODE_DIR = Path.home() / ".ncode"
CSI_CACHE_ROOT = Path.home() / ".codex/plugins/cache/ralto-local/codex-self-improvement"
STALE_DAYS = 90
LARGE_FILE_BYTES = 512 * 1024  # 512 KB

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--deep", action="store_true", help="add CSI host surface audit")
args = ap.parse_args()


def walk_files(root, max_depth=4):
    for dirpath, dirnames, filenames in os.walk(root):
        depth = Path(dirpath).relative_to(root).parts
        if len(depth) > max_depth:
            dirnames[:] = []
            continue
        for f in filenames:
            yield Path(dirpath) / f


findings = []


def add(level, msg):
    findings.append((level, msg))


now = time.time()
stale_threshold = now - (STALE_DAYS * 86400)

# Stale backups
backups = NCODE_DIR / "backups"
if backups.is_dir():
    for f in walk_files(backups, max_depth=2):
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        if mtime < stale_threshold:
            age_days = int((now - mtime) / 86400)
            add("INFO", f"stale backup ({age_days}d): {f.relative_to(NCODE_DIR)}")

# CSI trace artifacts
csi_dir = NCODE_DIR / "csi"
if csi_dir.is_dir():
    count = 0
    size = 0
    for f in walk_files(csi_dir, max_depth=3):
        try:
            count += 1
            size += f.stat().st_size
        except OSError:
            continue
    if count > 50 or size > 5 * 1024 * 1024:
        add("INFO", f"csi/ has {count} files, {size // 1024}KB — consider archiving")

# Duplicate settings backups
settings_baks = list(NCODE_DIR.glob("settings.json.bak-*"))
if len(settings_baks) > 3:
    add("INFO", f"{len(settings_baks)} settings.json backups — consider pruning old ones")

# Large files anywhere in tree (excluding obvious dirs)
skip_dirs = {"projects", "sessions", "history.jsonl", "tasks", "telemetry", "usage-data", "shell-snapshots", "paste-cache", "vision", "chrome", "file-history"}
for f in walk_files(NCODE_DIR, max_depth=3):
    rel = f.relative_to(NCODE_DIR)
    if rel.parts and rel.parts[0] in skip_dirs:
        continue
    try:
        sz = f.stat().st_size
    except OSError:
        continue
    if sz > LARGE_FILE_BYTES:
        add("INFO", f"large file ({sz // 1024}KB): {rel}")

# Orphan presence mirror not matched by source
src_presence = Path.home() / ".codex" / "csi"
dst_presence = NCODE_DIR / "csi"
if src_presence.is_dir() and dst_presence.is_dir():
    for fname in ("chat-presence.md", "rich-presence.md"):
        src = src_presence / fname
        dst = dst_presence / fname
        if dst.exists() and not src.exists():
            add("WARN", f"orphan mirror: {dst} (source missing)")

for level, msg in findings:
    print(f"[{level}] {msg}")

print(f"\nsummary: {len(findings)} findings (all read-only)")

# Optional deep audit — CSI host surface
if args.deep:
    candidates = sorted(glob.glob(str(CSI_CACHE_ROOT / "0.1.0*/scripts/host_surface_audit.py")))
    # Prefer +codex-stamped (full build) over bare 0.1.0 (slim)
    codex_candidates = [c for c in candidates if "+codex" in c]
    candidates = codex_candidates or candidates
    if not candidates:
        print("\n--deep: host_surface_audit.py not found under CSI cache")
        sys.exit(0)
    script = candidates[-1]
    plugin_root = str(Path(script).parents[1])  # scripts/../ = plugin root
    print(f"\n=== CSI host surface audit ===")
    try:
        r = subprocess.run(
            ["python3", script,
             "--plugin-root", plugin_root,
             "--format", "markdown",
             "--limit", "20"],
            capture_output=True, text=True, timeout=30
        )
        # host_surface_audit may exit nonzero but still emit markdown
        out = r.stdout.strip()
        if out:
            lines = out.split("\n")
            for line in lines[-30:]:
                print(line)
        elif r.stderr.strip():
            print(f"audit failed: {r.stderr.strip()[:300]}")
        else:
            print("audit returned no output")
    except subprocess.TimeoutExpired:
        print("audit timed out after 30s")

sys.exit(0)