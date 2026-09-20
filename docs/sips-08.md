# SIPS 0.8.0 — resumable foreground adaptation

The active task agent remains the author. The controller issues the next bounded
work packet, accepts a revision-checked result, and records the transition. No
coding-model process, child agent, scheduler or activation is launched by advance.

## Work packet protocol

Read `homebase_adaptation_read(episode=..., view="next")` or
`python3 scripts/adaptation.py show --episode EPISODE --view next`.
The `next` object includes packet_id, revision, kind, selected action, fixed inputs,
required output fields, task/evidence, allowed files, candidate path, acceptance
criteria, frozen suite/baseline identities and remaining evaluation budget.

Submit via adaptation write action `advance`:

```json
{"episode":"EPISODE","expected_revision":1,"idempotency_key":"unique-request","packet_id":"PACKET_ID","output":{"hypotheses":[{"id":"implementation","claim":"incorrect output"}],"probes":[]}}
```

Use the actual current packet's required fields. Investigate packets accept
hypotheses/probes; execution packets run their fixed probe; intervention packets
accept intervention/rationale; isolate packets have empty output; author packets
accept authorship and evaluate the existing isolated candidate:

```json
{"authorship":{"agent":"active task agent","model_label":"user-selected; exact slug unavailable","summary":"Describe the authored change","evidence":["executed probe or inspected source reference"]}}
```

Authorship is a declaration. The controller records the actual candidate manifest
and leaves real token usage unknown. It does not verify a model label by trusting
that label. Outputs cannot override the selected action or request controls.
Repeated identical requests return their prior receipt. Stale packets/revisions
and extra output fields fail. A fresh controller reconstructs the next packet
from durable state. An interrupted evaluation/probe must recover before proceeding.

Review, activated and stopped packets have no automatic action. Diagnostic-only
interventions return to investigation without requiring a fabricated code artifact.
Existing explicit lifecycle actions remain available for compatibility.

## Challenge the evaluator

Freeze an `evaluator_challenge` check inside an original/regression/counterexample
group before candidate authorship:

```json
{"kind":"evaluator_challenge","control":{"helper.py":"import sys\nprint(int(sys.argv[1])*2)\n"},"mutants":[{"id":"constant","files":{"helper.py":"print(4)\n"}}],"checks":[{"kind":"command","argv":["{python}","helper.py","2"],"stdout":"4\n"},{"kind":"command","argv":["{python}","helper.py","3"],"stdout":"6\n"}]}
```

The known-good control must pass all checks. Every declared wrong implementation
must fail at least one behavioral assertion. A survivor fails the challenge;
broken controls, unavailable checks, nonzero generic-command exits and pytest
infrastructure errors are unavailable, not successful mutation rejection. All
arms run in disposable copies under the same total check timeout. Bounds: 16
mutants, 16 control files, 32 checks. Mutants can change only control files.
Recursive challenges are unsupported. This tests oracle sensitivity to declared
faults; it does not prove that the evaluator is complete. Execution is for trusted
local fixtures and is not an OS sandbox. Original task checks are still required.

## Later-use evidence

`link_outcome` appends a linked authored evaluation to an exact reviewed source:

```json
{"episode":"SOURCE_EPISODE","expected_revision":7,"idempotency_key":"later-use-1","source_candidate":"EXACT_DIGEST","target_episode":"TARGET_EPISODE","task_identity":"matched-task-1","memory_mode":"procedure"}
```

Modes are none, episodic, procedure. The controller reads the target's executed,
content-pinned receipt; it does not accept caller-supplied pass/fail summaries.
Source/target artifacts, evaluator, criteria, fixtures and candidate identities
must remain current. Self-links, duplicate target episodes and duplicate matched
arms are rejected. Maximum 128 linked uses. Unavailable targets stay unavailable.

Read `outcomes` for complete/incomplete three-arm groups, observed gains, negative
transfer, unavailable groups and evaluation seconds. Matching and memory mode are
caller declarations. These are descriptive observations, not randomized causal
comparisons. Missing comparison arms leave effectiveness unmeasured. Evaluation
time excludes unobserved host reasoning time; billing tokens remain unknown.

## Compatibility and measured scope

Old episodes remain readable; new evaluated episodes pin receipt digests. Later-use
links require new pinned receipts and author declarations. All existing 0.7 methods,
0.6 contracts, promotion protections and exact-candidate activation remain.

The local 0.8 trial replays an actual 0.7 attribution defect, authors an isolated
repair, packages an executable conditional procedure, and evaluates a fresh related
instance. Cases are visible to the author. This establishes workflow execution
and observed paired outcomes, not independent transfer or comparative agent gains.
Versioned branching policies, learned selection and automatic rollout remain later
work. Release evidence and trial records are local in docs/sips-08-release.md and
.local-release/evidence/0.8; private research/trials are excluded from installation.
