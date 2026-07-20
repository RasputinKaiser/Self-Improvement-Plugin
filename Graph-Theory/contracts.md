# Runtime contracts

This document is the durable contract index for SIPS graph runtime 0.4.0. The
Python dataclasses and validators under `scripts/sips_runtime/` are executable
authority; examples here describe their stable wire shape.

## Canonical encoding and identity

All hashed values use UTF-8 JSON with sorted object keys and compact
separators. NaN, Infinity, unsupported objects, and non-string object keys are
rejected rather than coerced. Digests are lower-case SHA-256 hex strings.
Generated event identities are UUIDv7 values. A caller-supplied run or task ID
must be a safe stable identifier and cannot contain a path separator, `.` or
`..` path segment, or control characters.

Every write supplies both:

- `idempotency_key`: binds one logical request to one canonical request digest;
- `expected_revision`: an exact non-negative integer matching the verified
  event head.

Booleans and integers are exact JSON types. In particular, `true` is not a
valid revision and the string `"false"` is not a valid activation flag.

## Event

Each line of `events.jsonl` is a `sips.runtime.event.v1` object containing
`schema`, `schema_version`, `event_id`, `run_id`, `seq`, `revision`,
`prev_digest`, `event_type`, `actor`, `idempotency_key`, `timestamp`, `payload`,
`payload_digest`, and `event_digest`. Sequence and revision are exact integers.
The payload digest covers the canonical payload; the event digest covers the
canonical event without its own digest field.

`events.jsonl` plus the atomically replaced `head.json` are authority.
`snapshot.json` is a replayable projection and receipts are immutable derived
artifacts.

## TaskSpec

A task declares:

| Field | Contract |
| --- | --- |
| `id` | Unique stable safe ID. |
| `description` | Human work objective. |
| `dependencies` | AND predecessors that must succeed. |
| `acceptance` | Evidence-bearing completion criteria. |
| `priority` / `expected_value` | Deterministic scheduler inputs. |
| `estimated_tokens` | Positive enforceable model-token reservation. |
| `resource_estimates` | Reservation for every controlled resource dimension; caller values cannot undercut mandatory floors. |
| `read_set` / `write_set` | Canonical paths used for ancestor-aware locks. |
| `required_sources` / `context_query` | Scoped context inputs; never dependency edges. |
| `merge_contract` | Structured fan-in requirements. |
| `risk_tags` | Reviewer-triggering impact classes. |
| `required` | Exact boolean; optional work cannot hold a run open. |
| `retry_limit` | Non-negative retry count; default one. |

Compilation rejects unknown/self dependencies, duplicate IDs, cycles, path
escapes, undeclared write scope, invalid resource reservations, and invalid
merge contracts before work can be leased.

## Lease and budget grant

A `task.leased` event is the journaled dispatch intent. It binds the task,
attempt, owner, lease ID, monotonic fencing token, acquisition and expiry
times, heartbeat deadline, absolute attempt ceiling, context digest, and full
resource reservation. The host may spawn a worker only from this recorded
grant. An expired grant can be reconciled by a later lease with a higher fence;
the abandoned reservation is charged, never silently refunded.

## SliceResult

A non-legacy result contains `run_id`, `task_id`, `slice_id`, `attempt_id`,
`lease_id`, `owner`, `fencing_token`, `plan_digest`, `context_digest`, `status`,
`claims`, `evidence`, `artifacts`, `changed_paths`, `blockers`, `usage`,
`lesson_candidate`, and `result_hash`. Its lease owner and fence must match the
active persisted grant. Changed paths must be a subset of the declared write
scope. A repeated identical result is idempotent; a different result for one
attempt is a conflict.

Every material claim references admitted evidence. Successful evidence needs
an identity, an anchored source, a passed outcome, and a positive case count.
High-impact tasks additionally need a distinct reviewer identity and a
receipt-bound review decision.

The canonical serialized result is measured before the authoritative event is
written. Its measured output-token lower bound and byte size must fit the
persisted `output_tokens` and `memory_bytes` reservations. Unknown resource
keys are rejected rather than dropped.

## GraphReceipt

One immutable `sips.runtime.graph-receipt.v1` object is derived from the event
chain. Its `structured` member is complete machine content. `markdown` is a
bounded projection of the same data: at most 8,000 characters, 12 answer units,
and five representative omissions. The receipt digest covers strict canonical
structured content. Results, claims, artifacts, evidence, conflicts, blocked
work, and omissions are ordered by stable identity and digest, never arrival
time.

## Memory frontier and promotion

The frontier accepts a non-empty bounded scoped query and clamps traversal to eight
seeds, four outgoing candidates per node, depth two, 24 nodes, 80 edges, eight
paths, and 4,000 estimated tokens. Its SQLite file is a rebuildable projection;
Memory Fabric JSONL remains authority. Frontier results record selected IDs,
provenance, omissions, reasons, estimated tokens, index receipt, and applied
limits. Query text, topology evidence, IDs, and omission ledgers have separate
hard envelope bounds. Retrieval-record tokens and the complete serialized
response are both reported, so metadata cannot hide outside accounting.

A fan-in lesson is first recorded as `candidate` with
`verify_before_use=true`. Activation is a distinct side effect bound to the run
and GraphReceipt digest. On every activation attempt, references,
contradictions, supersession, provenance, evidence paths, and usage eligibility
are re-audited against the current target JSONL store. A writer failure records
a failed promotion receipt; it never implies an active memory record.

## API envelope

Read operations are `status`, `plan`, `events`, `receipt`, and `frontier`.
Write operations are `create`, `submit`, `lease`, `advance`, `cancel`, and
`promote`. The CLI and MCP tools route through the same `RuntimeAPI` dispatcher.
Compact responses contain status, revision, and bounded summaries;
`detail=full` exposes the complete immutable receipt.
