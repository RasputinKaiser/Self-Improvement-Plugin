#!/usr/bin/env bash
# install.sh — surface harness-self-improvement into the live NCode tree.
#
# Copies the latest source tree from this repo into:
#   ~/.ncode/plugins/marketplaces/harness-local/
#
# Before any copy, takes a snapshot via snapshot_harness.py so the previous
# installed state is rollback-able. Writes ~/.ncode/.harness.installed.json
# with a manifest the harness-app reads for drift detection (Phase 4).
#
# Usage:
#   ./install.sh                     # uses ~/.ncode paths
#   ./install.sh --check             # print drift, no mutation
#   ./install.sh --no-snapshot       # skip pre-install snapshot (DISCOURAGED)
#   ./install.sh --install-cron      # write launchd plist for weekly sweep + load it
#   ./install.sh --uninstall-cron    # unload + delete the launchd plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NCODE_DIR="${HOME}/.ncode"
DEST="${NCODE_DIR}/plugins/marketplaces/harness-local"
MANIFEST="${NCODE_DIR}/.harness.installed.json"
LOGS_DIR="${NCODE_DIR}/logs"
PLIST_LABEL="com.rasputinkaiser.ncode-sweep"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

DO_CHECK=0
DO_SNAPSHOT=1
DO_CRON_INSTALL=0
DO_CRON_UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) DO_CHECK=1; shift;;
    --no-snapshot) DO_SNAPSHOT=0; shift;;
    --install-cron) DO_CRON_INSTALL=1; shift;;
    --uninstall-cron) DO_CRON_UNINSTALL=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

# Cron-only operations: short-circuit before the install path.
if [ "$DO_CRON_UNINSTALL" -eq 1 ]; then
  echo "=== uninstalling launchd plist ==="
  if launchctl list "$PLIST_LABEL" &>/dev/null; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo "  unloaded $PLIST_LABEL"
  else
    echo "  not loaded — skipping unload"
  fi
  if [ -f "$PLIST_PATH" ]; then
    rm "$PLIST_PATH"
    echo "  deleted $PLIST_PATH"
  else
    echo "  no plist at $PLIST_PATH"
  fi
  exit 0
fi

# If --install-cron alone (no other install step), still write the plist now.
if [ "$DO_CRON_INSTALL" -eq 1 ] && [ "$DO_CHECK" -eq 0 ]; then
  mkdir -p "$LOGS_DIR"
  mkdir -p "$(dirname "$PLIST_PATH")"
  WEEKLY_SWEEP="${NCODE_DIR}/scripts/weekly_sweep.py"
  if [ ! -f "$WEEKLY_SWEEP" ]; then
    echo "ERR: weekly_sweep.py not installed at $WEEKLY_SWEEP" >&2
    echo "     run install.sh (without --install-cron) first" >&2
    exit 1
  fi
  # Schedule: Mon 9:17 AM local time (matches CLAUDE.md "Weekly self-improvement cron")
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>${WEEKLY_SWEEP}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>17</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${LOGS_DIR}/sweep.log</string>
  <key>StandardErrorPath</key>
  <string>${LOGS_DIR}/sweep.err.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
PLIST
  # Unload if previously loaded, then load fresh
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
  launchctl load "$PLIST_PATH" 2>/dev/null
  if launchctl list "$PLIST_LABEL" &>/dev/null; then
    echo "=== weekly sweep cron installed ==="
    echo "  plist: $PLIST_PATH"
    echo "  schedule: Mon 9:17 AM local"
    echo "  logs:    $LOGS_DIR/sweep.log + sweep.err.log"
    echo "  to test now: launchctl start $PLIST_LABEL"
    echo "  to remove:   install.sh --uninstall-cron"
  else
    echo "ERR: launchctl load failed" >&2
    exit 1
  fi
  exit 0
fi

cd "$SCRIPT_DIR"

# Pre-install snapshot for rollback safety (skip during --check)
if [ "$DO_CHECK" -eq 0 ] && [ "$DO_SNAPSHOT" -eq 1 ] && [ -d "$DEST/scripts" ]; then
  echo "=== pre-install snapshot ==="
  python3 "${NCODE_DIR}/scripts/snapshot_harness.py" \
    --reason "pre-install via install.sh" || true
fi

if [ "$DO_CHECK" -eq 1 ]; then
  python3 - "$MANIFEST" "$SCRIPT_DIR" <<'PY'
import json, os, sys, subprocess

manifest_path, source_dir = sys.argv[1], sys.argv[2]

if not os.path.exists(manifest_path):
    print("NO_MANIFEST: install.sh has never been run")
    sys.exit(2)

manifest = json.load(open(manifest_path))
source_commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=source_dir
).decode().strip() or "unknown"

installed_commit = manifest.get("commit", "?")
if installed_commit != source_commit:
    print(f"DRIFT_COMMIT: installed={installed_commit[:8]} source={source_commit[:8]}")
    sys.exit(1)

# Per-file drift
drift = 0
for rel in sorted(os.listdir(os.path.join(source_dir, "scripts"))):
    src = os.path.join(source_dir, "scripts", rel)
    if not os.path.isfile(src): continue
    import hashlib
    src_hash = hashlib.sha256(open(src, "rb").read()).hexdigest()
    entry = next((f for f in manifest["files"] if f["path"] == f"scripts/{rel}"), None)
    inst_hash = entry["sha256"] if entry else "MISSING"
    if src_hash != inst_hash:
        print(f"  CHANGED scripts/{rel}  installed={inst_hash[:8]} source={src_hash[:8]}")
        drift = 1
if drift == 0:
    print(f"OK: in sync at commit {source_commit[:8]}")
    sys.exit(0)
sys.exit(1)
PY
  exit $?
fi

echo "=== installing to $DEST ==="
mkdir -p "$DEST"
rsync -a --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  --exclude='*.tmp' \
  "${SCRIPT_DIR}/" "${DEST}/"

# Write a manifest the harness-app reads for drift detection
echo "=== writing manifest ==="
python3 - "$MANIFEST" "$SCRIPT_DIR" <<'PY'
import json, os, sys, subprocess, hashlib

manifest_path, source_dir = sys.argv[1], sys.argv[2]

commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=source_dir
).decode().strip() or "unknown"
branch = subprocess.check_output(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=source_dir
).decode().strip() or "unknown"

def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

hooks_h = sha256_file(os.path.join(source_dir, "hooks/hooks.json"))
mp_h = sha256_file(os.path.join(source_dir, ".ncode-plugin/marketplace.json"))
pj_h = sha256_file(os.path.join(source_dir, ".codex-plugin/plugin.json"))

manifest = {
    "commit": commit,
    "branch": branch,
    "installedAt": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
    "hooksSha256": hooks_h,
    "marketplaceJsonSha256": mp_h,
    "pluginJsonSha256": pj_h,
    "files": [],
}
for f in sorted(os.listdir(os.path.join(source_dir, "scripts"))):
    p = os.path.join(source_dir, "scripts", f)
    if not os.path.isfile(p): continue
    manifest["files"].append({"path": f"scripts/{f}", "sha256": sha256_file(p)})

os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
open(manifest_path, "w").write(json.dumps(manifest, indent=2))
print(f"wrote {manifest_path} ({len(manifest['files'])} files, commit {commit[:8]})")
PY

echo "=== done ==="
echo "run /reload-plugins in NCode to pick up any new hooks"