# SIPS 0.7.0 — research-informed commands

This release builds on the 0.6 controller and independent evaluator. It adds bounded advisory methods and revises all twelve commands. Optimize remains 0.6.0; its measurements can inform drift analysis without changing acceptance authority.

## Behavior changes

`/improve` now asks which evidence would distinguish explanations before proposing code. Investigations include a cost-bounded diagnostic design; unavailable predictions do not count as distinguishing evidence. `/brainstorm` explores explicit dimensions, incompatible combinations, a no-change control and falsifiable mechanisms. Idea cards request active-task inspection and candidate authorship rather than automatically delegating.

`/verify` can generate feasible interaction cases, but still requires executable oracles and independent original-task/consumer checks. `/teach` distinguishes user instructions, observations, hypotheses and independently verified findings; manual entry does not establish confidence. `/recall` exposes assumptions and invalidation conditions. `/patterns` excludes conflicting outcomes from success rates and missing metrics from metric correlations; correlations do not select a policy. Drift monitoring is advisory.

`/checkpoint` identifies exact snapshots and previews restoration. `/goal` distinguishes objective progress from activation. `/fan-out` and `/escalate` require explicit delegation scope and integration evidence. `/selfloop` stops at review readiness; successful edits are not automatically retained or activated. `/retro` retains evidence-linked lessons, including failed attempts.

Read [the shared command protocol](../references/command-protocol.md) and [method API with runnable requests](../references/research-methods.md). Existing lifecycle, 0.6 contracts and Optimize APIs remain compatible. Historical episodes are not rewritten.

## Interfaces

New MCP `homebase_method(method, request_json)` is read-only. `homebase_adaptation_write(action="analyze", request_json=...)` persists the same receipt through revision-checked lifecycle storage. The adaptation CLI exposes the same action. Existing investigation records gain `diagnostic_design` without changing their state machine.

## Research claims

Runtime tests establish deterministic behavior and boundaries. They do not establish improved task success, causal diagnosis, optimal probe design, novelty, or generalization. New cross-field combinations remain hypotheses. The dated local research dossier includes sources, access limits and proposed experiments; research notes are excluded from installation.
