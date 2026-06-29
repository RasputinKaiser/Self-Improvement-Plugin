#!/usr/bin/env python3
"""branch_session.py — session branching (Tier 5 #5).

Forks an existing NCode session transcript at a specific message UUID into
a new session file. The new session inherits the conversation history up
to (and including) the target message — then diverges. The original
session is untouched.

Usage:
  branch_session.py --source <sid> --at-uuid <uuid> [--project-dir <dir>]
  branch_session.py --source <sid> --at-index <n>  [--project-dir <dir>]
  branch_session.py --list <sid>                   # print messages with UUIDs

Branches land in the same project directory as the source (so NCode finds
them via the Projects navigator). The new SID is a fresh UUID.

The forked transcript preserves:
  - All system/init lines
  - All user/assistant messages up to + including the target
  - Sidechain messages (agent delegation transcripts) belonging to kept msgs

It drops:
  - Everything after the target UUID (the branch point)
  - Orphaned sidechain messages whose parent is no longer in the transcript
"""
import argparse
import json
import os
import sys
import uuid as uuid_mod
from pathlib import Path

NCODE_DIR = Path.home() / ".ncode"
PROJECTS_DIR = NCODE_DIR / "projects"


def find_transcript(source_sid, project_dir=None):
    """Locate the .jsonl file for source_sid.

    If project_dir is given, look there. Otherwise scan all project dirs.
    """
    if project_dir:
        cand = Path(project_dir) / f"{source_sid}.jsonl"
        return cand if cand.exists() else None
    for proj in PROJECTS_DIR.iterdir():
        cand = proj / f"{source_sid}.jsonl"
        if cand.exists():
            return cand
    return None


def load_lines(path):
    """Load transcript lines as list of dicts. Skips unparseable lines."""
    out = []
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def find_branch_index(lines, at_uuid=None, at_index=None):
    """Return the index in `lines` after the branch point.

    - at_uuid: branch after the message with this uuid (inclusive — the target
              message IS copied to the branch).
    - at_index: branch after the nth user/assistant message (0-indexed).
    Returns an index N such that lines[:N] is the branch content.
    """
    if at_uuid:
        for i, l in enumerate(lines):
            if l.get("uuid") == at_uuid:
                return i + 1
        print(f"ERR: uuid {at_uuid} not found in transcript", file=sys.stderr)
        sys.exit(1)
    if at_index is not None:
        # Count user/assistant messages
        count = 0
        for i, l in enumerate(lines):
            t = l.get("type")
            if t in ("user", "assistant"):
                if count == at_index:
                    return i + 1
                count += 1
        print(f"ERR: index {at_index} out of range (only {count} user/assistant msgs)",
              file=sys.stderr)
        sys.exit(1)
    # Default: branch after the last user message
    last_user = -1
    for i, l in enumerate(lines):
        if l.get("type") == "user":
            last_user = i
    return last_user + 1 if last_user >= 0 else 0


def filter_branch(lines, branch_index):
    """Return lines[:branch_index], keeping system/init + messages up to branch.

    Also keeps sidechain messages whose parentUuid is in the kept set.
    """
    kept = lines[:branch_index]
    kept_uuids = {l.get("uuid") for l in kept if l.get("uuid")}
    # Sidechain messages: keep if their parentUuid or their own uuid is in kept set
    # (parent points to the user message that spawned them)
    for l in lines:
        idx = lines.index(l)
        if idx >= branch_index:
            break
    # Already included — sidechains before branch_index are kept by default
    # Sidechains AFTER branch_index whose parent is in kept_uuids → include too
    extra = []
    for l in lines[branch_index:]:
        if l.get("isSidechain") and l.get("parentUuid") in kept_uuids:
            extra.append(l)
    return kept + extra


def cmd_branch(source_sid, at_uuid=None, at_index=None, project_dir=None):
    """Create a branch and print the new SID."""
    source_path = find_transcript(source_sid, project_dir)
    if not source_path:
        print(f"ERR: source transcript not found for sid {source_sid}", file=sys.stderr)
        sys.exit(1)

    lines = load_lines(source_path)
    branch_idx = find_branch_index(lines, at_uuid, at_index)
    branch_content = filter_branch(lines, branch_idx)

    new_sid = str(uuid_mod.uuid4())
    new_path = source_path.parent / f"{new_sid}.jsonl"

    with open(new_path, "w", encoding="utf-8") as fp:
        for l in branch_content:
            fp.write(json.dumps(l) + "\n")

    print(json.dumps({
        "ok": True,
        "newSid": new_sid,
        "sourceSid": source_sid,
        "sourcePath": str(source_path),
        "newPath": str(new_path),
        "branchIndex": branch_idx,
        "originalLineCount": len(lines),
        "branchLineCount": len(branch_content),
    }, indent=2))


def cmd_list_messages(source_sid, project_dir=None):
    """Print each user/assistant message with its UUID and a snippet."""
    source_path = find_transcript(source_sid, project_dir)
    if not source_path:
        print(f"ERR: source transcript not found", file=sys.stderr)
        sys.exit(1)
    lines = load_lines(source_path)
    print(f"session: {source_sid}")
    print(f"file: {source_path}")
    print(f"total lines: {len(lines)}")
    print()
    idx = 0
    for l in lines:
        t = l.get("type")
        if t not in ("user", "assistant"):
            continue
        u = l.get("uuid", "?")
        ts = l.get("timestamp", "")[:19]
        # Extract text snippet
        snippet = ""
        msg = l.get("message", {})
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            snippet = content[:80]
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    snippet = block.get("text", "")[:80]
                    break
        print(f"  [{idx}] {t:9s} {ts} {u[:12]}  {snippet}")
        idx += 1


def main():
    ap = argparse.ArgumentParser(description="Session branching (Tier 5 #5)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_branch = sub.add_parser("branch", help="fork a transcript at a message")
    p_branch.add_argument("--source", required=True, help="source session ID")
    p_branch.add_argument("--at-uuid", help="branch after this message UUID (inclusive)")
    p_branch.add_argument("--at-index", type=int, help="branch after the nth user/assistant msg")
    p_branch.add_argument("--project-dir", help="project directory (auto-detected if omitted)")

    p_list = sub.add_parser("list", help="print messages with UUIDs for branch-point selection")
    p_list.add_argument("--source", required=True, help="source session ID")
    p_list.add_argument("--project-dir")

    args = ap.parse_args()
    if args.command == "branch":
        cmd_branch(args.source, args.at_uuid, args.at_index, args.project_dir)
    elif args.command == "list":
        cmd_list_messages(args.source, args.project_dir)


if __name__ == "__main__":
    main()