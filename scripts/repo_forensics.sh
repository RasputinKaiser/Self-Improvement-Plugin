#!/usr/bin/env bash
# SIPS repo forensics wrapper.
# Usage:
#   repo_forensics.sh /path/to/repo
# Output: JSON map of git state, notable files, write scope, and likely tests.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <repo-root>" >&2
  exit 2
fi

REPO_ROOT="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 - "$PLUGIN_ROOT" "$REPO_ROOT" <<'PY'
import json
import subprocess
import sys

plugin_root, repo_root = sys.argv[1], sys.argv[2]
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "homebase_repo_map",
        "arguments": {"root": repo_root},
    },
}
completed = subprocess.run(
    ["python3", f"{plugin_root}/scripts/harness_homebase_mcp.py"],
    input=json.dumps(request) + "\n",
    cwd=plugin_root,
    capture_output=True,
    text=True,
    timeout=30,
)
if completed.returncode != 0:
    sys.stderr.write(completed.stderr)
    sys.exit(completed.returncode)
payload = json.loads(completed.stdout)
content = payload.get("result", {}).get("content", [])
for item in content:
    if item.get("type") == "text":
        print(item.get("text", ""))
PY
