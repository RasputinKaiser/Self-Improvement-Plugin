---
description: Create a bounded correction episode, evaluate an isolated candidate, and present it for review.
---
Use `homebase_adaptation_read` and `homebase_adaptation_write`, or the equivalent `scripts/adaptation.py` CLI described in `docs/sips-08.md`. All writes require the current expected revision and an idempotency key.

Inspect reproducible failures and capability gaps. Preserve evidence and competing hypotheses; missing results are unavailable, and file age/test references are supporting signals. Observe an episode with explicit workspace, allowed/context files, original acceptance checks, consumer regressions, counterexamples, and independent fixtures.

Diagnose, propose the smallest justified intervention, and build an isolated candidate. The active task agent authors edits only in the returned candidate directory. Use the factory registry to reuse or compose validated capabilities before creating another tool. No child agents or model processes are started automatically.

Evaluate with the built-in local adapters, inspect baseline/candidate results and the diff, and stop at ready_for_review. Report rejected or unavailable attempts faithfully. Do not call activate, factory promote, or rollback without the user's explicit instruction naming the reviewed candidate. Record episode and receipt paths in state.yaml and the ledger. Later recurrence is a new observation.

## SIPS 0.6 evidence workflow

Use the shared adaptation controller for structured investigations and bounded probes.
Prefer current v2 contracts and joint-prerequisite composition before new helpers.
Use additive counterexamples; preserve raw episodes when proposing procedures.
Policy trials are declarative proposals, never changes to evaluation or activation.
See `docs/sips-06.md` for request shapes, supported schemas, and research limits.

## Cross-disciplinary method selection

Follow `references/command-protocol.md`. Use diagnosis for indistinguishable
hypotheses, coverage for interacting failure modes, and assumptions for conditional
lessons. Preserve the no-change control, missing evidence, and falsification result.
A method receipt is advisory and cannot replace independent evaluation.

## Resumable foreground loop (0.8)

Read adaptation view `next`. Fulfill that packet with the active task agent,
then submit `advance` with its packet_id, current expected_revision, a unique
idempotency_key, and exactly the required output fields. Re-read next after each
accepted transition. Candidate authorship must identify the agent, declared model
label, change summary and evidence. Inspect review packets and stop; advance
never activates. An interrupted evaluation returns a recovery packet.

For evaluator sensitivity, freeze evaluator_challenge checks with a known-good
control and plausible wrong variants before authorship. A surviving variant is
an evaluator failure; infrastructure errors are unavailable. See docs/sips-08.md.

### Semantic and branching diagnosis (0.9)

Before reusing evidence, inspect the episode's `dependencies` view and resolve
reported drift. Prefer contracts declaring required units, roles and context
identities when similarly shaped values have different meanings. A proposed
`sips.policy.v2` can branch on durable probe outcomes through `policy_trial` with
`target_episode`. Follow `needs_evidence` by gathering the named probe evidence;
`inapplicable` requires refreshed assumptions or diagnosis. Use frozen
`policy_cases` original/regression/counterexample checks before review. See
`docs/sips-09.md`; policy trials remain advisory and do not activate policies.

For a skill/tool opportunity noticed during the current task, use
`skills/sips-in-run-improvement/SKILL.md`. Capture a `notice` with recorded evidence,
then inspect `opportunities`; do not lose the main task or silently widen its scope.
