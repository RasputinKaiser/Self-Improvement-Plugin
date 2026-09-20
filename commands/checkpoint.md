---
description: Create an identified recovery point and inspect exact restoration differences.
---
Follow `references/command-protocol.md`.

Run `python3 <plugin-root>/scripts/snapshot_harness.py --reason "before: <scope>"`.
Retain the exact snapshot ID, paths covered, workspace/ref, dirty state, and a
continuity packet through the documented compact_continuity.py JSON-stdin hook.
A snapshot only covers its declared files, not the entire machine.

Treat recovery as a transaction: record the before-state identity and intended
writes; preserve user changes made after the snapshot. Inspect
`python3 <plugin-root>/scripts/restore_harness.py <snapshot-id> --dry-run` first.
Use an explicit snapshot ID rather than relying on a moving latest pointer.
Restoration requires the user's authorized exact scope; the dry-run is not a
restoration receipt. Prefer the adaptation controller's journaled rollback for
an explicitly activated candidate.
