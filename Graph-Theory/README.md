# SIPS Graph Runtime

SIPS 0.4.0 implements two graph domains behind one controller:

- the **task DAG** is strict execution control;
- the **memory frontier** is bounded retrieval context.

They share identities, canonical hashes, provenance, limits, and receipts. Memory edges never satisfy a task dependency or change scheduler readiness.

## Documents

- [Architecture](architecture.md) defines the domains and invariants.
- [Contracts](contracts.md) defines canonical events, tasks, results, receipts, and public requests.
- [Operations](operations.md) describes scheduling, fan-in, budgets, modes, and promotion.
- [Recovery](recovery.md) documents replay, corruption handling, rollback, and legacy imports.
- [Verification](verification.md) lists the test and proof gates.
- [C0 receipt](receipts/c0-freeze.md) records the dirty-checkout preservation boundary.
- [Source verification receipt](receipts/source-verification.md) records the final source checks and explicit non-claims.

## Objective

The optimization target is verified, non-duplicate answer units per token. Hard integrity, correctness, regression, and resource gates are evaluated before throughput or efficiency.

## Canonical state

Runtime authority lives outside the repository at:

```text
${SIPS_HOME:-~/.codex/sips}/runtime/v1/runs/<run_id>/
  events.jsonl
  head.json
  snapshot.json
  receipts/
  slices/<task_id>/
```

Repository `state.yaml` is a status and proof projection only. Memory Fabric's append-only JSONL remains the memory source of truth; its SQLite graph index is rebuildable.

## Migration status

The release is additive and defaults to `legacy`. The runtime controller, indexed frontier, CLI, and MCP source surfaces are implemented and source-tested. `shadow` is read-only; controller-authoritative `dual` and `runtime` execution remain fail-closed until the structured legacy-result bridge, clean integration, cache parity, rollback rehearsal, and fresh-host MCP rediscovery each have their own proof.
