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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NCODE_DIR="${HOME}/.ncode"
DEST="${NCODE_DIR}/plugins/marketplaces/harness-local"
MANIFEST="${NCODE_DIR}/.harness.installed.json"

DO_CHECK=0
DO_SNAPSHOT=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) DO_CHECK=1; shift;;
    --no-snapshot) DO_SNAPSHOT=0; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

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