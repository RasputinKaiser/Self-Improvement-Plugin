#!/usr/bin/env python3
"""Patch NCode binary to unblock max effort for GLM 5.2.

Two byte-for-byte patches, both same-length (no offset shifts):

1. Stale effort message text:
   'Opus 4.6 only'  (13 bytes)  ->  'GLM 5.2 works'  (13 bytes)

2. Model profile flag (GLM 5.2 [1M] and GLM 5.2 entries only):
   'supportsMaxEffort: false'   ->   'supportsMaxEffort: 1===1'
   (1===1 evaluates to true in JS, same 5-byte length as 'false')

After patching, /effort max persists AND applies at runtime instead of being
silently downgraded to 'high'. Re-signs adhoc. Idempotent. Backs up before
first mutation.

Usage:
  patch_effort_message.py                  # patches active binary at $(which ncode)
  patch_effort_message.py /path/to/ncode   # patches a specific build
  patch_effort_message.py --check          # read-only: report current state
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

OLD_MSG = b"Opus 4.6 only"
NEW_MSG = b"GLM 5.2 works"

OLD_FLAG = b"supportsMaxEffort: false"
NEW_FLAG = b"supportsMaxEffort: 1===1"

ALIAS_NEEDLE = b"primaryAlias: \""
GLM_ALIASES = (b"glm-5.2[1m]", b"glm-5.2")


def find_binary():
    which = shutil.which("ncode")
    return Path(which).resolve() if which else None


def glm_flag_targets(data):
    """Return byte offsets of supportsMaxEffort: false whose preceding
    primaryAlias is glm-5.2[1m] or glm-5.2."""
    targets = []
    start = 0
    while True:
        idx = data.find(OLD_FLAG, start)
        if idx < 0:
            break
        chunk = data[max(0, idx-800):idx]
        li = chunk.rfind(ALIAS_NEEDLE)
        if li >= 0:
            base = max(0, idx-800) + li + len(ALIAS_NEEDLE)
            alias_end = data.find(b"\"", base)
            alias = data[base:alias_end]
            if alias in GLM_ALIASES:
                targets.append(idx)
        start = idx + 1
    return targets


def patch(binary: Path, dry_run: bool = False) -> int:
    if not binary.exists():
        print(f"ERR: binary not found: {binary}", file=sys.stderr)
        return 2

    data = binary.read_bytes()

    msg_count = data.count(OLD_MSG)
    glm_targets = glm_flag_targets(data)
    already_flag = data.count(NEW_FLAG)

    plan = []
    if msg_count == 0 and NEW_MSG in data:
        plan.append(f"message: already patched")
    elif msg_count == 1:
        plan.append(f"message: patch {OLD_MSG!r} -> {NEW_MSG!r}")
    elif msg_count > 1:
        print(f"ERR: {msg_count} occurrences of {OLD_MSG!r} — expected 1", file=sys.stderr)
        return 4
    else:
        plan.append("message: no match (unexpected)")

    if not glm_targets and already_flag >= 2:
        plan.append(f"GLM flag: already patched ({already_flag} entries)")
    elif glm_targets:
        plan.append(f"GLM flag: patch {len(glm_targets)} entries false -> 1===1")
    else:
        plan.append("GLM flag: no match (unexpected)")

    print("plan:")
    for p in plan:
        print(f"  {p}")

    if dry_run:
        return 0

    backup = binary.with_name(binary.name + ".bak-pre-effort-fix")
    if not backup.exists():
        shutil.copy2(binary, backup)
        print(f"backed up to {backup}")
    else:
        print(f"backup already exists: {backup}")

    if msg_count == 1:
        idx = data.find(OLD_MSG)
        data = data[:idx] + NEW_MSG + data[idx+len(OLD_MSG):]

    for off in sorted(glm_targets, reverse=True):
        false_off = off + len(b"supportsMaxEffort: ")
        assert data[false_off:false_off+5] == b"false"
        data = data[:false_off] + b"1===1" + data[false_off+5:]

    tmp = binary.with_name(binary.name + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o755)
    os.replace(tmp, binary)
    print("patched")

    r = subprocess.run(
        ["codesign", "--force", "--sign", "-", str(binary)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"WARN: re-sign failed: {r.stderr.strip()}", file=sys.stderr)
        return 5
    print("re-signed adhoc")

    r = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERR: post-patch smoke test failed: {r.stderr.strip()}", file=sys.stderr)
        return 6
    print(f"smoke OK: {r.stdout.strip() or r.stderr.strip()}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("binary", nargs="?", help="path to ncode binary (defaults to $(which ncode))")
    ap.add_argument("--check", action="store_true", help="read-only report, no mutation")
    args = ap.parse_args()

    binary = Path(args.binary) if args.binary else find_binary()
    if not binary:
        print("ERR: no binary specified and `ncode` not on PATH", file=sys.stderr)
        return 2
    return patch(binary, dry_run=args.check)


if __name__ == "__main__":
    sys.exit(main())