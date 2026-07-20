# Recovery and rollback

## Replay

On open, verify every event sequence, previous digest, payload digest, event digest, head anchor, and run identity. If the event log is valid but the snapshot is missing or mismatched, rebuild the snapshot and atomically replace it.

## Corruption

An invalid chain, non-final malformed line, head mismatch, or conflicting idempotency result blocks writes. Do not truncate or rewrite the original log. Recovery creates a new run from the verified prefix and records the damaged run ID, last valid sequence, last valid digest, source path, and recovery reason.

Recovery is itself idempotent under the destination run lock. A retry may
resume an exact creation-only destination or return an exact completed fork.
Any mismatched creation, provenance payload, extra event, or unexpected
destination material blocks the retry; recovery never guesses or appends to
the damaged source.

## Crash boundaries

- Intent without a result receipt is an incomplete side effect and must be reconciled.
- A durable event with a stale snapshot is repaired by replay.
- A snapshot ahead of the durable head is discarded and rebuilt.
- An expired lease may be reissued with a higher fencing token.
- A stale worker result remains evidence but is not admitted to state.

## Memory index recovery

The SQLite frontier is a projection. If its metadata contract revision, integrity check, source fingerprint, or indexed offset is invalid, close it, rebuild a replacement beside it, then atomically replace it. Non-finite or noncanonical JSONL lines are counted invalid and never indexed. Never modify Memory Fabric JSONL to repair the index.

## Rollback

During the compatibility release, set mode back to `legacy` or `shadow` and replay legacy projections. Keep runtime events, receipts, legacy inputs, and migration receipts. Rollback never deletes evidence.

## Dirty-checkout boundary

The 0.4.0 implementation is developed in the isolated `codex/sips-graph-runtime-v0.4.0` worktree. The original dirty `main` checkout is not stashed, reset, cleaned, or overwritten. Adapter reconciliation occurs only after focused runtime tests pass.
