---
description: Verify original behavior, interacting failure modes, and consumers with retained executed evidence.
---
Follow `references/command-protocol.md`.

Freeze the original task check, consumer regressions, fixtures, and evaluator.
List relevant failure dimensions (schema, environment, input edge, ordering,
dependency freshness). Use `homebase_method` method `coverage` to propose a
bounded 2-way or 3-way matrix with infeasible assignments declared explicitly.
Supply independent expected results; coverage generation alone is not execution.
Keep required regressions even when the matrix is smaller than the full product.

Run focused behavioral checks, then the required project suite. For SIPS run
`python3 <plugin-root>/scripts/run_tests.py` with an isolated temporary SIPS_HOME,
and the full pytest collection when validating a release. `script_smoke.py` is
a JSON-stdin hook, not a positional file-checking CLI. Use AST parsing for Python
syntax checks and the independent evaluator for behavior.

Record command, exit, collected checks, failures, unavailable checks, and scope.
Use additive counterexamples for newly exposed interactions. Fix or report a
failure without deleting its evidence. Inspect a checkpoint restoration diff
before any explicit restore; do not overwrite a dirty checkout automatically.
