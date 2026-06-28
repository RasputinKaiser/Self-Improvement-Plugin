---
description: Snapshot the harness and write a continuity packet. Safe point before risky work.
---
Create a safe point before any risky/self-modifying work:

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/snapshot_harness.py --reason "before: $ARGUMENTS"`
2. Write a continuity packet capturing the current objective and changed files so
   the state survives a compaction or a botched edit:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compact_continuity.py` (fed the current
   session/transcript context).
3. Print the snapshot hash and the continuity packet path. If anything regresses,
   restore with: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/restore_harness.py --latest`.

This is the proactive variant of the autonomy gate's snapshot-on-self-edit
behavior — call it before a batch of edits, not just before a single one.
