#!/usr/bin/env python3
"""Retired binary modification entrypoint. No host binary is inspected or modified."""
import sys
if '--help' in sys.argv or '-h' in sys.argv:
    print(__doc__)
else:
    print('Retired operation: model and host binaries are not modified.', file=sys.stderr)
    raise SystemExit(2)
