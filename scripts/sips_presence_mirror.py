#!/usr/bin/env python3
"""Mirror SIPS presence files from <cwd>/.codex/sips/ to <cwd>/.ncode/sips/.

Replaces the inline python3 -c hook in settings.local.json. Silent on
any failure — never blocks.
"""
import json
import os
import shutil
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = (payload.get("cwd") if isinstance(payload, dict) else None) or os.getcwd()
    src = os.path.join(cwd, ".codex", "sips")
    dst = os.path.join(cwd, ".ncode", "sips")
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for f in ("chat-presence.md", "rich-presence.md"):
        s = os.path.join(src, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(dst, f))


if __name__ == "__main__":
    main()
    sys.exit(0)
