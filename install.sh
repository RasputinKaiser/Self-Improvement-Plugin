#!/usr/bin/env bash
# Stage or explicitly install a verified local SIPS release.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/scripts/local_release.py" "$@"
