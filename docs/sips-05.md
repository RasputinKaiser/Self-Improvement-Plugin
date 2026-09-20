# SIPS 0.5 — local adaptive core

SIPS connects observation, diagnosis, a bounded work package, isolated candidate editing, paired local evaluation, and explicit review. The active task agent authors candidate changes. No background agent, model swap, scheduled campaign, or automatic activation is introduced.

## Starting an episode

Use `homebase_adaptation_write` with `action` and JSON-encoded `request_json`, or:

```sh
python3 scripts/adaptation.py observe --request-file /absolute/path/request.json
```

An observation request:

```json
{
  "workspace": "/absolute/path/project",
  "task": "Make helper.py output right instead of wrong",
  "allowed_files": ["helper.py"],
  "context_files": ["requirements.txt"],
  "evidence": ["Existing helper prints wrong"],
  "suite": {
    "original": [{"id":"repro","kind":"command","argv":["{python}","helper.py"],"stdout":"right\n"}],
    "regression": [{"id":"consumer","kind":"artifact","path":"requirements.txt","exists":true}],
    "counterexamples": [{"id":"bad-input","kind":"command","argv":["{python}","helper.py","--invalid"],"exit":2,"stdout":""}]
  },
  "fixtures": {},
  "expected_revision": 0,
  "idempotency_key": "unique-observation-key"
}
```

The returned episode identity and revision are required for subsequent writes. Retry the exact same request with its original key after uncertainty; a changed request needs a new key and the current revision. Read with `homebase_adaptation_read` or `adaptation.py show --episode ID --view status|events|diff|evidence|receipt`. Unknown reads do not create state.

`diagnose` records hypotheses. `propose` takes an `intervention` and `rationale` and produces a work package. `build` copies the declared baseline/context files into an isolated candidate directory; edit only its allowed files. `evaluate` compares baseline and candidate with the same frozen suite, fixtures, and evaluator package. Inspect the returned receipt and diff. A passing candidate reaches `ready_for_review`, never `activated`.

Interventions: gather_evidence, refresh_context, repair_interface, reuse, compose, repair_implementation, create_tool, consolidate, stop. Diagnostic/stop proposals do not need code files. Cancel a finished diagnostic episode or request further work explicitly.

Activation requires `action: activate` and `approved_candidate` equal to the reviewed candidate digest, in addition to revision and idempotency fields. User changes since the baseline cause a conflict rather than overwrite. `rollback` requires the same explicit digest and restores the baseline only when target files still match the activated candidate. A journal supports interrupted activation recovery. `recover` preserves interrupted candidates and marks unfinished evaluations unavailable; it does not pretend they passed.

## Evaluation adapters and limits

All three groups—original, regression, counterexamples—must contain executed checks. A missing group is unavailable. Supported adapters:

- `command`: argv array, expected exit, and exact stdout, JSON, or file-content assertions. Exit alone is insufficient.
- `pytest`: argv array of pytest arguments; the evaluator adds a temporary JUnit report and counts executed non-skipped cases. Empty/skipped-only collection is unavailable.
- `contract`: `script` points to a helper with an implemented `.contract.json`.
- `artifact`: relative path plus exists, exact text, or regex pattern assertions.
- `sequence`: relative path containing a JSON list of observed tool names and an `ordered` subsequence requirement.
- `llmJudge`: explicitly unavailable until the active task supplies separately requested model review; no model process is launched.

`{python}`, `{workspace}`, and `{fixtures}` placeholders are expanded by the evaluator. Put independent pytest files in observation fixtures and reference `{fixtures}/test_contract.py`. Candidate-controlled tests are useful evidence, but independent fixtures are necessary for strong acceptance. User-supplied commands and test programs are trusted code; candidate directories are not an OS sandbox.

Defaults: one candidate per episode, two candidate revisions, four composition steps, 120 seconds per command, and 600 seconds for the combined baseline/candidate evaluation budget. Limits are recorded at observation. Exhaustion is unavailable and reviewable. All state/criteria/evaluator identities are preserved. Declared baseline files include permissions as well as bytes. External packages and services still require explicitly recorded dependencies and environment evidence.

Paired baseline failure and candidate success is labeled `paired_improvement`, meaning improvement in this local test comparison, not proof of generalization or causality across future tasks. Intervention memory receipts record unknown effectiveness otherwise, and failed/unavailable attempts remain visible.

## Tool factory and memory

Tool validation executes contract cases. Packaging uses content/environment identity and declared resources; the registry shows contract types, prerequisites, effects, consumers, and whether validation matches current files/environment. Composition considers only currently validated capabilities. Plans still need consumer verification.

`tool_factory.py promote` is an explicit publication into the local helper library; do not run it for a generated candidate without user activation instructions. A single active.json pointer selects the version used by the generated dispatcher. Packaging is not host discovery proof.

Memory retrieval gives unrelated queries zero score and omits invalidated/expired records. Within relevance categories, newer valid evidence is preferred. Transcript activity is recorded as acceptance unknown; edit count and absence of API errors do not establish task success. Unverified outcomes are excluded from success-rate denominators and correlations.

## Migration and host support

Codex is the verified primary host. Existing Claude Code manifests, hooks, and commands remain supported. NCode execution and fallback discovery have been retired. Former binary modification and presence-mirroring entrypoints do not mutate anything; their original source is archived as text. Historical records remain untouched. `legacy_import.py PATH` reads JSONL into explicitly historical/unverified output without writing or activating memory. Old correction episode logs remain read-only; old `accepted` means a historical evaluator claim. Start a new v2 observation to revalidate it.

No global model settings are changed. Existing helpers work directly but require implemented contracts for factory promotion. Existing task-DAG APIs remain available; the adaptation controller reuses their event store, locks, and snapshots.

## Local release

`local_release.py --stage DIR` builds an explicit distribution manifest excluding research notes, transcripts, historical executable text, and temporary candidates. `--install DIR` backs up configuration and cache, installs from the staged local marketplace, extends only the SIPS tool allowlist, compares installed bytes, and probes a fresh direct MCP process. The installer does not schedule work or activate generated repairs.

The recovery directory holds configuration and prior cache bytes plus a restore map. A failed rollout should be restored from those recorded paths without deleting historical versions. A fresh direct MCP process proves the installed server; current desktop-task tool discovery remains separate and may require a new task or application restart. No publication or Git push is part of this procedure.
