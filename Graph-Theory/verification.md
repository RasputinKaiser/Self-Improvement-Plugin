# Verification

## Runtime contracts

- Canonical serialization is deterministic and rejects non-finite numbers.
- DAG compilation rejects duplicates, missing dependencies, self edges, and cycles.
- Ready order and fan-in hashes are invariant to input and completion order.
- Path conflicts include equal, ancestor, and descendant paths.
- Lease expiry and monotonic fencing reject stale writers.
- Budget reservation and reconciliation fail closed when no enforceable bound exists.
- Event replay verifies every sequence and digest; snapshots rebuild only from a valid log.

## Context, output, and learning

- Context packets apply trust/status filters, enforce record/token caps, and explain omissions.
- Every admitted material claim has evidence; missing or unsupported required proof fails closed and remains visible in the receipt.
- Missing slices, duplicate conflicts, blocked work, contradictions, and zero-case proof remain visible.
- Markdown remains at most 8,000 characters with at most 12 answer units and five representative omissions.
- Lessons begin as candidate plus `verify_before_use`; promotion requires evidence, provenance, confidence, and clean conflict audits.

## Memory frontier

- JSONL remains authoritative through incremental indexing and rebuilds.
- Indexed joins preserve relation priority and deterministic edge hashes.
- Traversal respects seed, fanout, depth, node, edge, path, and token caps, including cyclic graphs.
- The indexed path handles 1,000 or more records without invoking the legacy quadratic pair builder.

## Compatibility and interfaces

- MCP read/write tools and CLI operations return the same schemas and revisions.
- Writes require an idempotency key and expected revision.
- Legacy imports do not mutate their inputs.
- `legacy` and read-only `shadow` preserve historical inputs and hashes.
- Controller-authoritative `dual`/`runtime` execution remains a cutover gate until structured legacy-result bridging, parity receipts, and rollback rehearsal pass.

## Required commands

```text
python3 -m pytest -q tests/test_sips_runtime_core.py
python3 -m pytest -q tests/test_sips_runtime_execution.py tests/test_sips_runtime_cli.py
python3 -m pytest -q tests/test_sips_memory_frontier.py
python3 scripts/run_tests.py fan_out --verbose
python3 scripts/memory_fabric_benchmark.py
python3 scripts/run_tests.py homebase_mcp --verbose
python3 -m pytest -q
python3 scripts/validate_v2.py --check-eval
python3 -m compileall -q scripts tests
```

Source success is not installed-cache or live-host success. Cache parity, configuration, child-process tool listing, and fresh-task MCP callability are reported independently.
