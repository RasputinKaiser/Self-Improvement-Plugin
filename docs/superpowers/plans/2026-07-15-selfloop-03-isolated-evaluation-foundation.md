# Selfloop Isolated Evaluation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every required evaluation run from an explicit immutable release root and isolated profile, prove the loaded release, emit complete provenance, and fail closed when no case runs.

**Architecture:** Add protected evaluation contracts and a runtime launcher under `scripts/selfloop_supervisor/`. Every required run begins from P02's verified `ReleaseBundleReceipt`; the launcher supplies its explicit release/profile identities through a sanitized environment and accepts a run only after the runtime emits a matching load receipt. `scripts/eval_harness.py` becomes a mode adapter: legacy invocation remains diagnostic and promotion-ineligible, while `--selfloop-request` uses the isolated runner.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `json`, `subprocess`, `tempfile`, `hashlib`, `pathlib`, pytest 8+.

## Global Constraints

- Normative contract is `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`; advertised conformance remains C0 until P04 completes.
- “Champion and candidate run from explicit isolated release roots and profiles.”
- “Every row has complete release, model, evaluator, case-set, configuration, environment, permission, seed, and budget identity.”
- “Legacy rows with missing provenance MAY be retained for diagnosis and proposal generation. They MUST NOT be used as promotion evidence.”
- “Zero eligible or executed cases is a hard failure for any required gate.”
- “The runner MUST accept an explicit candidate plugin or release root and an isolated runtime/profile directory.”
- “It MUST prove through a runtime receipt which release was loaded. An isolated case `cwd` alone is insufficient.”
- P02 is a hard dependency: a required evaluation resolves the requested release through `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)` and rejects an arbitrary directory, detached `ReleaseIdentity`, manifest-only object, ambiguous attestation, or live-install fallback.
- The evaluated release ID, commit SHA, source-tree digest, manifest digest, install-payload digest, source-attestation digest, path-independent release-bundle receipt digest, and resolved immutable bundle root must all agree before launch.
- Model-sampling seed is separate from case and order seeds; unavailable authoritative model seeding is recorded as `modelSeedControl: unavailable`.
- This plan implements evaluation foundations only. It does not claim reproducible paired comparison, baseline caching, G0-G4, sealed cases, or C3.

---

## File Map

- Create `scripts/selfloop_supervisor/evaluation_contracts.py`: request, identity, row, summary, and validation types.
- Create `scripts/selfloop_supervisor/restricted_process.py`: fail-closed OS sandbox launcher shared by evaluator, candidate, shadow, and meta processes.
- Create `scripts/selfloop_supervisor/runtime_launcher.py`: isolated profile and loaded-release receipt enforcement.
- Create `scripts/selfloop_supervisor/evaluation.py`: case discovery, execution, grading bridge, persistence, and fail-closed summary.
- Create `scripts/eval_harness_legacy.py`: unchanged legacy implementation moved from `eval_harness.py`.
- Modify `scripts/eval_harness.py`: thin legacy/selfloop mode adapter.
- Create `references/selfloop/policies/evaluation-foundation-v1.json`.
- Create `references/selfloop/schemas/evaluation-row-v1.example.json`.
- Create `tests/selfloop/test_evaluation_contracts.py`, `test_runtime_isolation.py`, and `test_evaluation_foundation.py`.
- Create `tests/selfloop/test_restricted_process.py`: real temporary-path denial coverage for the platform sandbox.
- Create `tests/selfloop/test_eval_adapter.py`.
- Modify `tests/selfloop/conftest.py`: complete request, fake runtime, case, and adapter fixtures.
- Modify `scripts/validate_v2.py` and `tests/test_weekly_sweep.py`.

### Task 1: Define and validate complete evaluation provenance

**Files:**
- Create: `scripts/selfloop_supervisor/evaluation_contracts.py`
- Create: `references/selfloop/schemas/evaluation-row-v1.example.json`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_evaluation_contracts.py`

**Interfaces:**
- Consumes: P02 `ReleaseIdentity`, `ReleaseBundleReceipt`, and `ReleaseBundleStore.open_verified(release_id: str, source_attestation_digest: str) -> ReleaseBundleReceipt`.
- Produces: `EvaluationIdentity`, `EvaluationRequest`, `EvaluationRow`, `EvaluationSummary`, `validate_request(request)`, and `classify_historical_row(row)`.

- [ ] **Step 1: Write complete/missing/legacy provenance tests**

```python
def test_complete_request_round_trips(complete_request):
    validate_request(complete_request)
    assert complete_request.identity.model_seed_control == "available"
    assert complete_request.identity.case_seed != complete_request.identity.order_seed

def test_missing_identity_fails_before_runtime(complete_request):
    invalid = replace(
        complete_request,
        identity=replace(complete_request.identity, grader_bundle_sha=""),
    )
    with pytest.raises(ProvenanceError, match="grader_bundle_sha"):
        validate_request(invalid)

def test_legacy_row_is_diagnostic_only():
    result = classify_historical_row({"caseId": "old", "caseVersion": 1, "score": 1.0})
    assert result == {"provenanceComplete": False, "promotionEligible": False, "usage": "diagnostic-only"}
```

- [ ] **Step 2: Run tests and observe the missing contract module**

Run: `python3 -m pytest -q tests/selfloop/test_evaluation_contracts.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement exact immutable request fields**

```python
from collections.abc import Sequence

@dataclass(frozen=True)
class EvaluationIdentity:
    experiment_id: str
    candidate_release_id: str
    champion_release_id: str
    evaluated_release_id: str
    evaluated_role: str
    code_sha: str
    model: str
    model_parameters: dict
    evaluator_version: str
    grader_bundle_sha: str
    case_set_version: str
    configuration_digest: str
    dependency_environment_digest: str
    permission_manifest_digest: str
    case_seed: int
    order_seed: int
    model_seed: int | None
    model_seed_control: str
    budget_policy_id: str

@dataclass(frozen=True)
class EvaluationRequest:
    identity: EvaluationIdentity
    release_identity: ReleaseIdentity
    release_root: Path
    release_root_digest: str
    source_attestation_digest: str
    release_bundle_receipt_digest: str
    profile_root: Path
    cases_dir: Path
    results_path: Path
    runtime_command: Sequence[str]
    permission_manifest: dict
    allowed_environment_keys: tuple[str, ...]
    token_budget: int
    time_budget_seconds: int
    tool_call_budget: int
    memory_budget_bytes: int
```

Validate every field as nonempty, require positive budgets, require `evaluated_role` in `candidate|champion|seed`, and require `modelSeedControl` in `available|unavailable`. Require `identity.evaluated_release_id == request.release_identity.release_id`, `identity.code_sha == request.release_identity.commit_sha`, `release_root_digest == request.release_identity.source_tree_digest`, and source-attestation and release-bundle receipt digests supplied by the verified P02 bundle receipt. Reopen the receipt and require its recomputed path-independent digest to equal `release_bundle_receipt_digest`. Canonically hash `permission_manifest` and require it to equal `identity.permission_manifest_digest`; derive the environment allowlist only from `allowed_environment_keys` named by that manifest. The row schema must also include the release manifest/install/source-attestation/release-bundle-receipt digests, case ID/version, randomized order, actual usage, gate label, score/checks/error, artifact hashes, start/end timestamps, `provenanceComplete: true`, and `promotionEligible: false` until later plans authorize a gate. Extend `tests/selfloop/conftest.py` with `complete_request`, `empty_request`, `one_case_request`, and `request_file`; each fixture materializes and reopens a real P02 release bundle before constructing the request, uses a real one-case JSON file, and uses temporary result/profile paths.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_evaluation_contracts.py`

Expected: all contract tests pass.

```bash
git add scripts/selfloop_supervisor/evaluation_contracts.py references/selfloop/schemas/evaluation-row-v1.example.json tests/selfloop/conftest.py tests/selfloop/test_evaluation_contracts.py
git commit -m "feat(selfloop): define evaluation provenance contract"
```

### Task 2: Launch from an explicit release root and isolated profile

**Files:**
- Create: `scripts/selfloop_supervisor/restricted_process.py`
- Create: `scripts/selfloop_supervisor/runtime_launcher.py`
- Create: `references/selfloop/policies/evaluation-foundation-v1.json`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_restricted_process.py`
- Test: `tests/selfloop/test_runtime_isolation.py`

**Interfaces:**
- Consumes: a validated `EvaluationRequest`, its exact verified `ReleaseBundleReceipt`, and one versioned case.
- Produces: `ProcessLimits(timeout_seconds: float, memory_bytes: int, output_bytes: int, tool_calls: int)`, `RestrictedProcessLauncher.run(command, cwd, readable_roots, writable_roots, denied_roots, environment, limits, input_text=None) -> ProcessReceipt`, `RuntimeLauncher.run(request, case, case_cwd) -> RuntimeExecution`, and load receipt schema `selfloop.runtime.loaded.v1`.
- `ProcessReceipt` has canonical fields `exit_code`, `stdout`, `stderr`, `elapsed_seconds`, `timed_out`, `sandbox_backend_receipt`, `sandbox_policy_digest`, and `artifact_digest`; later plans use these exact names.

- [ ] **Step 1: Write candidate/champion load and unknown-release tests**

```python
def test_distinct_runs_prove_distinct_loaded_releases(runtime_fixture):
    candidate = runtime_fixture.run("release-candidate", "candidate")
    champion = runtime_fixture.run("release-champion", "champion")
    assert candidate.loaded_release_id == "release-candidate"
    assert champion.loaded_release_id == "release-champion"
    assert candidate.profile_root != champion.profile_root

def test_missing_or_mismatched_load_receipt_fails(runtime_fixture):
    with pytest.raises(UnknownLoadedReleaseError):
        runtime_fixture.run("release-expected", "candidate", emitted_release="release-wrong")

def test_real_restricted_process_cannot_read_supervisor_state(restricted_launcher, tmp_path):
    candidate = tmp_path / "candidate"
    supervisor = tmp_path / "supervisor"
    candidate.mkdir()
    supervisor.mkdir()
    secret = supervisor / "ledger-head.json"
    secret.write_text("protected", encoding="utf-8")
    receipt = restricted_launcher.run(
        (sys.executable, "-c", f"from pathlib import Path; print(Path({str(secret)!r}).read_text())"),
        cwd=candidate,
        readable_roots=(candidate,),
        writable_roots=(candidate,),
        denied_roots=(supervisor,),
        environment={},
        limits=ProcessLimits(timeout_seconds=5, memory_bytes=64 * 1024 * 1024,
                             output_bytes=4096, tool_calls=0),
    )
    assert receipt.exit_code != 0
    assert "protected" not in receipt.stdout
```

- [ ] **Step 2: Run tests and observe the missing launcher**

Run: `python3 -m pytest -q tests/selfloop/test_restricted_process.py tests/selfloop/test_runtime_isolation.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement sanitized launch and receipt validation**

Create the profile directory with mode `0700`; require it to be outside the release root. Before sandbox construction, reopen the release through `ReleaseBundleStore.open_verified(request.release_identity.release_id, request.source_attestation_digest)`, require its recomputed `receipt_digest == request.release_bundle_receipt_digest`, require the receipt path to equal `request.release_root.resolve()`, and recheck all manifest, source-attestation, and identity digests. `RestrictedProcessLauncher` uses `/usr/bin/sandbox-exec` on Darwin with a generated profile that permits system runtime reads plus only the verified release/case roots, permits writes only below the isolated profile and case cwd, and explicitly denies supervisor, sealed, live SIPS-home, and host-config roots. The current target host exposes `/usr/bin/sandbox-exec`; if no tested backend exists, required evaluation fails before launch instead of running unsandboxed. Enforce `ProcessLimits` before launch: wall time through a supervisor deadline/terminate/kill sequence, memory through the tested platform resource limit, output through bounded pipes, and tool calls through the broker counter. A limit breach returns a failed `ProcessReceipt` and sealed partial artifacts; it never becomes unknown success. Launch the exact `runtime_command` with case cwd plus environment keys `SIPS_PLUGIN_ROOT`, `SIPS_HOME`, `SELFLOOP_EXPECTED_RELEASE_ID`, `SELFLOOP_EXPECTED_RELEASE_DIGEST`, and `SELFLOOP_RUNTIME_PROFILE`. Pass only fixed runtime keys and the manifest-validated `allowed_environment_keys`; never inherit `PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, credentials, or the live home. Accept exactly one JSON event with schema `selfloop.runtime.loaded.v1`, expected release ID/digest, resolved release root, and resolved profile root. Preserve stdout/stderr artifacts and fail before grading on a missing, duplicate, or mismatched receipt. Add `runtime_fixture` to `tests/selfloop/conftest.py`; it commits a local Python executable into a temporary source release, materializes and seals that P02 bundle, runs the executable from the verified bundle root, echoes the five required environment values as the load receipt, and can deliberately emit a mismatched release ID.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_restricted_process.py tests/selfloop/test_runtime_isolation.py`

Expected: candidate/champion isolation passes and unknown loading fails closed.

```bash
git add scripts/selfloop_supervisor/restricted_process.py scripts/selfloop_supervisor/runtime_launcher.py references/selfloop/policies/evaluation-foundation-v1.json tests/selfloop/conftest.py tests/selfloop/test_restricted_process.py tests/selfloop/test_runtime_isolation.py
git commit -m "feat(selfloop): isolate evaluation runtimes"
```

### Task 3: Execute eligible cases and fail closed on an empty run

**Files:**
- Create: `scripts/selfloop_supervisor/evaluation.py`
- Test: `tests/selfloop/test_evaluation_foundation.py`

**Interfaces:**
- Consumes: `EvaluationRequest`, versioned JSON cases, `RuntimeLauncher`, and existing deterministic grader functions.
- Produces: `EvaluationRunner.run(request) -> EvaluationSummary` and append-only JSONL rows.

- [ ] **Step 1: Write zero-case, full-row, and artifact tests**

```python
def test_required_run_fails_when_no_case_is_eligible(empty_request):
    with pytest.raises(EmptyEvaluationError, match="zero eligible cases"):
        EvaluationRunner().run(empty_request)

def test_executed_row_contains_every_provenance_and_artifact_field(one_case_request):
    summary = EvaluationRunner().run(one_case_request)
    row = json.loads(one_case_request.results_path.read_text(encoding="utf-8"))
    assert summary.eligible_cases == 1 and summary.executed_cases == 1
    assert row["provenanceComplete"] is True
    assert row["loadedReleaseId"] == row["evaluatedReleaseId"]
    assert set(row["artifactHashes"]) == {"stdout", "stderr", "runtimeReceipt"}
```

- [ ] **Step 2: Run tests and observe the missing runner**

Run: `python3 -m pytest -q tests/selfloop/test_evaluation_foundation.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement deterministic discovery, execution, and JSONL persistence**

Discover only valid `*.json` cases with nonempty ID, positive version, prompt, and grading list; invalid files are errors, not silent skips. C1 required mode rejects `llmJudge` checks because the protected model-call budget broker does not land until P05; legacy diagnostic mode may retain them but cannot produce promotion evidence. Sort by case ID, shuffle from `order_seed`, derive a separate cwd per case from `case_seed`, and call `RuntimeLauncher`. Before launch, require an enforceable cap for every usage dimension or fail closed. Charge and record actual tokens, time, tool calls, and memory; an unavailable actual field is recorded as `unknown` and makes the row promotion-ineligible even when a conservative reservation bounded the call. Hash raw artifacts before appending the row with `os.open(request.results_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)`. Raise `EmptyEvaluationError` for zero eligible or zero executed cases.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_evaluation_foundation.py`

Expected: empty runs fail and complete rows pass.

```bash
git add scripts/selfloop_supervisor/evaluation.py tests/selfloop/test_evaluation_foundation.py
git commit -m "feat(selfloop): add fail-closed evaluation runner"
```

### Task 4: Convert `eval_harness.py` into a compatibility adapter

**Files:**
- Create: `scripts/eval_harness_legacy.py`
- Modify: `scripts/eval_harness.py`
- Modify: `scripts/validate_v2.py`
- Create: `tests/selfloop/test_eval_adapter.py`
- Modify: `tests/test_weekly_sweep.py`

**Interfaces:**
- Consumes: a request containing the P02 release ID plus its expected identity, source-attestation, and path-independent release-bundle receipt digests; protected code resolves the actual bundle path.
- Produces: `python3 scripts/eval_harness.py --selfloop-request <request.json>`; no-flag invocation delegates to legacy diagnostic mode.

- [ ] **Step 1: Move the current implementation byte-for-byte into `eval_harness_legacy.py` and add an adapter test**

```python
def test_no_flag_mode_delegates_to_diagnostic_legacy(monkeypatch):
    monkeypatch.setattr(eval_harness_legacy, "main", lambda: 0)
    assert eval_harness.main([]) == 0

def test_selfloop_mode_maps_fail_closed_exit_codes(monkeypatch, request_file):
    monkeypatch.setattr(eval_harness, "run_selfloop", lambda path: (_ for _ in ()).throw(EmptyEvaluationError("zero eligible cases")))
    assert eval_harness.main(["--selfloop-request", str(request_file)]) == 3
```

Extend the fixture for `UnknownLoadedReleaseError` to assert exit 4 and a one-case success fixture to assert exit 0. In `tests/test_weekly_sweep.py`, pin that the existing no-flag weekly call remains diagnostic-only.

- [ ] **Step 2: Implement strict request-file parsing**

Resolve the profile, case, and results paths, reject profile/release overlap, then call `ReleaseBundleStore.open_verified(request.releaseIdentity.releaseId, request.sourceAttestationDigest)` and require its recomputed receipt digest to equal `request.releaseBundleReceiptDigest`, its canonical path to equal the request's asserted release root, and all expected identity/source-attestation digests to match before launching. The request's release-root field is an equality assertion against that protected resolution, not an authority to load an arbitrary directory. Emit one summary JSON object. Do not fall back to the mutable source tree or live installation when `--selfloop-request` is supplied.

- [ ] **Step 3: Run the foundation gate**

Run: `python3 -m pytest -q tests/selfloop tests/test_weekly_sweep.py && python3 scripts/run_tests.py && python3 scripts/validate_v2.py && git diff --check`

Expected: all existing legacy callers remain green; isolated foundation tests pass; advertised conformance remains C0.

- [ ] **Step 4: Commit the evaluation adapter**

```bash
git add scripts/eval_harness.py scripts/eval_harness_legacy.py scripts/validate_v2.py tests/selfloop/test_eval_adapter.py tests/test_weekly_sweep.py
git commit -m "refactor(selfloop): isolate required evaluation mode"
```
