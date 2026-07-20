# Architecture

## Domain separation

One controller coordinates two graphs without merging their semantics:

```text
TaskSpec -> strict task DAG -> lease/budget -> SliceResult -> GraphReceipt
                              ^                         |
                              | context packet          | candidate lesson
                              |                         v
Memory JSONL -> indexed bounded frontier -> conflict/promotion audit
```

Task edges are scheduler control and must be acyclic. Memory edges are retrieval relationships and may contain cycles, but traversal is bounded. The only bridges are a context packet entering a task and an evidence-linked lesson candidate leaving a completed run.

## Shared primitives

- Canonical JSON: UTF-8, sorted keys, compact separators, and no non-finite numbers.
- Identities: generated run and event IDs use UUIDv7. Attempts, leases, reservations, receipts, and queries use stable, scoped identifiers whose meaning survives replay.
- Digests: SHA-256 over canonical payloads.
- Versions: durable events carry `schema` and `schema_version`; runtime state, migration projections, and receipts carry their applicable version or migration identifiers.
- Provenance: every admitted material claim points to source, command, test, or runtime evidence. Missing, contradictory, or unsupported required proof fails closed.

## Event authority

`events.jsonl` is the run authority. An event contains:

```json
{
  "schema": "sips.runtime.event.v1",
  "schema_version": 1,
  "event_id": "...",
  "run_id": "...",
  "seq": 1,
  "prev_digest": "...",
  "event_type": "run.created",
  "actor": "...",
  "idempotency_key": "...",
  "timestamp": "...",
  "payload": {},
  "payload_digest": "...",
  "event_digest": "..."
}
```

Each transition acquires a per-run `fcntl` mutex, verifies revision and fencing, appends and fsyncs the event, atomically replaces `head.json`, then atomically replaces `snapshot.json`. Lock files are synchronization devices, not state authority.

## Task contract

`TaskSpec` contains ID, description, AND dependencies, acceptance criteria, priority, expected value, estimated tokens, read/write sets, required sources, scoped context query, merge contract, risk tags, required flag, retry limit, and insertion ordinal.

Compilation rejects duplicate or missing IDs, self or unknown dependencies, cycles, path escapes, and invalid merge contracts. Read/read locks are compatible; every overlapping write/read or write/write path conflicts, including ancestor paths.

The deterministic ready order is:

1. priority descending;
2. remaining critical-path weight descending;
3. expected value per token descending;
4. estimated tokens ascending;
5. insertion ordinal ascending;
6. task ID ascending.

## Result and receipt contracts

`SliceResult` binds run, task, attempt, lease, fencing token, plan and context digests, status, claims, artifacts, evidence, changed paths, blockers, usage, and lesson candidate to a stable result hash.

`GraphReceipt` is the immutable truth surface. Human Markdown and MCP structured content are projections of this same receipt. Arrival order cannot affect the receipt hash.

## Memory index

`<store>.graph-index-v1.sqlite3` contains indexed record metadata, scopes, weighted terms, tags, evidence paths, and explicit references. Source inode, size, offset, modification time, and prefix fingerprint are stored in index metadata. Shrinkage, in-place mutation, fingerprint or schema mismatch, or corruption causes a rebuild from JSONL.

The relation priority is explicit reference, shared evidence, shared tag, then shared scope. Defaults are eight seeds, fanout four, depth two, 24 nodes, 80 edges, eight paths, and 4,000 retrieval tokens. The indexed frontier never uses unrestricted all-pairs expansion.
