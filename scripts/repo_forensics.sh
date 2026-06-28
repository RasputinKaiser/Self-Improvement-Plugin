#!/usr/bin/env bash
# Thin wrapper around CSI's repo_forensics_lab.py.
# Resolves the latest CSI plugin cache path dynamically, preferring +codex-stamped
# (full build) over bare 0.1.0 (slim). Survives plugin updates.
# Usage:
#   repo_forensics.sh /path/to/repo [--write-set <file>]
# Output: JSON map of entrypoints, imports, tests, risky files, patch boundaries.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <repo-root> [--write-set <file>]" >&2
  exit 2
fi

REPO_ROOT="$1"
shift

CSI_ROOT="$HOME/.codex/plugins/cache/ralto-local/codex-self-improvement"
SCRIPT=""

# Prefer +codex-stamped paths (full build); fall back to any 0.1.0* match
for d in "$CSI_ROOT"/0.1.0+codex.*/scripts/repo_forensics_lab.py; do
  if [ -f "$d" ]; then
    SCRIPT="$d"  # last match wins — latest version
  fi
done

if [ -z "$SCRIPT" ]; then
  for d in "$CSI_ROOT"/0.1.0*/scripts/repo_forensics_lab.py; do
    if [ -f "$d" ]; then
      SCRIPT="$d"
    fi
  done
fi

if [ -z "$SCRIPT" ]; then
  echo "ERR: repo_forensics_lab.py not found under $CSI_ROOT" >&2
  echo "Is the codex-self-improvement plugin installed?" >&2
  exit 3
fi

CSI_SCRIPTS_DIR="$(dirname "$SCRIPT")"

# CSI scripts depend on harness_scope — add scripts dir to sys.path
PYTHONPATH="$CSI_SCRIPTS_DIR:${PYTHONPATH:-}" \
  python3 "$SCRIPT" --cwd "$REPO_ROOT" "$@"