# SIPS 0.6: transferable adaptation research infrastructure

SIPS 0.6 extends the 0.5 controller. Existing lifecycle calls and historical
receipts remain readable. New generated artifacts remain proposals until exact
candidate activation. The active task authors all candidates; no model process
or background trial is launched. Codex is the verified host; Claude manifests
remain synchronized but live Claude execution is not claimed.

## Investigation API

The CLI `python3 scripts/adaptation.py ACTION --request-file request.json` and
`homebase_adaptation_write(action, request_json)` share one controller. Every
write includes episode, expected_revision, and a unique idempotency_key.

- `investigate`: hypotheses objects with unique id/claim and probes with id,
  independent check, predictions mapping each hypothesis to passed/failed/
  unavailable, positive cost_seconds, and boolean reversible. Ranking is an
  explicit discrimination/cost heuristic, not a probability or causal estimate.
- `probe`: name a proposed probe. Execute against an isolated baseline copy.
  Retain command, inputs, environment, check results, output identity, duration,
  and supporting/contradicting hypotheses. Unavailable evidence supports none.
- `reduce`: name a probe and input string. The predicate's argv must contain a
  literal `{input}` argument. A passing predicate means the failure reproduced.
  Deterministic chunk deletion runs at most 32 checks within the episode budget.
- `conclude`: outcome insufficient_evidence, environment_unavailable, stop, or
  intervention_selected, with rationale. No code artifact is necessary.
- `add_counterexamples`: append checks to a new suite epoch. Original suites and
  evaluation receipts remain intact. Baseline and candidate are both reevaluated;
  earlier review readiness is invalidated. An existing open candidate is required.
- `compose`: available and required named structural schemas; prerequisites and
  dependencies are explicit arrays. The current validated registry supplies tools.
  Compilation caches are content-addressed; consumer evaluation is never cached
  into an acceptance result.

Reads support status/events/evidence/receipt/diff plus investigation, lineage,
and procedures. Procedure retrieval takes query and context (CLI request JSON;
MCP query and context_json). Reads create no directories or events.

## Factory contracts and evaluation

Tool contract v2 replaces input/output string lists with named structural schemas,
adds input bindings and dependencies, and represents effects as reads/writes.
Resources include every declared dependency. Cases and consumer relationships
remain mandatory promotion evidence. Version 1 direct helpers remain supported.

The supported schema subset is type, properties, required, additionalProperties,
items, enum, and schema_version. Unsupported constraints fail closed; there is
no implicit coercion. Planning uses backward producer search and cost-ordered
forward validation. All prerequisites are conjunctive. Ambiguous bindings,
write conflicts, missing dependencies, stale validation, and cycles fail closed.
Declared working-directory writes are checked during contract validation. This
is trusted-code fixture isolation, not an OS sandbox or proof of all read effects.

New local evaluator kinds:

- property/metamorphic: bounded integer generator (min/max), explicit seed,
  1–64 samples, argv with `{input}`, and identity or idempotent relation.
  These are deliberately narrow, independently stated invariants.
- transfer: an external frozen fixture consumer receives --memory-mode none,
  episodic, and procedure in isolated copies. Record all arms with task_family,
  split held_out, and instance_digest. A paired task improvement is not proof
  of cross-family transfer or independent holdout sealing.

## Procedures and policy candidates

Create declarative JSON artifacts under sips-artifacts/policy/ or
sips-artifacts/procedure/ in the candidate workspace. The episode's allowed_files
must contain exactly that artifact. Register it using `artifact` with kind/path.
Evaluation and exact-digest activation/rollback use the existing lifecycle.

Policy schema sips.policy.v1 supports diagnosis/proposal/retrieval only, with
version, inputs, outputs, scope, description, and bounded 0–10 weights. It cannot
encode evaluator, permissions, activation, or budget changes. `policy_trial`
ranks caller-supplied normalized features against a uniform-weight ranking.
It also records a fixed reflection-baseline protocol for the active task agent;
that protocol remains unmeasured until executed in matched foreground trials.
Neither the ranking nor the protocol is an empirical effectiveness result.

Procedure schema sips.procedure.v1 requires version, task, applicability,
actions, bindings, expected_evidence, failure_modes, sources, valid_until,
and negative_contexts. Sources pin episode/revision/event_digest. Original
history remains immutable. Retrieval excludes invalid sources, expired records,
failed applicability, negative contexts, and zero-overlap matches. Motifs
normalize variable names while retaining action order and binding relationships.
Raw episodes and failed attempts remain available even after consolidation.

Lineage retains candidates and their evaluation receipts; the Pareto projection
uses recorded pass/fail, checks, cost, and file count. These are local metrics,
not learned causality or calibrated utility. Unsupported measurements stay unknown.

## Research and release boundaries

The public synthetic pilot has 24 tasks: 16 development and eight held-out
labels across four root-cause families. Since definitions are visible during
implementation, independent transfer claims require fresh hidden instances.
`research_pilot.py` runs deterministic runtime checks only, never model authorship.
Frozen 0.5 is retained locally. Module absence in that baseline is unavailable
measurement, not evidence that a candidate improved an original task.

Neural hash grids, model training, embeddings, and LSH indexes are not production
dependencies. Exact content hashes and structural workflow motifs are implemented.
The research notes record why continuous neural hash grids require a separate
representation and held-out utility experiment.

Default limits remain one active candidate, two revisions, four composition
steps, 120 seconds per evaluator command, and ten minutes per episode including
probes. Updates remain local. See docs/sips-06-release.md in the source workspace
for release evidence and installation proof boundaries.
