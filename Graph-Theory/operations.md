# Operations

## Run lifecycle

1. Create a versioned run with a declared budget profile and task list.
2. Compile and validate the task DAG.
3. Reserve budget and derive ready work.
4. Acquire a fenced lease for a compatible task.
5. Compile a minimum-sufficient context packet.
6. Journal dispatch intent; the host adapter starts the worker.
7. Validate the structured result and journal its receipt.
8. Fan in deterministically after every required task is terminal.
9. Apply evidence and quality gates.
10. Project bounded Markdown and the complete structured receipt.
11. Capture lesson candidates as `verify_before_use`; promote only after audits pass.

## Leases and scheduling

Standard concurrency is two workers. Workers are instructed to heartbeat every 15 seconds; the persisted 90-second lease is the fail-closed heartbeat-loss boundary, and attempts may run at most 900 seconds. Reacquisition increments the fencing token; a stale holder cannot advance state.

Eligibility requires successful predecessors, compatible paths, a valid merge contract, and an enforceable budget reservation. Failed predecessors block descendants unless the run records another terminal policy.

## Budget behavior

The standard profile has 60,000 soft and 120,000 hard model-token bounds with cumulative 30/35/35 tranche release. The first tranche is available at run creation. When an accepted task reservation needs the next tranche, the same immutable `task.leased` event records the prior and newly released tranche before host dispatch; the controller never silently spends past the released limit. Prompt/input, output, retrieval, delegation, tool calls, repair, wall time, and memory bytes are reserved before side effects. Mandatory reservation floors cannot be lowered by task estimates. The serialized context handoff and result are measured against their reservations before dispatch or commit. Provider usage is authoritative when available; otherwise the enforceable reservation is charged. Unknown is never rewritten as zero, and unknown resource identities fail closed.

## Context behavior

Task scope, acceptance criteria, and required sources lead the packet. Memory selection requires a scoped query and defaults to eight records and 4,000 tokens. Superseded, context-only, or `verify_before_use` records are excluded unless requested. Selected and omitted record IDs, reasons, provenance, and token estimates are retained. The complete handoff, including task metadata and omission details, must fit the persisted retrieval/input reservation; optional records and representative omission details are shed deterministically before a required source is allowed to fail closed.

## Fan-in and gates

The runtime accepts only structured results. It validates the active lease, fencing token, and changed-path scope. Identical duplicates are idempotent; a different digest for the same identity is a conflict.

Fan-in sorts task, claim, artifact, and evidence identities. It retains blocked, missing, and conflicting work. Quality is an AND sequence: integrity, correctness, regression bounds, resource identity/caps, and measurable benefit. Missing, contradictory, unknown, or zero-case proof fails closed. Risk tags for permissions, persistence, authentication, money, schema migration, destructive actions, and external writes require an independent reviewer receipt.

## Public surfaces

```text
sips_runtime_read(operation, request_json)
  status | plan | events | receipt | frontier

sips_runtime_write(operation, request_json)
  create | submit | lease | advance | cancel | promote
```

Every write includes `idempotency_key` and `expected_revision`. The CLI mirrors the same operations:

```text
python3 scripts/sips_runtime.py read  --op status --json '{...}'
python3 scripts/sips_runtime.py write --op create --json '{...}'
```

Compact output is the default; `detail=full` returns the complete receipt. The controller grants work but does not spawn agents.

## Campaign spine and child-thread fleet

The campaign fleet is a separate event stream rooted at
`${SIPS_HOME:-$HOME/.codex/sips}/runtime/v1/campaigns/<campaign_id>/`. Its
`events.jsonl` plus `head.json` are authority for campaign metadata; the
rebuildable `projection.json` exposes one foreground child, bounded child
cards, lifecycle counts, recent activity, and archive summaries.

```text
python3 scripts/sips_campaign_fleet.py create <objective> --campaign-id <id>
python3 scripts/sips_campaign_fleet.py attach <id> --child-id <child> --title <title> --thread-id <host-handle>
python3 scripts/sips_campaign_fleet.py status <id> --markdown
python3 scripts/sips_campaign_fleet.py search <thread-or-task-handle>
```

Child states are `planned`, `active`, `waiting`, `blocked`, `completed`,
`failed`, `canceled`, `archived`, and `abandoned`; `archive` is allowed only
after a child has a terminal outcome and removes it from the active foreground
projection without deleting its event history. `reopen` creates a new child
incarnation and leaves the old thread/task binding archived evidence. Writes
require an idempotency key and use the verified campaign revision for
optimistic concurrency. A runtime run may carry
`metadata.campaign_id`; the Goal Board performs a read-only join so the
campaign spine appears beside runtime task state.

This registry deliberately stores external thread/task handles instead of
claiming ownership of the host conversation store. Runtime task events,
leases, and immutable receipts remain authoritative for execution; host
enumeration, visible sidebar state, and actual chat archiving require their own
fresh host proof.

## Compatibility modes

- `legacy`: existing files are authoritative.
- `shadow`: runtime compiles and compares without controlling work.
- `dual`: intended cutover mode in which runtime is authoritative and emits legacy projections.
- `runtime`: intended steady state in which only versioned runtime state is authoritative.

The 0.4.0 source defaults to `legacy`. `shadow` is read-only. The adapters can compile hashed `dual` and `runtime` projections, but execution in those modes currently fails closed because legacy results do not carry the required attempt, lease, fencing, structured-evidence, and resource contracts. Therefore no controller-authoritative compatibility mode is enabled yet. Legacy imports are read-only and bind the raw input hash plus migration ID; historical files are never rewritten.
