#!/usr/bin/env python3
"""Probe hook — emits a unique marker every invocation.

Used to verify hook stdout reaches agent context. Writes a marker to
/tmp/hook_probe.log AND JSON to stdout. If the marker appears in agent
context, the channel works. If it only appears in the log file, hooks
run but their output isn't surfaced.
"""
import json
import os
import sys
import time
from pathlib import Path

LOG = Path("/tmp/hook_probe.log")
MARKER = f"PROBE_{int(time.time())}"

# Probe marker
PROBE_TRIGGER = "edit_test_v1"
try:
    with open(LOG, "a") as f:
        f.write(f"{MARKER} hook_event=priority_button\n")
except OSError:
    pass

# Emit JSON — this is what NCode should inject as additionalContext
sys.stdout.write(json.dumps({
    "additionalContext": f"[PROBE] hook fired; marker={MARKER}"
}))
sys.stdout.flush()