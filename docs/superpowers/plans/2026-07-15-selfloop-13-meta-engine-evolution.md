# Selfloop Meta Engine Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete C5 by comparing stable and proposed evolvable selfloop engines on identical historical replays, then promoting a better proposed engine only after the old pinned supervisor produces and persists a real G0-G5/C4 proof chain.

**Architecture:** Evolvable engine code lives only in `scripts/selfloop_strategy/` and returns bounded proposal/artifact identifiers over a strict JSON protocol. Protected `scripts/selfloop_supervisor/meta/` code binds each launch to verified immutable engine/champion `ReleaseBundleReceipt` handles, a replay capsule, and a single-use budget grant under one controller `MutationSession`; journals every phase; seals raw artifacts; materializes candidate releases; composes the real Plan 09-12 APIs from the old supervisor bundle; and commits C5 from verified ledger references rather than caller objects.

**Tech Stack:** Python 3.10+, standard-library dataclasses/hashlib/json/pathlib/subprocess/sqlite3, protected ledger and gate APIs from Plans 05 and 09-12, P03 OS-enforced sandbox, pytest 8+.

## Global Constraints

- Contract: `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- `scripts/selfloop_supervisor/**`, sealed cases, replay selection, evaluator, acceptance policy, meter, ledger, champion pointers, and rescue build remain protected and execute from the old pinned supervisor bundle.
- After source tests pass, the active P12 controller must TTY-authorize, prepare, and activate the exact P13 protected release through the roadmap's rollover checkpoint. The now-active P13 supervisor is the fixed "old supervisor" for subsequent stable-versus-proposed strategy comparisons; C5/status checks require its fresh-loader receipt and never execute protected meta code from the mutable source tree.
- Candidate-evolvable engine diffs are restricted to `scripts/selfloop_strategy/**`; complete release bundles still contain the supervisor subtree, but its digest must exactly match the old pinned supervisor source digest.
- META opens only after five accepted stable SIPS improvements since the most recent terminal meta-evaluation event or three completed generations without a G4 winner since that same event.
- A completed stable/proposed pair receives identical replay inputs, champion release/source-attestation/bundle-receipt digests, task-family distribution, model identity, permission manifest, case/order seeds, seed set, and grant terms. Its sides receive distinct single-use grant IDs because one grant cannot be spent twice. Under the pinned stop-after-first-terminal-failure policy, a reconciled failed stable side ends the attempt without authorizing or claiming a proposed launch. Any root path is derived from a verified bundle handle and is never authority.
- An engine result contains only replay/request/engine IDs plus bounded proposal, proposal-artifact, and reused-failure IDs. It cannot mint candidate release IDs, claim artifact digests, report authoritative usage, or name protected paths.
- The old pinned supervisor resolves proposal artifacts, materializes candidate releases, evaluates both engines' produced candidates, and subjects the proposed engine release itself to the real P09-P12 G0-G5/C4 path.
- Every external side effect has a ledger intent before execution and a completed phase receipt afterward. All mutation-capable work originates in a live lock-owning P05 `MutationSession` and consumes a scoped single-use capability per phase. Recovery verifies input and artifact digests, reuses completed raw process/gate/install/probation receipts, and resumes only the first incomplete phase through a controller-authorized recovery session.
- Every engine launch is reconciled exactly once, including nonzero exit, timeout, malformed output, and recovery. Missing authoritative usage charges the full protected reservation before the result may fail.
- C5 is a persisted, hash-linked ledger receipt over the exact replay, metrics, decision, G0-G5, C4, sandbox, usage, raw-artifact, old-supervisor, old-policy, old-evaluator, and spec digests. Hash-shaped strings or caller booleans are not proof.
- Unit tests may use deterministic temporary roots and clocks for local behavior. The C5 acceptance validator must execute the real P03 sandbox and real P09-P12 ledger-backed APIs in a temporary Git root; it cannot construct synthetic gate rows, fake C4/G5 objects, or mutate a live campaign, sealed store, configuration, or install.

---

### Task 1: Freeze the bounded engine protocol and identity-bound launcher

**Files:**
- Create: `scripts/selfloop_strategy/engine.py`
- Create: `scripts/selfloop_supervisor/meta/engine_protocol.py`
- Create: `scripts/selfloop_supervisor/meta/raw_process.py`
- Test: `tests/selfloop/test_meta_engine_protocol.py`

**Interfaces:**
- Consumes: P02 `ReleaseBundleReceipt`/`ReleaseBundleStore.open_verified`, P03 `RestrictedProcessLauncher`, P05 controller-owned `MutationSession`/`MutationCapability`, P05 `BudgetGrant`, immutable replay-capsule artifact, and the old pinned supervisor-source subtree digest.
- Produces: `MetaEngineRequest`, `MetaEngineResult`, `validate_engine_result(raw, request, allowed_failure_ids) -> MetaEngineResult`, `RawProcessCapture.run_or_load(operation_id, launch) -> ProcessReceipt`, and session-bound `EngineLauncher.run(engine_bundle, champion_bundle, request, grant, operation_id) -> EngineRunReceipt`.
- `EngineRunReceipt` carries the validated result when available, raw stdout/stderr/process/sandbox artifact digests, request/comparison/grant-terms digests, and structured failure. A launched process always returns a receipt; callers reconcile usage before calling `require_success()`.

- [ ] **Step 1: Write failing strict-schema, identity-binding, and raw-capture tests**

```python
def test_result_contains_only_bounded_ids(meta_request, allowed_failure_ids):
    raw = json.dumps({
        "schema": "selfloop.meta-engine-result.v1",
        "replayId": meta_request.replay_id,
        "requestDigest": meta_request.request_digest,
        "engineReleaseId": meta_request.engine_release_id,
        "proposalIds": ["proposal-1"],
        "proposalArtifactIds": ["artifact-1"],
        "reusedFailureIds": ["failure-2"],
    })
    result = validate_engine_result(raw, meta_request, allowed_failure_ids)
    assert result.proposal_ids == ("proposal-1",)
    assert result.proposal_artifact_ids == ("artifact-1",)


@pytest.mark.parametrize("forbidden", ("candidateReleaseIds", "artifactDigest", "actualTokens", "sealedRoot"))
def test_result_rejects_authoritative_or_protected_fields(meta_request, allowed_failure_ids, forbidden):
    payload = valid_result_payload(meta_request)
    payload[forbidden] = [] if forbidden.endswith("Ids") else "untrusted"
    with pytest.raises(EngineProtocolError, match="unknown result fields"):
        validate_engine_result(json.dumps(payload), meta_request, allowed_failure_ids)


def test_launcher_reopens_exact_engine_and_champion_bundle_bytes(
    launcher, engine_bundle, champion_bundle, meta_request, grant,
):
    receipt = launcher.run(
        engine_bundle, champion_bundle, meta_request, grant,
        "meta-7:stable:launch",
    )
    assert receipt.result.engine_release_id == engine_bundle.release_identity.release_id
    tamper_immutable_bundle(champion_bundle.path)
    with pytest.raises(ReleaseBundleMismatch, match="champion bundle"):
        launcher.run(
            engine_bundle, champion_bundle, meta_request, grant,
            "meta-7:changed-champion:launch",
        )


def test_launcher_accepts_no_caller_root_paths(launcher, meta_request, grant):
    with pytest.raises(TypeError):
        launcher.run(
            Path("/caller/engine"), Path("/caller/champion"),
            meta_request, grant, "meta-7:caller-paths",
        )


def test_recovery_reuses_atomic_raw_process_capture(capture, counted_launch):
    first = capture.run_or_load("meta-7:stable:launch", counted_launch)
    second = capture.run_or_load("meta-7:stable:launch", counted_launch)
    assert second == first
    assert counted_launch.calls == 1
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_meta_engine_protocol.py`

Expected: FAIL importing `selfloop_supervisor.meta.engine_protocol`.

- [ ] **Step 3: Implement the exact request/result schemas and path-free result boundary**

```python
# scripts/selfloop_supervisor/meta/engine_protocol.py
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,95}$")
RESULT_FIELDS = {
    "schema", "replayId", "requestDigest", "engineReleaseId",
    "proposalIds", "proposalArtifactIds", "reusedFailureIds",
}


@dataclass(frozen=True)
class MetaEngineRequest:
    replay_id: str
    engine_release_id: str
    engine_source_attestation_digest: str
    engine_bundle_receipt_digest: str
    capsule_digest: str
    champion_release_id: str
    champion_source_attestation_digest: str
    champion_bundle_receipt_digest: str
    task_distribution_digest: str
    model_id: str
    model_parameters_digest: str
    environment_digest: str
    permission_manifest_digest: str
    case_seed: str
    order_seed: str
    seed_set_digest: str
    budget_grant_id: str
    grant_terms_digest: str
    hard_budget_tokens: int
    proposal_cap: int

    def to_payload(self) -> dict[str, object]:
        payload = dataclasses.asdict(self)
        payload["schema"] = "selfloop.meta-engine-request.v1"
        return payload

    @property
    def request_digest(self) -> str:
        return sha256_canonical(self.to_payload())

    @property
    def comparison_digest(self) -> str:
        payload = self.to_payload()
        for name in (
            "engine_release_id", "engine_source_attestation_digest",
            "engine_bundle_receipt_digest", "budget_grant_id",
        ):
            payload.pop(name)
        return sha256_canonical(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "MetaEngineRequest":
        payload = json.loads(raw)
        if payload.pop("schema", None) != "selfloop.meta-engine-request.v1":
            raise EngineProtocolError("wrong request schema")
        expected = {field.name for field in dataclasses.fields(cls)}
        if set(payload) != expected:
            raise EngineProtocolError("request fields differ from schema")
        return cls(**payload)


@dataclass(frozen=True)
class MetaEngineResult:
    replay_id: str
    request_digest: str
    engine_release_id: str
    proposal_ids: tuple[str, ...]
    proposal_artifact_ids: tuple[str, ...]
    reused_failure_ids: tuple[str, ...]


def validate_engine_result(raw, request, allowed_failure_ids):
    payload = json.loads(raw)
    if set(payload) != RESULT_FIELDS:
        raise EngineProtocolError("unknown result fields")
    if payload["schema"] != "selfloop.meta-engine-result.v1":
        raise EngineProtocolError("wrong result schema")
    expected_identity = (request.replay_id, request.request_digest, request.engine_release_id)
    actual_identity = (payload["replayId"], payload["requestDigest"], payload["engineReleaseId"])
    if actual_identity != expected_identity:
        raise EngineProtocolError("result identity does not match launch")
    proposals = tuple(payload["proposalIds"])
    artifacts = tuple(payload["proposalArtifactIds"])
    reused = tuple(payload["reusedFailureIds"])
    all_ids = (*proposals, *artifacts, *reused)
    if not proposals or len(proposals) > request.proposal_cap or len(artifacts) != len(proposals):
        raise EngineProtocolError("proposal count exceeds protected cap")
    if any(not isinstance(value, str) or not ID_PATTERN.fullmatch(value) for value in all_ids):
        raise EngineProtocolError("invalid bounded identifier")
    if len(set(proposals)) != len(proposals) or len(set(artifacts)) != len(artifacts):
        raise EngineProtocolError("duplicate proposal identifier")
    if not set(reused) <= set(allowed_failure_ids):
        raise EngineProtocolError("unknown failure reference")
    return MetaEngineResult(actual_identity[0], actual_identity[1], actual_identity[2], proposals, artifacts, reused)
```

```python
# scripts/selfloop_strategy/engine.py
def run(request, capsule_reader, proposal_writer):
    capsule = capsule_reader.read_verified(request.capsule_digest)
    cards = select_cards(capsule, request.seed_set_digest, limit=request.proposal_cap)
    proposal_ids = tuple(card.card_id for card in cards)
    artifact_ids = tuple(proposal_writer.write(card.card_id, card.to_dict()) for card in cards)
    reused = tuple(sorted(card.failure_id for card in cards if card.failure_id is not None))
    return {
        "schema": "selfloop.meta-engine-result.v1",
        "replayId": request.replay_id,
        "requestDigest": request.request_digest,
        "engineReleaseId": request.engine_release_id,
        "proposalIds": list(proposal_ids),
        "proposalArtifactIds": list(artifact_ids),
        "reusedFailureIds": list(reused),
    }
```

`RawProcessCapture` reserves `${SIPS_HOME}/selfloop/supervisor/meta/raw/<operation-id>/`, records the expected command/input/environment/sandbox-policy digest before launch, and atomically writes canonical `process.json`, `stdout.bin`, and `stderr.bin`. `run_or_load` verifies and returns an existing complete capture before invoking P03; a conflicting operation ID fails. `EngineLauncher` reopens both handles through `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, recomputes each path-independent `ReleaseBundleReceipt.receipt_digest`, compares it with the request/handle digest, and only then derives the immutable engine/champion paths. It verifies exact request identities, grant ID/terms/cap, old-supervisor subtree digest, proposal scratch root, and its live controller capability before launch. Raw roots may appear only in equality assertions against the paths derived from verified bundle receipts; no caller path authorizes bytes. The process receives read access only to those two immutable bundle paths and the resolved capsule; writes only to proposal scratch/raw capture; and denies policy, ledger, sealed, pointer, credential, and sibling roots. Preflight failures launch nothing. Post-launch parsing failures remain inside `EngineRunReceipt` so Task 3 can meter them.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_meta_engine_protocol.py tests/selfloop/test_runtime_isolation.py`

Expected: strict protocol, release/champion binding, protected-path denial, and raw-capture replay tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_strategy/engine.py scripts/selfloop_supervisor/meta/engine_protocol.py scripts/selfloop_supervisor/meta/raw_process.py tests/selfloop/test_meta_engine_protocol.py
git commit -m "feat(selfloop): bind and capture meta engine launches"
```

### Task 2: Derive META triggers since the last terminal meta evaluation

**Files:**
- Create: `scripts/selfloop_supervisor/meta/triggers.py`
- Test: `tests/selfloop/test_meta_triggers.py`

**Interfaces:**
- Consumes: verified P05 ledger events for one root/campaign.
- Produces: `MetaTriggerState`, `MetaTriggerDecision`, `state_from_generation_history(rows) -> MetaTriggerState`, and `MetaTriggerProjector.from_ledger(ledger, root_id, campaign_id) -> MetaTriggerState`.
- The state records the terminal meta boundary sequence/digest and exact supporting event digests; caller-supplied counters are never accepted.

- [ ] **Step 1: Write failing boundary-reset and exclusion tests**

```python
def test_only_events_after_last_terminal_meta_evaluation_count(meta_history):
    rows = meta_history.rows(
        before=("stable_improvement", "stable_improvement", "no_winner"),
        terminal_meta="meta-4",
        after=("stable_improvement", "no_winner", "no_winner"),
    )
    state = state_from_generation_history(rows)
    assert state.last_meta_evaluation_id == "meta-4"
    assert state.accepted_stable_improvements == 1
    assert state.completed_no_winner_generations == 2


def test_second_meta_cycle_resets_at_newest_terminal_event(meta_history):
    rows = meta_history.two_completed_cycles()
    state = state_from_generation_history(rows)
    assert state.last_meta_evaluation_id == "meta-8"
    assert state.accepted_stable_improvements == 0
    assert state.completed_no_winner_generations == 1


def test_aborted_invalidated_and_nonaccepted_rows_do_not_count(meta_history):
    state = state_from_generation_history(meta_history.rows(
        after=("aborted", "evaluator_invalidated", "rejected_improvement", "no_winner"),
    ))
    assert state.accepted_stable_improvements == 0
    assert state.completed_no_winner_generations == 1
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_meta_triggers.py`

Expected: FAIL importing `selfloop_supervisor.meta.triggers`.

- [ ] **Step 3: Implement ledger-derived trigger accounting**

```python
@dataclass(frozen=True)
class MetaTriggerState:
    root_id: str
    campaign_id: str
    last_meta_evaluation_id: str | None
    boundary_sequence: int
    boundary_event_digest: str | None
    accepted_stable_improvements: int
    completed_no_winner_generations: int
    supporting_event_digests: tuple[str, ...]


@dataclass(frozen=True)
class MetaTriggerDecision:
    open_meta: bool
    reason: str
    state_digest: str


def state_from_generation_history(rows):
    ordered = tuple(sorted(rows, key=lambda row: row.sequence))
    terminals = [row for row in ordered if row.event_type == "meta.evaluation.terminal"]
    boundary = terminals[-1] if terminals else None
    cutoff = boundary.sequence if boundary is not None else 0
    eligible = tuple(row for row in ordered if row.sequence > cutoff)
    improvements = tuple(
        row for row in eligible
        if row.event_type == "promotion.stable_committed"
        and row.payload.get("acceptedSipsImprovement") is True
    )
    no_winners = tuple(
        row for row in eligible
        if row.event_type == "generation.completed"
        and row.payload.get("status") == "completed"
        and row.payload.get("g4WinnerReleaseId") is None
    )
    root_id = ordered[0].root_id if ordered else ""
    campaign_id = ordered[0].campaign_id if ordered else ""
    supports = tuple(row.digest for row in (*improvements, *no_winners))
    return MetaTriggerState(
        root_id=root_id,
        campaign_id=campaign_id,
        last_meta_evaluation_id=boundary.payload["metaEvaluationId"] if boundary else None,
        boundary_sequence=cutoff,
        boundary_event_digest=boundary.digest if boundary else None,
        accepted_stable_improvements=len(improvements),
        completed_no_winner_generations=len(no_winners),
        supporting_event_digests=supports,
    )


def evaluate_meta_trigger(state):
    digest = sha256_canonical(dataclasses.asdict(state))
    if state.accepted_stable_improvements >= 5:
        return MetaTriggerDecision(True, "five_stable_improvements_since_last_meta", digest)
    if state.completed_no_winner_generations >= 3:
        return MetaTriggerDecision(True, "three_no_winner_generations_since_last_meta", digest)
    return MetaTriggerDecision(False, "trigger_not_reached", digest)
```

`MetaTriggerProjector.from_ledger` first verifies the external anchor, rejects mixed root/campaign rows, and folds only canonical events. A meta evaluation writes `meta.evaluation.terminal` exactly once for every terminal retain/promote/failed outcome; an open probation phase is not terminal and does not reset the counters.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_meta_triggers.py tests/selfloop/test_ledger.py`

Expected: thresholds, newest-boundary reset, root/campaign isolation, and excluded-generation tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/meta/triggers.py tests/selfloop/test_meta_triggers.py
git commit -m "feat(selfloop): derive meta triggers from terminal boundaries"
```

### Task 3: Journal and resume paired replay with exact metering and raw-artifact reuse

**Files:**
- Create: `scripts/selfloop_supervisor/meta/store.py`
- Create: `scripts/selfloop_supervisor/meta/replay.py`
- Test: `tests/selfloop/test_meta_replay.py`
- Test: `tests/selfloop/test_meta_recovery.py`

**Interfaces:**
- Consumes: P02 `ReleaseBundleStore.open_verified`, P05 canonical `Ledger`, a live lock-owning `MutationSession`, session-bound `BudgetMeter.authorize/reconcile`, protected pinned `MetaReplayPolicy(failure_mode="stop_after_first_terminal_failure")`, Task 1 `EngineLauncher`, content-addressed artifact store, immutable replay capsule, stable/proposed/champion release-bundle receipt digests plus their release/attestation IDs, and Task 2 trigger decision.
- Produces: `MetaPhaseStore`, path-free `MetaReplayRequest`, `ReplaySideReceipt`, `ReplayPairReceipt`, and protected `MetaReplayRunner.run_or_resume(session: MutationSession, request: MetaReplayRequest) -> ReplayPairReceipt`.
- `MetaPhaseStore.begin`, `intent`, `complete`, `load_completed`, and `commit_terminal` include explicit root ID, campaign ID, meta-evaluation ID, phase, subject, input digest, and idempotency key. Reusing a key with different inputs raises `IdempotencyConflict`.

- [ ] **Step 1: Write failing equality, failure-metering, and every-phase recovery tests**

```python
def test_pair_uses_equal_terms_distinct_single_use_grants(meta_runtime):
    pair = meta_runtime.runner.run_or_resume(
        meta_runtime.session, meta_runtime.request,
    )
    assert pair.stable.comparison_digest == pair.proposed.comparison_digest
    assert pair.stable.grant_terms_digest == pair.proposed.grant_terms_digest
    assert pair.stable.grant_id != pair.proposed.grant_id
    assert pair.stable.usage_receipt_digest != pair.proposed.usage_receipt_digest


@pytest.mark.parametrize("failure", ("nonzero", "timeout", "malformed_json", "missing_usage"))
def test_failed_stable_launch_reconciles_only_actual_launch_before_stopping(
    meta_runtime, failure,
):
    meta_runtime.engine_process.fail_side_as("stable", failure)
    with pytest.raises(EngineRunFailed):
        meta_runtime.runner.run_or_resume(
            meta_runtime.session, meta_runtime.request,
        )
    assert meta_runtime.engine_process.calls_by_subject == {"stable": 1}
    assert meta_runtime.meter.authorized_count == 1
    assert meta_runtime.meter.reconciled_count == 1
    assert meta_runtime.meter.reconciliations_by_subject == {"stable": 1}
    if failure == "missing_usage":
        assert meta_runtime.meter.charged_tokens == (
            meta_runtime.meter.reserved_tokens("stable")
        )


def test_failed_proposed_launch_reconciles_both_actual_launches(meta_runtime):
    meta_runtime.engine_process.fail_side_as("proposed", "timeout")
    with pytest.raises(EngineRunFailed):
        meta_runtime.runner.run_or_resume(
            meta_runtime.session, meta_runtime.request,
        )
    assert meta_runtime.engine_process.calls_by_subject == {
        "stable": 1, "proposed": 1,
    }
    assert meta_runtime.meter.reconciliations_by_subject == {
        "stable": 1, "proposed": 1,
    }


def test_bundle_preflight_failure_launches_and_authorizes_neither_side(meta_runtime):
    meta_runtime.tamper_stable_bundle()
    with pytest.raises(ReleaseBundleMismatch):
        meta_runtime.runner.run_or_resume(
            meta_runtime.session, meta_runtime.request,
        )
    assert meta_runtime.engine_process.calls_by_subject == {}
    assert meta_runtime.meter.authorized_count == 0
    assert meta_runtime.meter.reconciled_count == 0


def test_crash_after_failed_stable_capture_reconciles_before_terminal_error(
    meta_runtime,
):
    meta_runtime.engine_process.fail_side_as("stable", "nonzero")
    meta_runtime.crash_after("stable_engine_captured")
    with pytest.raises(SimulatedCrash):
        meta_runtime.runner.run_or_resume(
            meta_runtime.session, meta_runtime.request,
        )
    restarted = meta_runtime.restart()
    with pytest.raises(EngineRunFailed):
        restarted.runner.run_or_resume(
            restarted.recovery_session, restarted.request,
        )
    assert meta_runtime.engine_process.calls_by_subject == {"stable": 1}
    assert meta_runtime.meter.reconciliations_by_subject == {"stable": 1}


@pytest.mark.parametrize("phase", (
    "capsule_verified",
    "stable_grant_authorized", "stable_engine_captured", "stable_usage_reconciled", "stable_artifacts_sealed",
    "proposed_grant_authorized", "proposed_engine_captured", "proposed_usage_reconciled", "proposed_artifacts_sealed",
    "replay_pair_committed",
))
def test_restart_resumes_first_incomplete_phase_without_duplicate_launch_or_charge(meta_runtime, phase):
    meta_runtime.crash_after(phase)
    with pytest.raises(SimulatedCrash):
        meta_runtime.runner.run_or_resume(
            meta_runtime.session, meta_runtime.request,
        )
    restarted = meta_runtime.restart()
    pair = restarted.runner.run_or_resume(
        restarted.recovery_session, restarted.request,
    )
    assert pair.status == "completed"
    assert meta_runtime.engine_process.calls_by_subject == {"stable": 1, "proposed": 1}
    assert meta_runtime.meter.reconciliations_by_grant == {pair.stable.grant_id: 1, pair.proposed.grant_id: 1}
    assert meta_runtime.artifacts.verify(pair.stable.raw_artifact_digest)
    assert meta_runtime.artifacts.verify(pair.proposed.raw_artifact_digest)
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_meta_replay.py tests/selfloop/test_meta_recovery.py`

Expected: FAIL importing `selfloop_supervisor.meta.store` and `selfloop_supervisor.meta.replay`.

- [ ] **Step 3: Implement the phase journal and resumable paired runner**

```python
META_REPLAY_PHASES = (
    "capsule_verified",
    "stable_grant_authorized", "stable_engine_captured", "stable_usage_reconciled", "stable_artifacts_sealed",
    "proposed_grant_authorized", "proposed_engine_captured", "proposed_usage_reconciled", "proposed_artifacts_sealed",
    "replay_pair_committed",
)


@dataclass(frozen=True)
class MetaReplayRequest:
    root_id: str
    campaign_id: str
    meta_evaluation_id: str
    idempotency_key: str
    trigger_state_digest: str
    capsule_digest: str
    stable_engine_release_id: str
    stable_engine_source_attestation_digest: str
    stable_engine_bundle_receipt_digest: str
    proposed_engine_release_id: str
    proposed_engine_source_attestation_digest: str
    proposed_engine_bundle_receipt_digest: str
    champion_release_id: str
    champion_source_attestation_digest: str
    champion_bundle_receipt_digest: str
    task_distribution_digest: str
    model_id: str
    model_parameters_digest: str
    environment_digest: str
    permission_manifest_digest: str
    case_seed: str
    order_seed: str
    seed_set_digest: str
    hard_budget_tokens: int
    proposal_cap: int
    old_supervisor_digest: str
    old_policy_digest: str
    old_evaluator_digest: str


class MetaPhaseStore:
    def run_once(self, session, scope, phase, subject, input_digest, operation):
        capability = session.issue(
            operation=self.operations.for_phase(phase),
            resource_id=f"{scope.meta_evaluation_id}:{subject}",
            phase=phase,
        )
        key = capability.idempotency_key
        completed = self.load_completed(scope.root_id, scope.campaign_id, key)
        if completed is not None:
            if completed.input_digest != input_digest:
                raise IdempotencyConflict(key)
            verify_capability = session.issue(
                operation=self.operations.verify_phase,
                resource_id=completed.receipt_digest,
                phase=f"{phase}:verify",
            )
            with self.service_context.bind(verify_capability):
                self.verifiers.for_phase(phase).verify(completed.receipt)
            return completed.receipt
        self.intent(scope, phase, subject, input_digest, key)
        with self.service_context.bind(capability):
            receipt = operation(key, capability)
        return self.complete(scope, phase, subject, input_digest, key, receipt)
```

```python
class MetaReplayRunner:
    def run_or_resume(self, session, request):
        require_session_scope(session, request.root_id, request.campaign_id)
        require_equal(session.request_idempotency_key, request.idempotency_key)
        self.policy.require_failure_mode(
            "stop_after_first_terminal_failure"
        )
        scope = self.store.begin(session, request)
        stable_bundle = self._resolve_bundle(
            request.stable_engine_release_id,
            request.stable_engine_source_attestation_digest,
            request.stable_engine_bundle_receipt_digest,
        )
        proposed_bundle = self._resolve_bundle(
            request.proposed_engine_release_id,
            request.proposed_engine_source_attestation_digest,
            request.proposed_engine_bundle_receipt_digest,
        )
        champion_bundle = self._resolve_bundle(
            request.champion_release_id,
            request.champion_source_attestation_digest,
            request.champion_bundle_receipt_digest,
        )
        capsule = self.store.run_once(
            session, scope, "capsule_verified", "pair", request.capsule_digest,
            lambda operation_id, capability: self.capsules.verify(
                request.capsule_digest, operation_id, capability,
            ),
        )
        terms = self.meter.meta_terms(
            root_id=request.root_id,
            campaign_id=request.campaign_id,
            hard_budget_tokens=request.hard_budget_tokens,
            permission_manifest_digest=request.permission_manifest_digest,
            purpose="meta-historical-replay",
        )
        stable = self._run_side(
            session, scope, "stable", stable_bundle, champion_bundle,
            request, capsule, terms,
        )
        # _run_side seals and reconciles an actual launch before raising.
        # Under the pinned stop policy, a failed stable side ends the pair;
        # proposed is neither authorized nor represented as launched.
        proposed = self._run_side(
            session, scope, "proposed", proposed_bundle, champion_bundle,
            request, capsule, terms,
        )
        if stable.comparison_digest != proposed.comparison_digest:
            raise MetaReplayMismatch("replay inputs differ")
        if stable.grant_terms_digest != proposed.grant_terms_digest or stable.grant_id == proposed.grant_id:
            raise MetaReplayMismatch("grant terms differ or grant was reused")
        pair_input = sha256_canonical({
            "stable": stable.receipt_digest,
            "proposed": proposed.receipt_digest,
            "capsule": capsule.receipt_digest,
        })
        return self.store.run_once(
            session, scope, "replay_pair_committed", "pair", pair_input,
            lambda operation_id, capability: ReplayPairReceipt.build(
                request, stable, proposed, capsule,
                operation_id, capability.session_digest,
            ),
        )

    def _resolve_bundle(self, release_id, source_attestation_digest, expected_digest):
        bundle = self.release_bundles.open_verified(
            release_id, source_attestation_digest,
        )
        if bundle.receipt_digest != expected_digest:
            raise ReleaseBundleMismatch(release_id)
        return bundle

    def _run_side(
        self, session, scope, subject, engine_bundle, champion_bundle,
        request, capsule, terms,
    ):
        grant = self.store.run_once(
            session, scope, f"{subject}_grant_authorized", subject, terms.digest,
            lambda operation_id, capability: self.meter.authorize(
                terms.to_request(subject, operation_id), capability,
            ),
        )
        engine_request = build_engine_request(
            request, engine_bundle, champion_bundle, grant, capsule,
        )
        launched = self.store.run_once(
            session, scope, f"{subject}_engine_captured", subject,
            engine_request.request_digest,
            lambda operation_id, capability: self.launcher.run(
                engine_bundle, champion_bundle, engine_request, grant, operation_id,
            ),
        )
        usage = self.store.run_once(
            session, scope, f"{subject}_usage_reconciled", subject,
            launched.process_receipt_digest,
            lambda operation_id, capability: self.meter.reconcile(
                grant.grant_id,
                authoritative_or_full_reservation(launched.process_receipt, grant),
                capability,
            ),
        )
        raw = self.store.run_once(
            session, scope, f"{subject}_artifacts_sealed", subject,
            launched.raw_capture_digest,
            lambda operation_id, capability: self.artifacts.seal_engine_run(
                scope, subject, launched, operation_id, capability,
            ),
        )
        launched.require_success()
        return ReplaySideReceipt.from_verified(engine_request, grant, launched, usage, raw)
```

`MetaReplayRequest` contains no roots or paths. Stable, proposed, and champion bytes are authorized only by their release ID, exact source-attestation digest, and path-independent `ReleaseBundleReceipt.receipt_digest`; `_resolve_bundle` derives paths internally and resolves all three before any grant or launch. P13 pins `stop_after_first_terminal_failure`: `_run_side` always captures, seals, and reconciles a side that actually launched before `require_success`; a failed stable side then stops without authorizing or inventing a proposed launch, while a failed proposed side follows a reconciled successful stable side. This avoids both under-reconciliation and a false two-launch invariant. A future symmetric-attempt policy would be a different protected policy/schema and must capture both sides before requiring either success. `MetaPhaseStore` uses P05's hash-linked append API and verifies the ledger anchor before every resume. Every effect receives a single-use capability from the live lock-owning `MutationSession`; the service context makes that capability visible to APIs whose public signatures stay path/capability-free. Recovery re-enters through `SelfloopController`, reconstructs the authorized session from the persisted intent, and issues fresh verification capabilities without changing the original native idempotency keys. Each completed event contains the exact receipt digest and immutable artifact handles; each intent contains the planned output location and operation ID. `RawProcessCapture.run_or_load` makes a crash after process exit but before phase completion recoverable without relaunch. Usage reconciliation is a separate idempotent phase keyed to the persisted process receipt; it executes for every launched side before schema/process failure is raised. Proposal JSON, stdout, stderr, process receipt, sandbox receipt, and usage receipt are all sealed before `ReplayPairReceipt` becomes terminal.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_meta_engine_protocol.py tests/selfloop/test_meta_replay.py tests/selfloop/test_meta_recovery.py tests/selfloop/test_budget.py tests/selfloop/test_ledger.py`

Expected: equal-input/distinct-grant checks pass for completed pairs; stable failures reconcile one actual launch and create no proposed grant/launch, proposed failures reconcile two actual launches, and every injected crash resumes from sealed artifacts without duplicate launch, grant, or charge.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/meta/store.py scripts/selfloop_supervisor/meta/replay.py tests/selfloop/test_meta_replay.py tests/selfloop/test_meta_recovery.py
git commit -m "feat(selfloop): journal resumable metered meta replay"
```

### Task 4: Compose the real P09-P12 pipeline under the old supervisor

**Files:**
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/meta/store.py`
- Create: `scripts/selfloop_supervisor/meta/candidate_materializer.py`
- Create: `scripts/selfloop_supervisor/meta/old_supervisor_runner.py`
- Test: `tests/selfloop/test_meta_old_supervisor_runner.py`

**Interfaces:**
- Consumes: Task 3 `ReplayPairReceipt`/`MetaPhaseStore`; P02 `ReleaseBuilder`, `ReleaseBundleStore.materialize`, byte-bearing `ReleaseBundleReceipt`, and `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`; P05 live lock-owning `MutationSession` plus per-phase `MutationCapability`; P08 `CandidateManager` and the exact changed-path classifier; P09 `GateScope`, `GateEvidenceBuilder`, `run_g0(scope, evidence_builder, idempotency_key)`, `run_g1(scope, g0_receipt_digest, evidence_builder, idempotency_key)`, `ProgressiveGateRunner.run_g2/run_g3`, `DevelopmentConformanceService.issue`, and `GateLedger`; P10 `G4Runner.run(scope, development_ready_event_digest, idempotency_key)`; P11 typed `InstallTrialPayload`, `PromotionAuthorizationStore`, `PromotionResolver`, `SelfloopController`, and `TrialControlStore`; P12 `ProbationStartStore`, `RoutingStore`, `OutcomeStore`, `ShadowStore`, `ProbationEvidenceBuilder`, typed `G5Store`/`ProbationWatchdog`, `StablePromotionManager`, and `C4ConformanceStore`.
- Produces: `CandidateMaterializer.materialize(session, engine_side, proposal_id, artifact_id, operation_id) -> CandidateMaterializationReceipt`, `CandidateMaterializationFailureReceipt`, and exact candidate ID/reservation/create/commit/removal/release proof; `NativeReceiptPointer`; `NativePhaseResult[T]`; controller-private `ControllerSubAction` and `SelfloopController.dispatch_subaction(parent_session, subaction)`; `GateProofRef`; `EngineCandidateEvaluationReceipt`; `MetaGateChainReceipt`; `OldSupervisorRunner.evaluate_generated_candidates(session, pair) -> tuple[EngineCandidateEvaluationReceipt, ...]`; `OldSupervisorRunner.run_proposed_engine_to_c4(session, pair, generated) -> MetaGateChainReceipt`; and `OldSupervisorRunner.observe_probation_signal(session, root_id, promotion_id, signal_id) -> G5Receipt`.
- P09 G0-G3, P10 G4, P11 trial control, and every P12 stage keep their native persisted receipt types. P13 stores their native receipt/event digests, invokes the owning plan's resolver or idempotent service on every resume, and only then derives a `GateProofRef`. The outer meta phase event is a recovery pointer, never proof that the native owner succeeded.

- [ ] **Step 1: Write failing protected-materialization, exact-composition, and owner-verified recovery tests**

```python
def test_engine_cannot_mint_candidate_release_or_change_protected_path(real_meta_pair, old_runner):
    real_meta_pair.proposed_artifacts.replace_patch(
        "artifact-1", changed_path="scripts/selfloop_supervisor/kernel.py",
    )
    with pytest.raises(CandidateMaterializationFailed) as raised:
        old_runner.evaluate_generated_candidates(
            real_meta_pair.session, real_meta_pair,
        )
    assert "protected path" in raised.value.receipt.reason
    assert raised.value.receipt.worktree_removal_receipt_digest
    assert raised.value.receipt.candidate_reservation_release_receipt_digest
    assert real_meta_pair.store.candidate_release_count == 0


def test_materialized_candidate_carries_byte_verified_release_bundle(real_meta_pair, old_runner):
    generated = old_runner.evaluate_generated_candidates(
        real_meta_pair.session, real_meta_pair,
    )
    materialized = generated[0].candidate_materialization
    reopened = old_runner.release_bundles.open_verified(
        materialized.release_identity.release_id,
        materialized.source_attestation_digest,
    )
    assert reopened.receipt_digest == materialized.release_bundle_receipt_digest


def test_materialization_uses_reserved_id_capabilities_and_terminal_cleanup(
    real_meta_pair, old_runner,
):
    generated = old_runner.evaluate_generated_candidates(
        real_meta_pair.session, real_meta_pair,
    )
    receipt = generated[0].candidate_materialization
    assert receipt.candidate_id == real_meta_pair.reserved_candidate_id
    assert receipt.candidate_reservation_event_digest
    assert receipt.worktree_create_receipt_digest
    assert receipt.candidate_commit_receipt_digest
    assert receipt.worktree_removal_receipt_digest
    assert receipt.candidate_reservation_release_receipt_digest
    assert old_runner.capabilities.operations_for(receipt.candidate_id) == (
        MutationOperation.BUDGET_RESERVE,
        MutationOperation.WORKTREE_CREATE,
        MutationOperation.WORKTREE_COMMIT,
        MutationOperation.WORKTREE_REMOVE,
        MutationOperation.BUDGET_RELEASE,
    )


def test_materialization_failure_removes_worktree_and_releases_reservation(
    real_meta_pair, old_runner,
):
    old_runner.patch_applier.fail_after_write()
    with pytest.raises(CandidateMaterializationFailed) as raised:
        old_runner.evaluate_generated_candidates(
            real_meta_pair.session, real_meta_pair,
        )
    failure = raised.value.receipt
    assert failure.worktree_removal_receipt_digest
    assert failure.candidate_reservation_release_receipt_digest
    assert old_runner.candidates.exists(failure.candidate_id) is False
    assert old_runner.budget.reservation(failure.candidate_id).state == "consumed"


def test_old_runner_calls_real_gate_owners_and_preserves_native_receipts(real_meta_pair, old_runner):
    generated = old_runner.evaluate_generated_candidates(
        real_meta_pair.session, real_meta_pair,
    )
    chain = old_runner.run_proposed_engine_to_c4(
        real_meta_pair.session, real_meta_pair, generated,
    )
    assert tuple(ref.gate for ref in chain.gates) == ("G0", "G1", "G2", "G3", "G4", "G5")
    assert old_runner.c4_store.current(real_meta_pair.root_id).receipt_digest == chain.c4_receipt_digest
    assert chain.evidence_receipt_digest == chain.gates[-1].evidence_receipt_digest
    assert old_runner.loaded_supervisor_digest == real_meta_pair.old_supervisor_digest
    assert old_runner.owner_verification_count() >= len(chain.gates)


@pytest.mark.parametrize("phase", (
    "candidate_materialized", "G0", "G1", "G2", "G3", "development_ready", "G4",
    "promotion_authorized", "trial_control_ready", "probation_started",
    "routes_outcomes", "shadow_selection", "shadows", "evidence", "G5",
    "stable_promotion", "C4",
))
def test_old_runner_reuses_completed_native_receipts_after_restart(real_meta_pair, old_runner, phase):
    old_runner.crash_after(phase)
    generated = old_runner.evaluate_generated_candidates(
        real_meta_pair.session, real_meta_pair,
    )
    with pytest.raises(SimulatedCrash):
        old_runner.run_proposed_engine_to_c4(
            real_meta_pair.session, real_meta_pair, generated,
        )
    restarted = old_runner.restart()
    chain = restarted.run_proposed_engine_to_c4(
        restarted.recovery_session, real_meta_pair, generated,
    )
    assert chain.status == "passed"
    assert old_runner.native_call_count(phase) == 1
    assert old_runner.owner_verify_count(phase) >= 2


def test_runner_exposes_no_caller_policy_state_or_receipt_construction(old_runner):
    assert tuple(inspect.signature(old_runner.g4.run).parameters) == (
        "scope", "development_ready_event_digest", "idempotency_key",
    )
    subaction = old_runner.controller_subactions[0]
    assert subaction.action is ControllerAction.INSTALL_TRIAL
    assert isinstance(subaction.payload, InstallTrialPayload)
    assert dataclasses.asdict(subaction.payload) == {
        "promotion_id": old_runner.promotion_id,
    }
    assert old_runner.constructed_native_receipt_count == 0


def test_trial_install_delegates_inside_existing_root_lock_without_nested_handle(
    real_meta_pair, old_runner,
):
    generated = old_runner.evaluate_generated_candidates(
        real_meta_pair.session, real_meta_pair,
    )
    old_runner.run_proposed_engine_to_c4(
        real_meta_pair.session, real_meta_pair, generated,
    )
    assert old_runner.root_lock.acquire_count == 1
    assert old_runner.controller.public_handle_calls == 1
    assert old_runner.controller.internal_subaction_calls == 1
    assert old_runner.controller.nested_handle_calls == 0
    assert old_runner.direct_p11_mutator_calls == 0
    assert old_runner.controller.subaction_receipt("install-trial").parent_session_digest == (
        real_meta_pair.session.session_digest
    )


def test_native_pipeline_requires_live_session_and_one_capability_per_phase(
    real_meta_pair, old_runner,
):
    with pytest.raises(MutationSessionRequired):
        old_runner.evaluate_generated_candidates(None, real_meta_pair)
    old_runner.evaluate_generated_candidates(real_meta_pair.session, real_meta_pair)
    assert old_runner.capabilities.all_bound_to(real_meta_pair.session.session_digest)
    assert old_runner.capabilities.no_reuse()


def test_authorization_pointer_is_re_resolved_to_typed_receipt_before_use(
    real_meta_pair, old_runner,
):
    chain = old_runner.run_until_phase(
        real_meta_pair.session, real_meta_pair, "promotion_authorized",
    )
    restarted = old_runner.restart()
    authorization = restarted.resolve_native_phase(
        restarted.recovery_session, chain.scope, "promotion_authorized",
    ).receipt
    assert isinstance(authorization, PromotionAuthorizationReceipt)
    assert authorization.promotion_id == chain.promotion_id
    restarted.tamper_phase_lookup_key("promotion_authorized", "promotion-forged")
    with pytest.raises(NativeReceiptRecoveryMismatch, match="lookup key"):
        restarted.resume(restarted.recovery_session, real_meta_pair)


def test_watchdog_owns_triggered_rollback(real_meta_pair, old_runner):
    old_runner.append_authenticated_probation_trigger("integrity-failure")
    g5 = old_runner.observe_probation_signal(
        real_meta_pair.session, real_meta_pair.root_id,
        old_runner.promotion_id, "signal-9",
    )
    assert g5.outcome == "rollback"
    assert g5.rollback_receipt_digest
    assert old_runner.direct_rollback_calls == 0
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_meta_old_supervisor_runner.py`

Expected: FAIL importing `selfloop_supervisor.meta.old_supervisor_runner`.

- [ ] **Step 3: Materialize only supervisor-verified proposal artifacts**

```python
class CandidateMaterializer:
    def materialize(
        self, session, engine_side, proposal_id, artifact_id, operation_id,
    ):
        if proposal_id not in engine_side.result.proposal_ids:
            raise CandidateMaterializationError("proposal ID was not emitted by engine")
        if artifact_id not in engine_side.result.proposal_artifact_ids:
            raise CandidateMaterializationError("artifact ID was not emitted by engine")
        artifact = self.artifacts.resolve_verified(engine_side.raw_artifact_digest, artifact_id)
        candidate_id = self.phases.reserve_id(
            session, f"{operation_id}:candidate-id", "candidate",
        )
        reservation = self.budget.reserve_candidate(
            self.scope, candidate_id,
            session.issue(
                MutationOperation.BUDGET_RESERVE, candidate_id,
                f"{operation_id}:reserve-candidate",
            ),
        )
        workspace = None
        try:
            workspace = self.candidates.create(
                self.scope, artifact.experiment_card, self.champion.commit_sha,
                candidate_id, reservation.event_digest,
                session.issue(
                    MutationOperation.WORKTREE_CREATE, candidate_id,
                    f"{operation_id}:create-worktree",
                ),
            )
            application = self.patch_applier.apply_declarative_patch(
                workspace, artifact.payload,
            )
            classification = classify_changed_paths(application.changed_paths)
            if any(
                not path.startswith("scripts/selfloop_strategy/")
                for path in application.changed_paths
            ):
                raise CandidatePolicyDenied("meta proposal changed a protected path")
            commit = self.candidates.commit(
                candidate_id, f"meta proposal {proposal_id}",
                session.issue(
                    MutationOperation.WORKTREE_COMMIT, candidate_id,
                    f"{operation_id}:commit-candidate",
                ),
            )
            build = self.releases.build(
                self.scope.root_id, workspace.path, commit.commit_sha,
                self.release_metadata,
            )
            bundle = self.release_bundles.materialize(build)
            verified_bundle = self.release_bundles.open_verified(
                bundle.release_identity.release_id,
                bundle.source_attestation_digest,
            )
            if verified_bundle.receipt_digest != bundle.receipt_digest:
                raise CandidateMaterializationError(
                    "release bundle receipt changed after build"
                )
            if sha256_tree(
                workspace.path / "scripts/selfloop_supervisor"
            ) != self.old_supervisor_digest:
                raise CandidatePolicyDenied(
                    "candidate supervisor subtree digest changed"
                )
        except BaseException as error:
            removal, released = self._cleanup_candidate(
                session, candidate_id, reservation, operation_id,
            )
            failure = self.receipts.commit_materialization_failure(
                CandidateMaterializationFailureReceipt.from_error(
                    operation_id, proposal_id, artifact_id, candidate_id,
                    reservation.event_digest, removal.receipt_digest,
                    released.receipt_digest, error,
                ),
                session.issue(
                    MutationOperation.RECEIPT_PERSIST, candidate_id,
                    f"{operation_id}:persist-failure",
                ),
            )
            raise CandidateMaterializationFailed(failure) from error
        removal, released = self._cleanup_candidate(
            session, candidate_id, reservation, operation_id,
        )
        return CandidateMaterializationReceipt.build(
            operation_id, engine_side.engine_release_id, proposal_id, artifact_id,
            artifact.receipt_digest, classification, candidate_id,
            reservation.event_digest, workspace.create_receipt_event_digest,
            commit.receipt_digest, removal.receipt_digest, released.receipt_digest,
            release_identity=verified_bundle.release_identity,
            source_attestation_digest=verified_bundle.source_attestation_digest,
            release_bundle_receipt_digest=verified_bundle.receipt_digest,
        )

    def _cleanup_candidate(
        self, session, candidate_id, reservation, operation_id,
    ):
        removal = self.candidates.remove(
            candidate_id,
            session.issue(
                MutationOperation.WORKTREE_REMOVE, candidate_id,
                f"{operation_id}:remove-worktree",
            ),
        )
        released = self.budget.release_reservation(
            reservation.reservation_id, ReservationUsage(status="consumed"),
            session.issue(
                MutationOperation.BUDGET_RELEASE, candidate_id,
                f"{operation_id}:consume-candidate",
            ),
        )
        return removal, released
```

The declarative patch schema contains only normalized relative paths, expected preimage digests, replacement bytes, and file modes. It rejects absolute paths, `..`, symlink traversal, commands, hooks, and writes outside the candidate worktree. The candidate ID comes only from P05's persisted `object.id.reserved` phase and the candidate budget reservation precedes `CandidateManager.create`; P08 receives the exact ID, reservation event digest, and distinct create/commit/remove capabilities. Both success and failure paths remove the disposable worktree and terminally consume/release the candidate reservation before returning or raising, and their typed receipts are part of the materialization proof. The materializer computes commit/release/artifact digests itself; no release identity from engine JSON is accepted. Its canonical receipt carries the verified `release_identity`, exact `source_attestation_digest`, and path-independent `release_bundle_receipt_digest`. All later scope/gate construction reopens the exact bytes with `ReleaseBundleStore.open_verified` and compares the recomputed receipt digest; a detached `ReleaseIdentity` or stored bundle path is insufficient.

- [ ] **Step 4: Journal native pointers and re-enter every owner on resume**

```python
@dataclass(frozen=True)
class NativeReceiptPointer:
    owner: str
    receipt_digest: str
    event_digest: str | None
    lookup_key: str | None
    native_idempotency_key: str


@dataclass(frozen=True)
class NativePhaseResult(Generic[T]):
    pointer: NativeReceiptPointer
    receipt: T


class MetaPhaseStore:
    def run_native(self, session, scope, phase, input_digest, invoke, verify):
        require_live_lock_owning_session(session, scope.root_id, scope.campaign_id)
        if completed := self.load_completed(scope, phase, input_digest):
            pointer = NativeReceiptPointer.from_payload(
                completed.payload["nativeReceipt"]
            )
            capability = session.issue(
                operation=self.operations.verify_native,
                resource_id=pointer.receipt_digest,
                phase=f"{phase}:verify",
            )
            with self.service_context.bind(capability):
                receipt = verify(pointer, pointer.native_idempotency_key)
            self.require_pointer_matches_receipt(pointer, receipt)
            return NativePhaseResult(pointer, receipt)
        capability = session.issue(
            operation=self.operations.for_native_phase(phase),
            resource_id=input_digest,
            phase=phase,
        )
        idempotency_key = capability.idempotency_key
        operation_id = self.append_intent(
            scope, phase, input_digest, idempotency_key,
        ).operation_id
        with self.service_context.bind(capability):
            native = invoke(idempotency_key)
        pointer = NativeReceiptPointer(
            owner=type(native).__name__,
            receipt_digest=native.receipt_digest,
            event_digest=getattr(native, "event_digest", None),
            lookup_key=getattr(native, "promotion_id", None),
            native_idempotency_key=idempotency_key,
        )
        verify_capability = session.issue(
            operation=self.operations.verify_native,
            resource_id=pointer.receipt_digest,
            phase=f"{phase}:verify",
        )
        with self.service_context.bind(verify_capability):
            receipt = verify(pointer, pointer.native_idempotency_key)
        self.require_pointer_matches_receipt(pointer, receipt)
        self.append_completed(
            scope, phase, input_digest, operation_id,
            native_receipt=dataclasses.asdict(pointer),
        )
        return NativePhaseResult(pointer, receipt)
```

`run_native` stores only the native receipt pointer after the owner has re-resolved it. On invocation and restart, `verify` must return the owner's typed native receipt; `require_pointer_matches_receipt` compares receipt/event digest and `lookup_key` (including `promotion_id`) before returning `NativePhaseResult`. Callers never treat `NativeReceiptPointer` as an authorization or access fields such as `promotion_id` on it. Invocation and verification each consume a distinct single-use capability from the live lock-owning `MutationSession`; the capability is bound inside the controller-owned service context, so the authoritative P09-P12 signatures do not gain caller capability parameters. The pointer preserves the original native idempotency key, allowing a recovery-session verification capability to re-enter G4 or another idempotent owner without changing that key. The exact owner paths are: `ReleaseBundleStore.open_verified` for materialized candidate bytes; `GateLedger.resolve_gate_receipt` for G0-G3; `GateLedger.resolve_event(..., "development.g0_g3.ready")` plus `DevelopmentGateReceipt.from_event` for readiness; the same idempotent `G4Runner.run` call for G4; `PromotionResolver.resolve(PromotionRequest(...))` followed by the native `PromotionAuthorizationReceipt`; `TrialControlStore.resolve` and `resolve_current` for P11; P12 `require`/idempotent typed store calls for start, routes, outcomes, selections, shadows, and evidence; `G5Store.require_terminal` for terminal G5 (the same `evaluate_and_commit` key for open G5); the same canonical `StablePromotionManager.promote` key for stable promotion; and `C4ConformanceStore.current` for C4. A digest mismatch after any owner call is `NativeReceiptRecoveryMismatch`. A missing, wrong-scope, expired, or reused capability fails before the native service reads or mutates state.

- [ ] **Step 5: Implement exact native receipt references and authoritative orchestration**

```python
@dataclass(frozen=True)
class GateProofRef:
    gate: str
    status: str
    receipt_digest: str
    event_digest: str
    evidence_receipt_digest: str | None


@dataclass(frozen=True)
class MetaGateChainReceipt:
    meta_evaluation_id: str
    proposed_engine_release_id: str
    gates: tuple[GateProofRef, ...]
    development_ready_receipt_digest: str
    development_ready_event_digest: str
    promotion_id: str | None
    trial_control_receipt_digest: str | None
    probation_start_receipt_digest: str | None
    routing_receipt_digests: tuple[str, ...]
    outcome_receipt_digests: tuple[str, ...]
    shadow_receipt_digests: tuple[str, ...]
    g5_receipt_digest: str | None
    evidence_receipt_digest: str | None
    stable_promotion_receipt_digest: str | None
    c4_receipt_digest: str | None
    sandbox_receipt_digests: tuple[str, ...]
    raw_artifact_digests: tuple[str, ...]
    usage_receipt_digests: tuple[str, ...]
    old_supervisor_digest: str
    old_policy_digest: str
    old_evaluator_digest: str
    status: str
    receipt_digest: str
```

`CandidateMaterializer` reopens the `ReleaseBundleReceipt` bytes and constructs the one canonical `GateScope` from persisted P02/P08 release, experiment, policy-pin, supervisor, and champion records. P13 never supplies changed paths, provenance, check results, review objects, policies, state, or verdicts to P09-P12. The implementation calls the authoritative development/G4 APIs exactly:

```python
class OldSupervisorRunner:
    def native_call(
        self, session, scope, phase, input_digest, invoke, verify,
    ):
        result = self.phases.run_native(
            session, scope, phase, input_digest, invoke, verify,
        )
        return result.receipt

    def run_development_and_g4(self, session, scope, protected_cases):
        require_live_lock_owning_session(session, scope.root_id, scope.campaign_id)
        g0 = self.native_call(
            session, scope, "G0", scope.candidate_diff_hash,
            lambda key: run_g0(scope, self.gate_evidence, key),
            self.verify_g0(scope),
        )
        g1 = self.native_call(
            session, scope, "G1", g0.receipt_digest,
            lambda key: run_g1(
                scope, g0.receipt_digest, self.gate_evidence, key,
            ),
            self.verify_g1(scope),
        )
        g2 = self.native_call(
            session, scope, "G2", g1.receipt_digest,
            lambda key: self.progressive.run_g2(
                scope, g1.receipt_digest, protected_cases.g2,
                protected_cases.selection_seed, key,
            ),
            self.verify_g2(scope),
        )
        g3 = self.native_call(
            session, scope, "G3", g2.receipt_digest,
            lambda key: self.progressive.run_g3(
                scope, g2.receipt_digest, protected_cases.g3, key,
            ),
            self.verify_g3(scope),
        )
        development = self.native_call(
            session, scope, "development_ready", g3.receipt_digest,
            lambda key: self.development.issue(scope, key),
            self.verify_development(scope),
        )
        g4 = self.native_call(
            session, scope, "G4", development.event_digest,
            lambda key: self.g4.run(scope, development.event_digest, key),
            self.verify_g4(scope, development.event_digest),
        )
        return (g0, g1, g2, g3), development, g4

    def verify_authorization(self, root_id):
        def verify(pointer, native_idempotency_key):
            if not pointer.lookup_key:
                raise NativeReceiptRecoveryMismatch(
                    "promotion authorization lookup key is missing"
                )
            resolved = self.promotion_resolver.resolve(PromotionRequest(
                root_id=root_id,
                promotion_id=pointer.lookup_key,
                idempotency_key=native_idempotency_key,
            ))
            authorization = self.promotion_authorizations.require(
                root_id, pointer.lookup_key,
            )
            if (
                resolved.authorization_receipt_digest
                != authorization.receipt_digest
            ):
                raise NativeReceiptRecoveryMismatch(
                    "promotion authorization lookup key mismatch"
                )
            return authorization
        return verify

    def install_authorized_trial(self, session, scope, g4):
        authorization = self.native_call(
            session, scope, "promotion_authorized", g4.receipt_digest,
            lambda key: self.promotion_authorizations.authorize_g4(
                scope.root_id, g4.event_digest, key,
            ),
            self.verify_authorization(scope.root_id),
        )
        trial = self.native_call(
            session, scope, "trial_control_ready", authorization.receipt_digest,
            lambda key: self._install_trial(
                session, scope, authorization, key,
            ),
            self.verify_trial_control(scope.root_id, authorization.promotion_id),
        )
        return authorization, trial

    def _install_trial(
        self, session, scope, authorization, idempotency_key,
    ):
        subaction = ControllerSubAction(
            action=ControllerAction.INSTALL_TRIAL,
            payload=InstallTrialPayload(
                promotion_id=authorization.promotion_id,
            ),
            idempotency_key=idempotency_key,
        )
        response = self.controller.dispatch_subaction(session, subaction)
        response.require_success()
        digest = response.payload["trial_control_receipt_digest"]
        trial = self.trial_controls.resolve(
            scope.root_id, authorization.promotion_id, digest,
        )
        current = self.trial_controls.resolve_current(
            scope.root_id, authorization.promotion_id,
        )
        if current.receipt_digest != trial.receipt_digest:
            raise NativeReceiptRecoveryMismatch(
                "trial_control.ready is not current"
            )
        return trial
```

`native_call` is the receipt-resolving wrapper over `MetaPhaseStore.run_native`; it never bypasses the session/capability logic above. P09 derives G0/G1 evidence from `GateScope`, persists every native gate, and alone issues `development.g0_g3.ready`. P10 resolves the readiness event and pinned policy internally. P11 extends P05's closed public `ControllerAction`/`ControllerRequest.payload` union with `ControllerAction.INSTALL_TRIAL` and exact `InstallTrialPayload(promotion_id: str)`; root and idempotency key remain in the public request envelope, and no loose optional promotion field is added. Because P13 is already executing inside the public meta action's lock-owning session, it must not recursively call `SelfloopController.handle` and reacquire the same root lock. Instead it uses this controller-private typed delegation contract:

```python
@dataclass(frozen=True)
class ControllerSubAction:
    action: ControllerAction
    payload: InstallTrialPayload
    idempotency_key: str


class SelfloopController:
    def dispatch_subaction(self, parent_session, subaction):
        parent_session.require_live_lock_owner()
        intent = self.journal.append_subaction_intent(
            parent_session, subaction.action, subaction.payload,
            subaction.idempotency_key,
        )
        authorization = self.policy.authorize_subaction(
            parent_session, intent, subaction.action,
        )
        delegated = parent_session.delegate(
            intent_id=intent.intent_id,
            authorization_digest=authorization.receipt_digest,
            idempotency_key=subaction.idempotency_key,
        )
        try:
            response = self._dispatch_with_session(
                delegated, subaction.action, subaction.payload,
            )
            return self.journal.complete_subaction(
                parent_session, delegated, intent, response,
            )
        finally:
            delegated.invalidate()
```

`dispatch_subaction` verifies and shares the already-held root lock; it never calls `handle`, creates a second lock owner, or exposes the delegated session to an adapter. `_dispatch_with_session` enters P11's controller-owned install orchestration, which consumes capabilities derived from the delegated session and owns installation, first activation, the real rollback drill, exact reactivation, current C3 validation, and persistence of `trial_control.ready`. P13 neither calls a low-level P11 mutator nor synthesizes a P11 receipt. Rollback caused by probation is likewise owned by P12 `G5Store`/`ProbationWatchdog`, which uses the same internal delegation boundary for P11 rollback.

After trial control is current, P13 starts probation and records the actual task lane through P12 stores. The protected task driver supplies only immutable task/execution artifact digests required by the P12 request schemas:

```python
start = probation_starts.start(
    scope.root_id, authorization.promotion_id,
    trial.receipt_digest, phase_key("probation-started"),
)
for task in probation_tasks.resolve(start.receipt_digest):
    route = routes.route(TaskRouteRequest(
        root_id=scope.root_id,
        promotion_id=authorization.promotion_id,
        task_id=task.task_id,
        task_descriptor_digest=task.task_descriptor_digest,
        input_artifact_digest=task.input_artifact_digest,
        permission_manifest_digest=task.permission_manifest_digest,
        idempotency_key=phase_key(f"route:{task.task_id}"),
    ))
    execution = probation_executor.run_or_resume(route)
    outcomes.record(TaskOutcomeInput(
        routing_receipt_digest=route.receipt_digest,
        runtime_execution_receipt_digest=execution.receipt_digest,
        recorded_input_artifact_digest=execution.recorded_input_artifact_digest,
        grader_artifact_digest=execution.grader_artifact_digest,
        replay_safety_receipt_digest=execution.replay_safety_receipt_digest,
        incident_artifact_digest=execution.incident_artifact_digest,
        idempotency_key=phase_key(f"outcome:{task.task_id}"),
    ))

selection = shadows.select(
    scope.root_id, authorization.promotion_id,
    phase_key("shadow-selection"),
)
shadow_receipts = tuple(
    shadows.run(
        scope.root_id, selection.receipt_digest, outcome_digest,
        phase_key(f"shadow:{outcome_digest}"),
    )
    for outcome_digest in selection.selected_outcome_digests
)
cutoff_sequence = ledger.verify().sequence
evidence = evidence_builder.build(
    scope.root_id, authorization.promotion_id, cutoff_sequence,
    phase_key(f"evidence:{cutoff_sequence}"),
)
g5 = g5_store.evaluate_and_commit(
    scope.root_id, authorization.promotion_id, evidence.receipt_digest,
    phase_key(f"G5:{cutoff_sequence}"),
)
```

Every start, route, outcome, selection, shadow, evidence, and G5 call above is wrapped by `MetaPhaseStore.run_native` in the implementation; the straight-line excerpt shows the exact P12 signatures. An open `G5Receipt` returns an open `MetaGateChainReceipt`. A later resume chooses a new ledger cutoff and G5 idempotency key but reuses all previously owner-verified phases. `observe_probation_signal` calls only `ProbationWatchdog.observe(root_id, promotion_id, idempotency_key)`, stores the returned typed `G5Receipt` under the same promotion phase family, and never calls P11 rollback itself.

Only a typed passed terminal G5 can reach the final calls:

```python
terminal_g5 = g5_store.require_terminal(
    scope.root_id, authorization.promotion_id, g5.receipt_digest,
)
stable = promotions.promote(
    scope.root_id, authorization.promotion_id,
    terminal_g5.receipt_digest, phase_key("stable-promotion"),
)
c4 = c4_store.evaluate_and_commit(
    scope.root_id, authorization.promotion_id, phase_key("C4"),
)
current_c4 = c4_store.current(scope.root_id)
if current_c4.receipt_digest != c4.receipt_digest:
    raise NativeReceiptRecoveryMismatch("C4 is not current")
```

`StablePromotionManager.promote` alone resolves canonical state, performs retention, and switches the stable tuple. `C4ConformanceStore.evaluate_and_commit` alone folds P11/P12 proof and constructs C4. P13 passes no state object, receipt object, proof collection, policy, or outcome boolean to either call. `GateProofRef` is derived after owner verification; only G5 populates `evidence_receipt_digest`, copied from the native `G5Receipt.evidence_receipt_digest` field.

- [ ] **Step 6: Run composition and recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_meta_old_supervisor_runner.py tests/selfloop/test_g0_g1.py tests/selfloop/test_progressive_gates.py tests/selfloop/test_development_conformance.py tests/selfloop/test_g4_runner.py tests/selfloop/test_adapter_trial_control.py tests/selfloop/test_trial_control_receipt.py tests/selfloop/test_probation_routing.py tests/selfloop/test_probation_outcomes.py tests/selfloop/test_probation_shadowing.py tests/selfloop/test_g5_and_watchdog.py tests/selfloop/test_c4_retention.py`

Expected: generated candidates and the proposed engine run only under the old pinned supervisor; readiness is a persisted `development.g0_g3.ready` event; G4 resolves pinned policy internally; P11 mutation occurs only through one minimal controller request; P12 stores all probation/native proofs; every restarted phase invokes its owner verifier and performs its native mutation at most once.

- [ ] **Step 7: Commit**

```bash
git add scripts/selfloop_supervisor/contracts.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/meta/store.py scripts/selfloop_supervisor/meta/candidate_materializer.py scripts/selfloop_supervisor/meta/old_supervisor_runner.py tests/selfloop/test_meta_old_supervisor_runner.py
git commit -m "feat(selfloop): compose old-supervisor meta gates"
```

### Task 5: Persist exact meta decisions and prove C5 through an executable temporary-root gate

**Files:**
- Create: `references/selfloop/policies/meta-acceptance-policy-v1.json`
- Create: `scripts/selfloop_supervisor/meta/evaluation.py`
- Create: `scripts/selfloop_supervisor/meta/c5_conformance.py`
- Create: `scripts/selfloop_supervisor/meta/c5_acceptance.py`
- Create: `scripts/validate_selfloop_c5.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `scripts/validate_v2.py`
- Test: `tests/selfloop/test_meta_evaluation.py`
- Test: `tests/selfloop/test_c5_acceptance.py`
- Modify: `tests/selfloop/test_adapter_c2.py`
- Modify: `tests/test_homebase_mcp.py`

**Interfaces:**
- Consumes: Task 3 `ReplayPairReceipt`, Task 4 generated-candidate and proposed-engine gate-chain receipts, protected `meta-acceptance.v1` policy from the old pinned bundle, P05 canonical ledger/artifact resolver, and task-local adapter runtime proof.
- Produces: `MetaMetrics`, exact `MetaDecision`, protected `MetaEvaluationService.evaluate_or_resume(session, meta_evaluation_id) -> MetaDecision`, `C5ConformanceReceipt`, protected `C5ConformanceService.commit(session, root_id, campaign_id, meta_evaluation_id, idempotency_key) -> C5ConformanceReceipt`, `C5ConformanceService.verify(receipt_digest) -> C5ConformanceReceipt`, and `run_temporary_c5_acceptance(root: Path) -> C5ConformanceReceipt`.
- Adapters may advertise C5 only from `C5ConformanceService.verify` against the current canonical ledger head and task-local runtime identity. Source-file presence never enables a conformance claim.

- [ ] **Step 1: Pin the exact meta acceptance policy**

Create `references/selfloop/policies/meta-acceptance-policy-v1.json` with canonical JSON:

```json
{
  "schema": "selfloop.meta-acceptance-policy.v1",
  "policyId": "meta-acceptance.v1",
  "requiredGateOrder": ["G0", "G1", "G2", "G3", "G4", "G5"],
  "requiredC4Conformance": "C4",
  "metricOrder": [
    "integrity_failures_ascending",
    "g4_survivors_descending",
    "g3_survivors_descending",
    "g2_survivors_descending",
    "sealed_benefit_descending",
    "root_cause_quality_descending",
    "tokens_per_survivor_ascending"
  ],
  "maximumIntegrityFailures": 0,
  "requireStrictImprovement": true,
  "allowedChangedPathPrefix": "scripts/selfloop_strategy/"
}
```

Copy this policy into the old pinned supervisor bundle, record its digest before replay starts, and reject a replay request whose policy digest differs.

- [ ] **Step 2: Write failing exact-decision, persisted-proof, adapter, and executable-validator tests**

```python
def test_meta_decision_records_every_proof_family(real_completed_meta_evaluation):
    decision = real_completed_meta_evaluation.service.evaluate_or_resume(
        real_completed_meta_evaluation.session,
        real_completed_meta_evaluation.meta_evaluation_id,
    )
    assert decision.outcome == "promote"
    assert len(decision.gate_receipt_digests) == 6
    assert decision.c4_receipt_digest
    assert decision.raw_artifact_digests
    assert decision.usage_receipt_digests
    assert decision.sandbox_receipt_digests


def test_c5_service_resolves_proofs_from_store_not_caller_values(real_completed_meta_evaluation):
    receipt = real_completed_meta_evaluation.c5.commit(
        real_completed_meta_evaluation.c5_session,
        real_completed_meta_evaluation.root_id,
        real_completed_meta_evaluation.campaign_id,
        real_completed_meta_evaluation.meta_evaluation_id,
        "c5:meta-7",
    )
    assert receipt.conformance == "C5"
    real_completed_meta_evaluation.artifacts.delete(receipt.gate_receipt_digests[4])
    with pytest.raises(ConformanceProofMissing, match="G4"):
        real_completed_meta_evaluation.c5.verify(receipt.receipt_digest)


def test_adapter_does_not_claim_c5_from_source_presence(adapter_runtime):
    adapter_runtime.write_c5_module_without_receipt()
    response = adapter_runtime.status()
    assert response["conformance"] == "C4"


def test_executable_c5_validator_uses_real_temporary_pipeline(repo_root):
    completed = subprocess.run(
        [sys.executable, "scripts/validate_selfloop_c5.py", "--repo-root", str(repo_root), "--json"],
        cwd=repo_root, text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["conformance"] == "C5"
    assert payload["gateOrder"] == ["G0", "G1", "G2", "G3", "G4", "G5"]
    assert payload["sandboxBackend"] == "enforced"
    assert payload["proofMode"] == "real-temp-root-p09-p12"
```

- [ ] **Step 3: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_meta_evaluation.py tests/selfloop/test_c5_acceptance.py`

Expected: FAIL importing `selfloop_supervisor.meta.evaluation` and `selfloop_supervisor.meta.c5_conformance`.

- [ ] **Step 4: Implement exact metrics and the persisted meta decision**

```python
@dataclass(frozen=True)
class MetaMetrics:
    root_cause_quality: float
    g2_survivors: int
    g3_survivors: int
    g4_survivors: int
    sealed_benefit: float
    total_tokens: int
    tokens_per_survivor: float
    failed_experiment_reuse: int
    attempts_to_promotion: int
    integrity_failures: int
    receipt_digest: str


@dataclass(frozen=True)
class MetaDecision:
    root_id: str
    campaign_id: str
    meta_evaluation_id: str
    outcome: str
    reason: str
    stable_engine_release_id: str
    proposed_engine_release_id: str
    selected_candidate_release_id: str | None
    replay_receipt_digest: str
    stable_metrics_digest: str
    proposed_metrics_digest: str
    gate_chain_receipt_digest: str | None
    gate_receipt_digests: tuple[str, ...]
    evidence_receipt_digest: str | None
    c4_receipt_digest: str | None
    sandbox_receipt_digests: tuple[str, ...]
    usage_receipt_digests: tuple[str, ...]
    raw_artifact_digests: tuple[str, ...]
    old_supervisor_digest: str
    old_policy_digest: str
    old_evaluator_digest: str
    spec_digest: str
    receipt_digest: str


class MetaEvaluationService:
    def evaluate_or_resume(self, session, meta_evaluation_id):
        require_live_lock_owning_session_for_meta(session, meta_evaluation_id)
        if existing := self.store.load_terminal_decision(meta_evaluation_id):
            return self.store.verify_meta_decision(existing.receipt_digest)
        pair = self.store.load_verified_replay_pair(meta_evaluation_id)
        generated = self.runner.evaluate_generated_candidates(session, pair)
        stable_metrics = compute_meta_metrics(generated, engine="stable")
        proposed_metrics = compute_meta_metrics(generated, engine="proposed")
        if not self.policy.strictly_better(proposed_metrics, stable_metrics):
            return self.store.commit_meta_decision(MetaDecision.retain(pair, stable_metrics, proposed_metrics))
        chain = self.runner.run_proposed_engine_to_c4(session, pair, generated)
        if chain.status == "open":
            return self.store.commit_open_decision(MetaDecision.open(pair, stable_metrics, proposed_metrics, chain))
        if chain.status != "passed":
            return self.store.commit_meta_decision(MetaDecision.retain_with_chain(pair, stable_metrics, proposed_metrics, chain))
        decision = MetaDecision.promote(pair, stable_metrics, proposed_metrics, chain, SPEC_DIGEST)
        return self.store.commit_meta_decision(decision)
```

`compute_meta_metrics` folds only native gate/evaluation, budget, and artifact receipts resolved from the store. Attempts equal actual materialized candidates; reuse counts only validated replay failure IDs referenced by a materialized candidate; integrity failures come from old-supervisor receipts. `MetaDecision.open` is nonterminal and is replaced by the same idempotency key after G5 advances. Retain/promote/failed outcomes append one `meta.evaluation.terminal` event so Task 2's next cycle resets at the correct boundary.

- [ ] **Step 5: Implement store-resolved C5, runtime-gated adapters, and the real temporary-root acceptance path**

```python
@dataclass(frozen=True)
class C5ConformanceReceipt:
    root_id: str
    campaign_id: str
    meta_evaluation_id: str
    conformance: str
    active_engine_release_id: str
    replay_receipt_digest: str
    decision_receipt_digest: str
    stable_metrics_digest: str
    proposed_metrics_digest: str
    gate_receipt_digests: tuple[str, ...]
    evidence_receipt_digest: str
    c4_receipt_digest: str
    sandbox_receipt_digests: tuple[str, ...]
    usage_receipt_digests: tuple[str, ...]
    raw_artifact_digests: tuple[str, ...]
    old_supervisor_digest: str
    old_policy_digest: str
    old_evaluator_digest: str
    spec_digest: str
    ledger_event_digest: str
    receipt_digest: str


class C5ConformanceService:
    def commit(
        self, session, root_id, campaign_id,
        meta_evaluation_id, idempotency_key,
    ):
        require_live_lock_owning_session(session, root_id, campaign_id)
        capability = session.issue(
            operation=self.operations.c5_commit,
            resource_id=meta_evaluation_id,
            phase="C5",
        )
        require_equal(session.request_idempotency_key, idempotency_key)
        self.store.verify_anchor()
        decision = self.store.load_terminal_decision(meta_evaluation_id)
        if decision.outcome != "promote":
            raise ConformanceProofMissing("promoted terminal meta decision required")
        chain = self.store.load_gate_chain(decision.gate_chain_receipt_digest)
        native = self.phases.verify_gate_chain(
            session=session,
            chain=chain,
            expected_gate_receipt_digests=decision.gate_receipt_digests,
        )
        g5 = native[-1]
        if tuple(receipt.gate.value for receipt in native) != ("G0", "G1", "G2", "G3", "G4", "G5"):
            raise ConformanceProofMissing("ordered G0-G5 receipts required")
        if any(receipt.status.value != "passed" for receipt in native):
            raise ConformanceProofMissing("all native gates must be passed and verified")
        if decision.evidence_receipt_digest != g5.evidence_receipt_digest:
            raise ConformanceProofMissing("G5 evidence receipt mismatch")
        c4 = self.phases.verify_current_c4(session, chain)
        if c4.conformance != "C4" or c4.receipt_digest != chain.c4_receipt_digest:
            raise ConformanceProofMissing("verified C4 receipt required")
        sandboxes = tuple(self.store.resolve_sandbox(digest) for digest in decision.sandbox_receipt_digests)
        if not sandboxes or any(receipt.status != "enforced" for receipt in sandboxes):
            raise ConformanceProofMissing("enforced sandbox receipts required")
        for digest in (*decision.usage_receipt_digests, *decision.raw_artifact_digests):
            self.store.resolve_verified_artifact(digest)
        with self.service_context.bind(capability):
            return self.store.commit_c5_receipt(
                root_id, campaign_id, decision, chain, c4, sandboxes,
                capability.idempotency_key,
            )
```

`verify_gate_chain` is Task 4's owner-specific verifier, not a generic digest resolver: under distinct session-issued verification capabilities it reopens the P02 bundle, resolves P09 G0-G3/readiness, re-enters P10 G4 with its stored native idempotency key, calls P12 `G5Store.require_terminal`, and compares every native receipt/event digest. `verify_current_c4` similarly invokes `C4ConformanceStore.current` under its own capability. C5 cannot turn an outer phase row or hash-shaped string into native proof.

```python
# scripts/validate_selfloop_c5.py
def main(argv=None):
    arguments = parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="selfloop-c5-") as directory:
        receipt = run_temporary_c5_acceptance(
            repo_root=arguments.repo_root.resolve(),
            temporary_root=Path(directory),
            required_sandbox_backend="/usr/bin/sandbox-exec",
        )
        payload = {
            "conformance": receipt.conformance,
            "gateOrder": ["G0", "G1", "G2", "G3", "G4", "G5"],
            "sandboxBackend": "enforced",
            "proofMode": "real-temp-root-p09-p12",
            "receiptDigest": receipt.receipt_digest,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
```

`run_temporary_c5_acceptance` creates two real temporary Git release roots, byte-bearing P02 `ReleaseBundleReceipt` rows, a temporary anchored P05 ledger, immutable replay/proposal/sealed artifact roots, temporary slots/configuration, and a protected old-supervisor bundle. It enters through the temporary root's real `SelfloopController`, which holds the root lock, persists the meta intent, creates the `MutationSession`, and supplies per-phase capabilities. It reopens each bundle with `ReleaseBundleStore.open_verified`, then invokes Task 3 replay, Task 4 materialization, real P09 G0-G3, real P10 sealed G4, P11 typed controller install through persisted `trial_control.ready`, and real P12 routed task outcomes/shadows/evidence/G5/canonical stable promotion/C4. Deterministic task programs execute through P03's actual Darwin sandbox; historical timestamps are signed temporary ledger inputs folded by the real P12 evidence builder, not summary booleans or a substituted G5 policy. The acceptance fails when the backend is unavailable, a session/capability is missing or reused, a bundle attestation or native receipt is missing, any process did not produce an enforced sandbox receipt, or any digest cannot be resolved.

`scripts/validate_v2.py --check-eval` must execute `python3 scripts/validate_selfloop_c5.py --repo-root <ROOT> --json`, parse its terminal JSON, and require `conformance == "C5"`, six ordered gates, `sandboxBackend == "enforced"`, and a receipt that re-verifies from the temporary store. It must not check only that a Python file exists. The kernel stores the latest verified C5 receipt digest in canonical state. CLI/MCP `status` reports C5 only when `C5ConformanceService.verify` succeeds and the task-local host reports the same active engine release; otherwise it retains the last proven stage and a precise blocker.

- [ ] **Step 6: Run the P13 acceptance slice and complete proof gate**

Run: `python3 -m pytest -q tests/selfloop/test_meta_engine_protocol.py tests/selfloop/test_meta_triggers.py tests/selfloop/test_meta_replay.py tests/selfloop/test_meta_recovery.py tests/selfloop/test_meta_old_supervisor_runner.py tests/selfloop/test_meta_evaluation.py tests/selfloop/test_c5_acceptance.py tests/selfloop/test_adapter_c2.py tests/test_homebase_mcp.py && python3 scripts/validate_selfloop_c5.py --repo-root . --json && python3 scripts/validate_v2.py --check-eval && git diff --check`

Expected: all tests pass; the standalone validator emits one C5 JSON receipt with real P09-P12 proof mode and enforced sandbox; `validate_v2.py` exits `0`; adapters remain below C5 when the stored/runtime proof is removed; diff check is silent.

- [ ] **Step 7: Commit**

```bash
git add references/selfloop/policies/meta-acceptance-policy-v1.json scripts/selfloop_supervisor/meta/evaluation.py scripts/selfloop_supervisor/meta/c5_conformance.py scripts/selfloop_supervisor/meta/c5_acceptance.py scripts/validate_selfloop_c5.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py scripts/validate_v2.py tests/selfloop/test_meta_evaluation.py tests/selfloop/test_c5_acceptance.py tests/selfloop/test_adapter_c2.py tests/test_homebase_mcp.py
git commit -m "feat(selfloop): persist and execute C5 proof"
```

## Plan 13 Completion Gate

- [ ] META counters are ledger-derived strictly after the newest terminal meta-evaluation event.
- [ ] Engine request/result identities bind the launched engine release and immutable champion root; results contain bounded IDs only.
- [ ] Completed stable/proposed replay inputs and grant terms are equal and grant IDs are distinct; every side that actually launched is reconciled exactly once, while a failed stable side creates no proposed launch claim.
- [ ] Every replay, materialization, gate, controller-owned trial-control, probation, decision, and conformance phase has an intent/completion receipt; recovery reuses raw artifacts and re-enters each native owner verifier.
- [ ] The old pinned supervisor explicitly composes the real P09-P12 APIs and verifies every native receipt before normalization.
- [ ] `MetaDecision` has one exact schema for open, retain, and promote outcomes and persists all replay/metrics/gate/C4/sandbox/usage/raw proof references.
- [ ] C5 resolves and verifies actual G0-G5, C4, sandbox, usage, and raw artifacts from the protected store and is hash-linked in the ledger.
- [ ] The standalone temporary-root validator runs the actual OS sandbox and P09-P12 stack; synthetic gates, fake C4/G5 receipts, and source-presence claims fail.
- [ ] CLI/MCP advertise C5 only when stored conformance and task-local active-engine proofs agree.
- [ ] Execute the roadmap's **Shared protected-runtime rollover execution task** with `SOURCE_STAGE=P12`, `TARGET_STAGE=P13`, and the exact committed P13 SHA; verify its authorization/pending/activation/rescue/fresh-loader receipt chain before runtime-facing META/C5 verification is accepted.
