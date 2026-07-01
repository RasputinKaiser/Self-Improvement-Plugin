#!/usr/bin/env python3
"""Harness garbage collector for ~/.ncode/.

Read-only drift report. Does NOT delete or mutate anything.

Reports:
- Stale backups older than 90 days (suggestion only)
- Orphan presence/cache files not referenced anywhere
- SIPS trace artifacts accumulated under ~/.ncode/sips/
- Duplicate settings backups
- Large files that may bloat context
- (optional --deep) SIPS host surface audit: plugin drift, broken refs, MCP errors

Usage:
  harness_gc.py                # basic drift report
  harness_gc.py --deep         # adds SIPS host surface audit
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sips_paths import harness_home

NCODE_DIR = harness_home()
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STALE_DAYS = 90
LARGE_FILE_BYTES = 512 * 1024  # 512 KB

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--deep", action="store_true", help="add SIPS host surface audit")
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

# SIPS trace artifacts
sips_dir = NCODE_DIR / "sips"
if sips_dir.is_dir():
    count = 0
    size = 0
    for f in walk_files(sips_dir, max_depth=3):
        try:
            count += 1
            size += f.stat().st_size
        except OSError:
            continue
    if count > 50 or size > 5 * 1024 * 1024:
        add("INFO", f"sips/ has {count} files, {size // 1024}KB - consider archiving")

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
src_presence = Path.home() / ".codex" / "sips"
dst_presence = NCODE_DIR / "sips"
if src_presence.is_dir() and dst_presence.is_dir():
    for fname in ("chat-presence.md", "rich-presence.md"):
        src = src_presence / fname
        dst = dst_presence / fname
        if dst.exists() and not src.exists():
            add("WARN", f"orphan mirror: {dst} (source missing)")

for level, msg in findings:
    print(f"[{level}] {msg}")

print(f"\nsummary: {len(findings)} findings (all read-only)")

# Optional deep audit - SIPS host surface
if args.deep:
    script = PLUGIN_ROOT / "scripts" / "harness_homebase_mcp.py"
    print("\n=== SIPS host surface audit ===")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "homebase_host_audit",
            "arguments": {"root": str(PLUGIN_ROOT)},
        },
    }
    try:
        r = subprocess.run(
            ["python3", str(script)],
            input=json.dumps(request) + "\n",
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PLUGIN_ROOT),
        )
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
        content = payload.get("result", {}).get("content", [])
        text = "\n".join(item.get("text", "") for item in content if item.get("type") == "text").strip()
        print(text or r.stderr.strip() or "audit returned no output")
    except subprocess.TimeoutExpired:
        print("audit timed out after 30s")
    except (json.JSONDecodeError, OSError) as exc:
        print(f"audit failed: {exc}")

sys.exit(0)
