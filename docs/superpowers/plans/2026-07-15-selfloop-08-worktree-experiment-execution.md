# Worktree Experiment Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete C2 by executing each selected card as either a fixed DIAGNOSE probe or one committed candidate in an isolated Git worktree, with C1 foundation checks and a terminal experiment receipt.

**Architecture:** The protected controller creates worktrees from an immutable champion SHA, grants resources, runs the evolvable builder through schema-validated JSON subprocess, verifies commits and release identity, executes C1 foundation checks, archives raw artifacts, and commits the terminal receipt to the anchored ledger. Strategy code never edits the primary checkout or supervisor state; process tracking, review enforcement, recovery, and terminal classification remain protected.

**Tech Stack:** Python 3.10+, standard-library `subprocess`, `hashlib`, `json`, `pathlib`, Git worktrees, Plan 05 ledger/controller, Plan 07 grants, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- The minimum valid C2 experiment is exactly one of: a fixed falsifiable `DIAGNOSE` probe with raw result and terminal receipt, or a committed candidate with C1 foundation checks and terminal receipt. Free text never satisfies the contract.
- Every research-advancing invocation at C2 must execute at least one valid experiment before returning success. Proposal-only completion fails.
- Candidate worktrees start from the immutable stable champion SHA or recorded parent candidate SHA, never dirty primary bytes.
- Experiment, candidate, repair, worktree, build, commit, foundation, review, and process IDs are reserved in the P05 phase journal before effects. Worktree create/commit/remove and every receipt/budget/reservation write require an exact capability from the current `MutationSession`.
- Branches use `codex/selfloop/<campaign-id>/<candidate-id>`; every evaluated state is committed, and uncommitted bytes are excluded from evidence.
- One primary candidate exists per mutating attempt; repairs are linked sub-attempts and do not reset gate history.
- Large/meta sequential commits must each be buildable and carry commit, diff hash, changed paths, verification, and remaining hypothesis.
- Architecture, permissions, persistence, promotion, evaluation, or selfloop changes require an independent review receipt for the exact current diff hash before later G2 work.
- Candidate subprocesses receive no sealed paths, supervisor store, anchor, champion pointer, credentials, or external-effect authority.
- Selection, diagnosis, building, foundation evaluation, and independent review use distinct root/campaign-scoped grants. A reconciled selection grant is never reused for experiment work, and every broker returns a terminal call receipt so the executor can reconcile before raising.
- Candidate, repair, builder, and agent reservations are acquired through P07 before their corresponding worktree or child-process effect and receive terminal release/reconciliation receipts before root unlock. Every builder, foundation, review, or evaluator child launches through P05's durable `ProcessRegistry.launch`; direct `Popen` is forbidden.
- Raw process/broker/experiment receipts are observations only. Protected final experiment receipts are separate exact `kind`/`stage` dataclasses derived from persisted raw event digests, verified artifacts, committed Git/release bytes, budget/reservation events, and queue state. A raw receipt or caller boolean can never satisfy C2.
- Candidate and champion release references always carry `release_id`, `source_attestation_digest`, and path-independent release-bundle `receipt_digest`, so later gates can call `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, compare `receipt_digest`, and recover the exact bytes.
- Every final or terminal-failed experiment receipt contains the complete section-20 terminal key set: original hypothesis, candidate commit, release ID, changed paths, reviewer receipt, G0-Gn results, paired-baseline identity, resource usage, outcome, archive path, and search-statistic updates. Kind-specific dataclasses keep those keys required. A genuinely inapplicable value is explicit `null` (or an empty changed-path sequence) and requires a protected, field-specific `not_applicable_reason`; omission and caller-authored reasons are invalid.
- Opportunity queue writes continue to use only P06's normative `queued|selected|implemented|invalidated|archived` enum. Experiment `supported|falsified|inconclusive|failed|aborted|budget_exhausted` outcomes live only on experiment receipts.
- C2 execution does not promote or install candidates. G0-G5 behavior belongs to later plans.

---

### Task 1: Create candidates from immutable champion commits

**Files:**
- Create: `scripts/selfloop_supervisor/candidates.py`
- Create: `scripts/selfloop_supervisor/git_runner.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Test: `tests/selfloop/test_candidates.py`

**Interfaces:**
- Produces: `CandidateManager.create(scope: ObjectScope, card: ExperimentCard, base_commit: str, candidate_id: str, reservation_event_digest: str, capability: MutationCapability) -> CandidateWorkspace`, `commit(candidate_id: str, message: str, capability: MutationCapability) -> CandidateCommit`, and `remove(candidate_id: str, capability: MutationCapability) -> RemovalReceipt`.
- `CandidateWorkspace` records pre-journaled candidate ID, worktree path, branch, base SHA, Git common directory, immutable parent release ID/source-attestation/receipt digests, candidate reservation event digest, and create-intent/receipt event digests.
- `create`, `commit`, and `remove` require respectively `WORKTREE_CREATE`, `WORKTREE_COMMIT`, and `WORKTREE_REMOVE` for the exact candidate and phase. They record intent before Git, replay an existing receipt, and reject a naked idempotency string, missing reservation, cross-session capability, unexpected branch/HEAD, or unjournaled path.

- [ ] **Step 1: Write failing real-worktree and dirty-primary-isolation tests**

```python
def test_candidate_uses_reserved_id_recorded_sha_and_ignores_dirty_primary(
    seed_repo, manager, selected_card, candidate_reservation,
):
    stable_sha = seed_repo.commit("stable.txt", "stable\n")
    (seed_repo.path / "dirty.txt").write_text("must not cross boundary\n")
    workspace = manager.create(
        scope(), selected_card, stable_sha, candidate_id="candidate-1",
        reservation_event_digest=candidate_reservation.event_digest,
        capability=worktree_capability("create", "candidate-1"),
    )
    assert workspace.branch == "codex/selfloop/campaign-1/candidate-1"
    assert git(workspace.path, "rev-parse", "HEAD") == stable_sha
    assert not (workspace.path / "dirty.txt").exists()
    assert workspace.path != seed_repo.path

def test_worktree_mutations_require_matching_session_capabilities(manager, selected_card, stable_sha, reservation):
    with pytest.raises(MutationDenied, match="WORKTREE_CREATE capability required"):
        manager.create(scope(), selected_card, stable_sha, "candidate-1", reservation.event_digest, None)
    workspace = manager.create(
        scope(), selected_card, stable_sha, "candidate-1", reservation.event_digest,
        worktree_capability("create", "candidate-1", session="session-a"),
    )
    with pytest.raises(MutationDenied, match="session mismatch"):
        manager.commit(
            workspace.candidate_id, "candidate commit",
            worktree_capability("commit", "candidate-1", session="session-b"),
        )

def test_create_replays_after_worktree_side_effect_without_duplicate_branch(manager_factory, fixture):
    first = manager_factory(crash_after="git-worktree-added")
    with pytest.raises(SimulatedCrash):
        first.create(**fixture.create_arguments)
    resumed = manager_factory().create(**fixture.create_arguments)
    assert resumed.candidate_id == fixture.candidate_id
    assert fixture.repo.worktrees_for_branch(resumed.branch) == (resumed.path,)
```

- [ ] **Step 2: Run and confirm candidate modules are absent**

Run: `python3 -m pytest -q tests/selfloop/test_candidates.py`

Expected: collection fails with missing `candidates`.

- [ ] **Step 3: Implement worktree creation with exact SHA and branch validation**

```python
capability.require(MutationOperation.WORKTREE_CREATE, resource_id=candidate_id)
branch = f"codex/selfloop/{scope.campaign_id}/{candidate_id}"
self.journal.record_intent(
    scope, "worktree.create",
    {"candidateId": candidate_id, "branch": branch, "baseCommit": base_commit,
     "reservationEventDigest": reservation_event_digest},
    capability.idempotency_key,
)
self.git.run(repo_root, "cat-file", "-e", f"{base_commit}^{{commit}}")
self.git.run(repo_root, "worktree", "add", "-b", branch, str(worktree_path), base_commit)
head = self.git.run(worktree_path, "rev-parse", "HEAD").stdout.strip()
if head != base_commit:
    raise CandidateIntegrityError(f"expected {base_commit}, loaded {head}")
return self.journal.commit_worktree_receipt(scope, candidate_id, branch, worktree_path, capability)
```

`candidate_id` is supplied by the controller's earlier `object.id.reserved` event; `CandidateManager` has no ID generator. Recovery inspects Git worktree metadata after an interrupted create and either commits the matching receipt or removes only the exact uncommitted disposable worktree under a separate removal capability. Commit and remove use the same intent/receipt pattern.

- [ ] **Step 4: Run candidate tests**

Run: `python3 -m pytest -q tests/selfloop/test_candidates.py`

Expected: `8 passed`.

- [ ] **Step 5: Commit candidate management**

```bash
git add scripts/selfloop_supervisor/candidates.py scripts/selfloop_supervisor/git_runner.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/contracts.py tests/selfloop/test_candidates.py
git commit -m "feat(selfloop): create isolated candidate worktrees"
```

### Task 2: Execute fixed diagnosis or one mutating builder

**Files:**
- Create: `references/selfloop/policies/diagnose-probes-v1.json`
- Create: `scripts/selfloop_supervisor/experiment_receipts.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/process_registry.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Create: `scripts/selfloop_supervisor/builder_broker.py`
- Create: `scripts/selfloop_supervisor/candidate_policy.py`
- Create: `scripts/selfloop_supervisor/foundation_checks.py`
- Create: `scripts/selfloop_supervisor/experiments.py`
- Create: `scripts/selfloop_strategy/experiment_builder.py`
- Modify: `scripts/selfloop_strategy/worker.py`
- Test: `tests/selfloop/test_experiment_execution.py`

**Interfaces:**
- Consumes: P02 `ReleaseBuilder`, `ReleaseBundleStore.materialize`, and `open_verified(release_id, source_attestation_digest) -> ReleaseBundleReceipt`; P03 evaluation/restricted-process policies; P04 `bootstrap_g0.v1`/`bootstrap_critical_g1.v1`; the pinned `diagnose-probes-v1.json`; P05 session/phase/process registry; and P07 budget/reservation repositories. Candidate checks reuse policies but never write seed pointers.
- Produces exact receipts registered in P06 dispatch: `RawDiagnoseExperimentReceipt(kind="diagnose-experiment", stage="raw")`, `RawCandidateExperimentReceipt(kind="candidate-experiment", stage="raw")`, `RawRepairExperimentReceipt(kind="repair-experiment", stage="raw")`, and corresponding `Failed*ExperimentReceipt(stage="terminal-failed")`. Final variants are declared here but may be constructed only by Task 4's protected finalizer. Every terminal-failed variant fixes the complete terminal key set; pre-effect fields are explicit nulls with protected `failure_before_candidate`, `failure_before_release`, `review_not_required`, `gate_not_reached`, or `baseline_not_established` reasons selected from an exact per-field table.
- Raw receipts carry observations, raw artifact/call event digests, IDs, grants/budget/reservation events, commit/diff and `ReleaseBundleReceipt.release_identity`, `manifest_digest`, `source_attestation_digest`, and path-independent `receipt_digest`. They do not carry `terminal=true`, promotability, learning decisions, queue status changes, conformance, or a caller-supplied ledger digest.
- Protected brokers produce `ProcessLaunchSpec` and parse a registered terminal process receipt: `BuilderBroker.launch_spec(card, workspace, grant)`, `BuilderBroker.collect(terminal_process_event_digest, grant) -> BuilderCallReceipt`, and analogous foundation/probe methods. Every child is spawned by `ProcessRegistry.launch` after its launch intent and reaches a protected terminal event through `await_terminal`; brokers own credentials/parsers but have no ledger, spawn, reconciliation, or capability authority.
- Produces session-bound `ExperimentExecutor.execute(card: ExperimentCard, session: MutationSession, experiment_id: str) -> RawExperimentReceipt | FailedExperimentReceipt` and `execute_repair(parent_final_event_digest: str, session: MutationSession, experiment_id: str, repair_id: str) -> RawRepairExperimentReceipt | FailedRepairExperimentReceipt`. The executor authorizes/reconciles fresh phase grants, persists each raw call through a receipt capability, and commits either one raw experiment event or one terminal-failed event before returning.
- A DIAGNOSE card names only a versioned `probeId` and expected falsifiable predicate. The supervisor resolves its command, readable roots, timeout, and parser from the immutable policy; arbitrary card-supplied commands are invalid.
- Foundation checks prove clean candidate commit, whole-release digest, manifest/dependency completeness, explicit candidate release root, isolated profile, nonempty eligible checks, complete provenance, and loaded-release identity.

- [ ] **Step 1: Write failing DIAGNOSE and committed-candidate contract tests**

```python
def test_diagnose_requires_fixed_probe_and_raw_observation_receipt(executor, diagnose_card):
    receipt = executor.execute(diagnose_card, experiment_session("diagnose-1"), "experiment-diagnose-1")
    assert receipt.kind == "diagnose-experiment" and receipt.stage == "raw"
    assert receipt.probe.question == "Does candidate profile load release release-1?"
    assert receipt.probe.command == ("python3", "-c", "print('release-1')")
    assert receipt.raw_artifact_sha256
    assert receipt.outcome in {"supported", "falsified", "inconclusive"}
    assert not hasattr(receipt, "promotable") and not hasattr(receipt, "terminal")

def test_diagnose_rejects_card_supplied_command_and_uses_restricted_launcher(executor, diagnose_card):
    rejected = executor.execute(
        replace(diagnose_card, command=("sh", "-c", "cat ~/.codex/sips/selfloop/supervisor/state.sqlite3")),
        experiment_session("diagnose-reject-1"), "experiment-diagnose-reject-1",
    )
    assert rejected.stage == "terminal-failed"
    receipt = executor.execute(
        replace(diagnose_card, probe_id="loaded-release-identity.v1"),
        experiment_session("diagnose-2"), "experiment-diagnose-2",
    )
    assert receipt.probe.policy_digest == diagnose_policy_digest
    assert receipt.probe.sandbox_backend_receipt.status == "enforced"

def test_mutating_experiment_requires_commit_and_foundation_checks(executor, improve_card):
    receipt = executor.execute(improve_card, experiment_session("improve-1"), "experiment-improve-1")
    assert receipt.kind == "candidate-experiment" and receipt.stage == "raw"
    assert receipt.candidate_commit
    assert receipt.release_id
    assert receipt.source_attestation_digest and receipt.release_bundle_receipt_digest
    assert receipt.foundation.status == "passed"
    assert receipt.builder.usage.source in {"provider", "conservative-reservation"}
    assert receipt.builder.grant_status == "reconciled"
    assert receipt.foundation.grant_status == "reconciled"
    assert receipt.builder.grant_id != receipt.foundation.grant_id
    reopened = executor.release_bundles.open_verified(receipt.release_id, receipt.source_attestation_digest)
    assert reopened.receipt_digest == receipt.release_bundle_receipt_digest

def test_repair_keeps_card_mechanism_and_parent_history(executor, failed_candidate_final_event):
    parent = FinalCandidateExperimentReceipt.from_event(failed_candidate_final_event)
    repaired = executor.execute_repair(
        failed_candidate_final_event.digest, experiment_session("repair-1"),
        experiment_id="experiment-repair-1", repair_id="repair-1",
    )
    assert repaired.card_id == parent.card_id
    assert repaired.mechanism == parent.mechanism
    assert repaired.parent_experiment_id == parent.experiment_id
    assert repaired.repair_index == parent.repair_index + 1

def test_selection_grant_is_not_reused_for_any_experiment_phase(executor, improve_card, selection_grant):
    receipt = executor.execute(
        improve_card, experiment_session("improve-metering-1"), "experiment-improve-metering-1",
    )
    phase_grants = {receipt.builder.grant_id, receipt.foundation.grant_id}
    assert selection_grant.grant_id not in phase_grants
    assert all(executor.ledger.event_by_digest(digest).event_type == "budget.reconciled" for digest in receipt.budget_event_digests)

def test_candidate_builder_agent_and_process_are_reserved_and_journaled_before_effect(executor, improve_card):
    receipt = executor.execute(improve_card, experiment_session("ordered-1"), "experiment-ordered-1")
    assert executor.ledger.event_sequence("budget.reservation.created", kind="candidate") < executor.ledger.event_sequence("worktree.create.intended")
    assert executor.ledger.event_sequence("budget.reservation.created", kind="builder") < executor.ledger.event_sequence("process.launch.intended")
    assert executor.ledger.event_sequence("budget.reservation.created", kind="agent") < executor.ledger.event_sequence("process.launch.intended")
    assert executor.ledger.event_by_digest(receipt.builder.process_event_digest).event_type == "process.terminal"

def test_ordinary_builder_cannot_change_protected_paths(executor, protected_path_card):
    failed = executor.execute(
        protected_path_card, experiment_session("protected-1"), "experiment-protected-1",
    )
    assert failed.kind == "candidate-experiment" and failed.stage == "terminal-failed"
    assert failed.error.code == "candidate-policy-denied"
    assert failed.budget_event_digests and failed.reservation_event_digests
    assert executor.candidates.commits_for(protected_path_card.card_id) == ()
```

- [ ] **Step 2: Run and observe missing execution modules**

Run: `python3 -m pytest -q tests/selfloop/test_experiment_execution.py`

Expected: collection fails with missing `experiments`.

- [ ] **Step 3: Implement the two allowed experiment forms and reject dirty/free-text results**

```python
def run_registered_call(self, session, phase, usage_request, launch_spec, collector):
    grant = self.budget.authorize(
        usage_request,
        session.issue(MutationOperation.BUDGET_GRANT, phase, f"{phase}:grant"),
    )
    started = self.processes.launch(
        session.scope, session.intent_id, launch_spec(grant),
        session.issue(MutationOperation.PROCESS_LAUNCH, phase, f"{phase}:process"),
    )
    terminal = self.processes.await_terminal(
        started.process_id,
        session.issue(MutationOperation.PROCESS_RECONCILE, started.process_id, f"{phase}:terminal"),
    )
    call = self.phases.persist_raw(
        session, f"{phase}:raw", collector(terminal.event_digest, grant),
        session.issue(MutationOperation.RECEIPT_PERSIST, phase, f"{phase}:raw"),
    )
    budget = self.budget.reconcile(
        grant.grant_id, call.usage_receipt,
        session.issue(MutationOperation.BUDGET_RECONCILE, grant.grant_id, f"{phase}:reconcile"),
    )
    call.require_success()
    return call, budget

def execute(self, card, session, experiment_id):
    scope = session.scope
    try:
        if card.operator == "DIAGNOSE":
            probe = self.diagnose_policy.resolve(card.probe_id, card.expected_predicate)
            call, budget = self.run_registered_call(
                session, "diagnose", UsageRequest.for_tool(scope, f"diagnose:{probe.probe_id}", 1),
                lambda grant: self.probe_broker.launch_spec(probe, grant), self.probe_broker.collect,
            )
            raw = RawDiagnoseExperimentReceipt.derive(experiment_id, card, probe, call, budget)
            return self.receipts.commit_raw(
                session, raw,
                session.issue(MutationOperation.RECEIPT_PERSIST, experiment_id, "persist-raw-experiment"),
            )

        candidate_id = self.phases.reserve_id(session, "candidate-id", "candidate")
        candidate_reservation = self.budget.reserve_candidate(
            scope, candidate_id,
            session.issue(MutationOperation.BUDGET_RESERVE, candidate_id, "reserve-candidate"),
        )
        stable = self.state.stable_champion(scope.root_id)
        workspace = self.candidates.create(
            scope, card, stable.commit_sha, candidate_id, candidate_reservation.event_digest,
            session.issue(MutationOperation.WORKTREE_CREATE, candidate_id, "create-worktree"),
        )
        builder_id = self.phases.reserve_id(session, "builder-id", "builder")
        agent_id = self.phases.reserve_id(session, "builder-agent-id", "agent")
        builder_reservation = self.budget.acquire_builder(
            scope, builder_id, candidate_id,
            session.issue(MutationOperation.BUDGET_RESERVE, builder_id, "reserve-builder"),
        )
        agent_reservation = self.budget.acquire_agent(
            scope, agent_id, "candidate-builder",
            session.issue(MutationOperation.BUDGET_RESERVE, agent_id, "reserve-builder-agent"),
        )
        builder, builder_budget = self.run_registered_call(
            session, "builder", UsageRequest.for_builder(scope, card),
            lambda grant: self.builder_broker.launch_spec(card, workspace, grant),
            self.builder_broker.collect,
        )
        builder_release = self.budget.release_reservation(
            builder_reservation.reservation_id, builder.usage_receipt,
            session.issue(MutationOperation.BUDGET_RELEASE, builder_id, "release-builder"),
        )
        agent_release = self.budget.release_reservation(
            agent_reservation.reservation_id, builder.usage_receipt,
            session.issue(MutationOperation.BUDGET_RELEASE, agent_id, "release-builder-agent"),
        )
        classification = self.candidate_policy.classify(self.git.changed_paths(workspace.path))
        commit = self.candidates.commit(
            candidate_id, builder.payload["commitMessage"],
            session.issue(MutationOperation.WORKTREE_COMMIT, candidate_id, "commit-candidate"),
        )
        if self.git.is_dirty(workspace.path):
            raise ExperimentRejected("uncommitted candidate bytes")
        build = self.release_builder.build(
            scope.root_id, workspace.path, commit.commit_sha,
            self.release_metadata.for_campaign(scope),
        )
        materialized = self.release_bundles.materialize(build)
        release_bundle = self.release_bundles.open_verified(
            materialized.release_identity.release_id, materialized.source_attestation_digest,
        )
        foundation, foundation_budget = self.run_registered_call(
            session, "foundation", UsageRequest.for_evaluation(scope, self.foundation.policy),
            lambda grant: self.foundation.launch_spec(workspace, release_bundle, grant),
            self.foundation.collect,
        )
        candidate_consumed = self.budget.release_reservation(
            candidate_reservation.reservation_id, ReservationUsage(status="consumed"),
            session.issue(MutationOperation.BUDGET_RELEASE, candidate_id, "consume-candidate"),
        )
        raw = RawCandidateExperimentReceipt.derive(
            experiment_id, card, workspace, commit, classification, release_bundle,
            builder, foundation, budgets=(builder_budget, foundation_budget),
            reservations=(candidate_reservation, builder_reservation, agent_reservation),
            reservation_terminals=(candidate_consumed, builder_release, agent_release),
        )
        return self.receipts.commit_raw(
            session, raw,
            session.issue(MutationOperation.RECEIPT_PERSIST, experiment_id, "persist-raw-experiment"),
        )
    except BaseException as error:
        self.resources.reconcile_started(session, experiment_id, conservative=True)
        return self.receipts.commit_failed_from_journal(
            session, experiment_id, card, error,
            session.issue(MutationOperation.RECEIPT_PERSIST, experiment_id, "persist-failed-experiment"),
        )
```

Ship `diagnose-probes-v1.json` with exact argv templates, parsers, input schemas, timeouts, and allowed read/write roots. Validate its digest from the pinned supervisor bundle before resolving a probe. The probe launch spec grants no supervisor/credential/sealed access, archives raw stdout/stderr, and fails closed if the OS sandbox backend is unavailable. No free-text shell, interpolated command, or candidate-provided parser is accepted.

`BuilderBroker` first obtains a schema-validated build instruction from the evolvable strategy subprocess, then describes only grant-authorized calls inside the candidate worktree. P05's trampoline/process registry performs the spawn and preserves terminal provider/process/tool usage even on failure. Foundation uses the same launch path. The executor persists each raw call, reconciles once before `require_success`, releases builder/agent reservations with terminal receipts after process reconciliation, and conservatively charges/reconciles them on failure. `commit_raw` appends `experiment.raw-recorded`; it does not claim C2 completion. `commit_failed_from_journal` appends exactly one kind-specific terminal-failed event with every raw artifact, budget event, reservation event, last commit, and incomplete phase.

`execute_repair` resolves the parent final event from the ledger, reserves the supplied repair ID with `reserve_repair` before creating its linked worktree, and otherwise follows the same builder/agent/process/budget/release path. It consumes a repair reservation, not a new implemented-candidate reservation, and fixes `kind="repair-experiment"`; caller-provided parent objects or relabeled mechanisms are rejected.

- [ ] **Step 4: Run experiment tests**

Run: `python3 -m pytest -q tests/selfloop/test_experiment_execution.py`

Expected: all experiment-execution tests pass and pytest exits `0`.

- [ ] **Step 5: Commit minimum C2 experiment execution**

```bash
git add references/selfloop/policies/diagnose-probes-v1.json scripts/selfloop_supervisor/experiment_receipts.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/process_registry.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/builder_broker.py scripts/selfloop_supervisor/candidate_policy.py scripts/selfloop_supervisor/foundation_checks.py scripts/selfloop_supervisor/experiments.py scripts/selfloop_strategy/experiment_builder.py scripts/selfloop_strategy/worker.py tests/selfloop/test_experiment_execution.py
git commit -m "feat(selfloop): execute proof-bearing C2 experiments"
```

### Task 3: Record sequential commits and exact-diff independent review

**Files:**
- Modify: `scripts/selfloop_supervisor/candidate_policy.py`
- Modify: `scripts/selfloop_supervisor/experiments.py`
- Modify: `scripts/selfloop_supervisor/experiment_receipts.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/process_registry.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Create: `scripts/selfloop_supervisor/review.py`
- Test: `tests/selfloop/test_experiment_review.py`

**Interfaces:**
- Produces: `commit_step(workspace: CandidateWorkspace, remaining_hypothesis: str, capability: MutationCapability) -> StepReceipt`, protected `ReviewBroker.launch_spec(workspace, diff_hash, grant) -> ProcessLaunchSpec`, `collect(process_event_digest, grant) -> RawReviewCallReceipt`, `ReviewRegistry.verify(receipt, current_diff_hash, builder_id, review_grant, agent_reservation) -> bool`, and `accept(receipt, current_diff_hash, builder_id, review_grant, budget_receipt, agent_release_receipt, capability) -> FinalReviewAcceptanceReceipt`.
- The controller reserves review/agent IDs first, acquires the agent reservation and review grant, launches the reviewer through P05 `ProcessRegistry`, persists the raw review receipt, reconciles budget, releases the agent reservation, then invokes `accept` with a `REVIEW_ACCEPT` capability. `accept` appends the exact final review proof; naked idempotency strings are rejected.
- This task modifies the Task 2 receipt module; it must not recreate it. Raw candidate/repair receipts gain optional-by-variant review event fields through separate reviewed/unreviewed dataclasses, not nullable fields on one broad schema.
- Protected supervisor, sealed tests/policies, ledger migration, and credential paths are never candidate-editable and cannot be authorized by review. Reviewable architecture/permissions/persistence/promotion/evaluation/selfloop paths require an independent reviewer whose identity differs from the builder, a separate protected review grant, and an exact current-diff hash.

- [ ] **Step 1: Write failing buildable-step and stale-review tests**

```python
def test_architecture_candidate_requires_review_for_current_diff(experiment, reviewer):
    experiment.write("scripts/goal_state.py", "first reviewed change\n")
    step = experiment.commit_step(
        "Move persistence adapter behind ledger", worktree_capability("commit-step", experiment.candidate_id),
    )
    stale = reviewer.review(step.diff_hash, builder_id=experiment.builder_id, grant=review_grant())
    experiment.write("scripts/goal_state.py", "changed after review\n")
    current = experiment.current_diff_hash()
    with pytest.raises(ReviewRequired, match=current):
        experiment.accept_review(stale, review_accept_capability(experiment.candidate_id))

def test_protected_supervisor_change_is_rejected_even_with_review(experiment, reviewer):
    experiment.write("scripts/selfloop_supervisor/kernel.py", "candidate mutation\n")
    with pytest.raises(CandidatePolicyDenied, match="protected path"):
        experiment.commit_step(
            "Attempt protected mutation", worktree_capability("commit-step", experiment.candidate_id),
        )

def test_reviewer_must_differ_and_use_separate_grant(experiment, reviewer):
    experiment.write("scripts/goal_state.py", "reviewable change\n")
    diff_hash = experiment.current_diff_hash()
    with pytest.raises(ReviewRequired, match="independent reviewer"):
        experiment.accept_review(
            reviewer.review(diff_hash, builder_id=reviewer.reviewer_id, grant=builder_grant()),
            review_accept_capability(experiment.candidate_id),
        )

def test_each_large_step_is_committed_and_verified(experiment):
    receipt = experiment.commit_step(
        "Test second storage adapter", worktree_capability("commit-step", experiment.candidate_id),
    )
    assert receipt.commit_sha and receipt.diff_hash
    assert receipt.changed_paths
    assert receipt.verification.status == "passed"

def test_ordinary_execution_records_separately_metered_review(executor, architecture_card):
    receipt = executor.execute(
        architecture_card, experiment_session("reviewed-ordinary-1"), "experiment-reviewed-1",
    )
    assert receipt.classification.review_required is True
    assert receipt.review.diff_hash == receipt.diff_hash
    assert receipt.review.reviewer_id != receipt.builder.builder_id
    assert receipt.review.grant_id not in {receipt.builder.grant_id, receipt.foundation.grant_id}
    assert receipt.review.grant_status == "reconciled"
    assert executor.ledger.event_by_digest(receipt.review.agent_reservation_event_digest).payload["reservationKind"] == "agent"
    assert executor.ledger.event_sequence("process.launch.intended", purpose="independent-review") < executor.ledger.event_sequence("review.raw-recorded")
```

- [ ] **Step 2: Run and verify review enforcement is absent**

Run: `python3 -m pytest -q tests/selfloop/test_experiment_review.py`

Expected: collection fails with missing `review`.

- [ ] **Step 3: Implement changed-path classification and diff-hash binding**

```python
PROTECTED_PREFIXES = (
    "scripts/selfloop_supervisor/", "tests/selfloop/sealed/", "references/selfloop/policies/",
    ".codex/credentials/", ".env",
)
REVIEW_PREFIXES = (
    "scripts/goal_state.py", "scripts/eval_", "scripts/harness_homebase_mcp.py",
    "scripts/autonomy_gate.py", ".mcp.json", ".codex-plugin/", "hooks/",
    "commands/selfloop.md", "skills/sips-selfloop/",
)

def classify_changed_paths(changed_paths):
    protected = tuple(path for path in changed_paths if path.startswith(PROTECTED_PREFIXES))
    if protected:
        raise CandidatePolicyDenied(f"protected path: {protected[0]}")
    return ChangeClassification(
        review_required=any(path.startswith(REVIEW_PREFIXES) for path in changed_paths),
        changed_paths=tuple(sorted(changed_paths)),
    )

def verify(self, receipt, current_diff_hash, builder_id, review_grant, agent_reservation):
    if (
        receipt.diff_hash != current_diff_hash
        or receipt.reviewer_id == builder_id
        or receipt.grant_id != review_grant.grant_id
        or review_grant.category != "subagent"
        or review_grant.purpose != "independent-review"
        or agent_reservation.reservation_kind != "agent"
        or agent_reservation.purpose != "independent-review"
        or receipt.agent_reservation_id != agent_reservation.reservation_id
    ):
        raise ReviewRequired(f"review required for diff {current_diff_hash}")
    return True

def accept(self, receipt, current_diff_hash, builder_id, grant, budget, agent_release, capability):
    capability.require(MutationOperation.REVIEW_ACCEPT, resource_id=current_diff_hash)
    agent_reservation = self.budget.require_reservation(agent_release.reservation_id)
    self.verify(receipt, current_diff_hash, builder_id, grant, agent_reservation)
    return self._append_final_acceptance(
        receipt, budget, agent_release, idempotency_key=capability.idempotency_key,
    )
```

After the exact commit/diff exists, `ExperimentExecutor` reserves review and agent IDs, acquires an `agent` reservation with purpose `independent-review`, and authorizes a fresh `subagent` grant. It obtains a review launch spec, calls `ProcessRegistry.launch`, persists the raw review call, reconciles its budget, releases the agent reservation, then calls `require_success` and capability-gated `accept`. `ReviewBroker` owns reviewer credentials and denies candidate writes but never spawns, writes the ledger, or reconciles. `accept` persists grant/budget/reservation event digests, policy digest, decision, exact diff/review artifact hashes, and process terminal event. Any subsequent byte change invalidates it. Failures append `review`/`terminal-failed` and are linked from the experiment failure receipt. A reviewer-supplied `independent` boolean is not proof.

- [ ] **Step 4: Run review tests**

Run: `python3 -m pytest -q tests/selfloop/test_experiment_review.py`

Expected: all review/classification tests pass and pytest exits `0`.

- [ ] **Step 5: Commit review and step receipts**

```bash
git add scripts/selfloop_supervisor/candidate_policy.py scripts/selfloop_supervisor/experiments.py scripts/selfloop_supervisor/experiment_receipts.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/process_registry.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/review.py tests/selfloop/test_experiment_review.py
git commit -m "feat(selfloop): bind experiment review to exact diffs"
```

### Task 4: Make research invocations terminal, resumable, and abortable

**Files:**
- Modify: `scripts/selfloop_supervisor/process_registry.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/experiment_receipts.py`
- Modify: `scripts/selfloop_supervisor/candidates.py`
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/opportunity_queue.py`
- Modify: `scripts/selfloop_supervisor/operator_contract.py`
- Modify: `scripts/selfloop_supervisor/selection_policy.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Test: `tests/selfloop/test_research_invocation.py`

**Interfaces:**
- Adds private `SelfloopController.advance(session: MutationSession) -> ControllerResponse`; only the shared typed `handle` obtains the root lock/session. Produces `ExperimentFinalizer.finalize(raw_experiment_event_digest: str, expected: InvocationIdentity, session: MutationSession, capability: MutationCapability) -> FinalDiagnoseExperimentReceipt | FinalCandidateExperimentReceipt | FinalRepairExperimentReceipt` and `ExperimentReceiptValidator.require_c2_terminal(final_experiment_event_digest: str, expected: InvocationIdentity) -> VerifiedTerminalExperiment`.
- The finalizer accepts only a persisted `experiment.raw-recorded` event digest. It dispatches its exact raw kind/stage, rehashes artifacts, verifies every grant/budget/reservation/process event, Git commit/diff, review, foundation/probe, and calls `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)` then compares `receipt_digest`. Raw objects, terminal-failed events, caller booleans, nullable supersets, and source paths are rejected.
- In one `BEGIN IMMEDIATE`, finalization appends protected lineage/operator/search updates, performs the normative queue transition (`selected -> implemented` for a committed candidate, `selected -> archived` for completed DIAGNOSE, or an explicitly evidenced `invalidated`; repairable failure remains `selected`), appends the kind-specific final receipt, and advances invocation state. Final receipts fix `stage="final"`, `terminal=true`, all source/raw/learning event digests, and the complete section-20 terminal key set. Candidate and repair variants carry candidate/champion release IDs plus source-attestation and release-bundle receipt digests. DIAGNOSE keeps candidate commit/release/reviewer/gate/baseline keys present with explicit nulls or empty changed paths plus exact protected `diagnose_non_mutating`, `review_not_required`, `gate_not_reached`, and `baseline_not_established` reasons.
- `ProcessRegistry` remains the P05 durable launcher. P08 adds experiment/card/candidate/review metadata to `ProcessLaunchSpec` and archive queries; it does not expose `register(Popen)`. Resume reconciles intended handshakes/process terminals before inspecting raw/final receipts.
- Proposal-only, pre-experiment, recovery, or administrative failure appends `FailedResearchInvocationReceipt(kind="research-invocation", stage="terminal-failed")`. Once an experiment kind is known, failure uses that kind's terminal-failed class. Every controller return is therefore backed by a final or terminal-failed ledger event.

- [ ] **Step 1: Write failing proposal-only, restart, idempotency, and abort tests**

```python
def test_proposal_only_invocation_fails(controller):
    controller.strategy.stop_after = "idea-pack"
    response = controller.handle(v2_request("advance", "advance-1"))
    assert response.status == "failed"
    assert response.receipt.kind == "research-invocation"
    assert response.receipt.stage == "terminal-failed"
    assert response.receipt.error.code == "terminal-experiment-required"

def test_raw_experiment_cannot_satisfy_final_validator(controller, raw_candidate_event):
    with pytest.raises(InvalidExperimentReceipt, match="final experiment event required"):
        controller.receipt_validator.require_c2_terminal(raw_candidate_event.digest, invocation_identity())
    with pytest.raises(InvalidExperimentReceipt, match="persisted event digest required"):
        session = experiment_session("raw-object")
        controller.finalizer.finalize(
            raw_candidate_event.payload, invocation_identity(), session,
            session.issue(MutationOperation.EXPERIMENT_FINALIZE, "experiment-raw", "finalize-raw-object"),
        )

def test_diagnose_terminal_has_all_mandated_keys_with_validated_not_applicable_reasons(controller):
    receipt = controller.handle(v2_request("advance", "diagnose-terminal-1")).receipt
    assert receipt.kind == "diagnose-experiment" and receipt.stage == "final"
    assert receipt.candidate_commit is None and receipt.release_id is None
    assert receipt.changed_paths == () and receipt.reviewer_receipt is None
    assert receipt.gate_results is None and receipt.paired_baseline_identity is None
    assert receipt.not_applicable_reasons == {
        "candidate_commit": "diagnose_non_mutating", "release_id": "diagnose_non_mutating",
        "changed_paths": "diagnose_non_mutating", "reviewer_receipt": "review_not_required",
        "gate_results": "gate_not_reached", "paired_baseline_identity": "baseline_not_established",
    }
    assert receipt.resource_usage and receipt.outcome and receipt.archive_path
    assert receipt.search_statistic_updates

def test_restart_resumes_same_experiment_once(controller_factory):
    first = controller_factory(crash_after="candidate-commit")
    with pytest.raises(SimulatedCrash):
        first.handle(v2_request("advance", "advance-2"))
    reserved = first.ledger.reserved_ids("advance-2")
    resumed = controller_factory().handle(v2_request("resume", "advance-2"))
    assert resumed.receipt.terminal is True and resumed.receipt.stage == "final"
    assert resumed.receipt.experiment_id == reserved["experiment"]
    assert resumed.receipt.candidate_id == reserved["candidate"]
    assert controller_factory().ledger.count("experiment.started") == 1
    assert controller_factory().ledger.count("experiment.raw-recorded") == 1
    assert controller_factory().ledger.count("experiment.finalized") == 1

def test_abort_terminates_child_and_preserves_card_and_events(controller, long_running_builder):
    experiment_id = controller.start_for_test(long_running_builder)
    response = controller.handle(v2_request("abort", "abort-1"))
    assert response.status == "aborted"
    assert controller.processes.is_running(experiment_id) is False
    assert controller.opportunities.get(long_running_builder.card_id).status is QueueStatus.SELECTED
    assert controller.ledger.count("campaign.aborted") == 1

def test_final_commit_updates_normative_queue_learning_budget_and_release_once(controller):
    response = controller.handle(v2_request("advance", "advance-learning-1"))
    receipt = response.receipt
    assert receipt.queue_transition.status in {QueueStatus.IMPLEMENTED, QueueStatus.ARCHIVED, QueueStatus.INVALIDATED}
    assert receipt.outcome in {"supported", "falsified", "inconclusive", "passed", "failed"}
    assert receipt.lineage_update_digest and receipt.operator_update_digest
    assert receipt.search_statistics_digest and receipt.budget_event_digests
    assert receipt.candidate_source_attestation_digest and receipt.candidate_release_bundle_receipt_digest
    reopened = controller.release_bundles.open_verified(
        receipt.candidate_release_id, receipt.candidate_source_attestation_digest,
    )
    assert reopened.receipt_digest == receipt.candidate_release_bundle_receipt_digest
    replay = controller.handle(v2_request("resume", "advance-learning-1"))
    assert replay.receipt == receipt
    assert controller.ledger.count("experiment.finalized") == 1

def test_crash_during_abort_resumes_archival_and_releases_every_reservation(
    controller_factory, long_running_builder,
):
    first = controller_factory(crash_after="abort-terminate")
    experiment_id = first.start_for_test(long_running_builder)
    with pytest.raises(SimulatedCrash):
        first.handle(v2_request("abort", "abort-crash-1"))
    resumed = controller_factory().handle(v2_request("abort", "abort-crash-1"))
    assert resumed.receipt.process_termination.experiment_id == experiment_id
    assert resumed.receipt.archived_stdout_digest and resumed.receipt.archived_stderr_digest
    assert resumed.receipt.last_commit is not None and resumed.receipt.incomplete_gates
    assert resumed.receipt.released_reservation_kinds >= {"agent", "builder", "candidate"}
    assert controller_factory().ledger.ordered_types("abort-crash-1")[-3:] == [
        "campaign.aborted", "worktree.removed", "root.lock.released",
    ]
    assert controller_factory().ledger.count("abort.intent") == 1
    assert controller_factory().ledger.count("campaign.aborted") == 1
```

- [ ] **Step 2: Run and confirm invocation semantics are red**

Run: `python3 -m pytest -q tests/selfloop/test_research_invocation.py`

Expected: fails because the protected finalizer and final-event validator are undefined; the existing controller cannot turn a persisted raw event into a terminal C2 event.

- [ ] **Step 3: Implement journaled phase recovery and evidence-preserving abort**

```python
def advance(self, session):
    run = self.recovery.load_or_start_invocation(session)
    try:
        self.prepare_generation(session)
        selection = self.select_next(session)
        if selection.stage == "terminal-failed":
            return self.failed_response(selection)
        experiment_id = self.phases.reserve_id(session, "experiment-id", "experiment")
        raw = self.experiments.execute(selection.card, session, experiment_id)
        if raw.stage == "terminal-failed":
            return self.failed_response(raw)
        final = self.finalizer.finalize(
            raw.event_digest, run.identity, session,
            session.issue(MutationOperation.EXPERIMENT_FINALIZE, experiment_id, "finalize-experiment"),
        )
        verified = self.receipt_validator.require_c2_terminal(final.event_digest, run.identity)
        return self.success_response(
            run, verified, conformance=self.conformance.current_for_event(final.event_digest),
        )
    except BaseException as error:
        failed = self.invocation_receipts.commit_failed_from_journal(
            session, run, error,
            session.issue(MutationOperation.RECEIPT_PERSIST, run.identity.invocation_id, "persist-invocation-failed"),
        )
        return self.failed_response(failed)

def abort(self, session):
    experiment_id = self.state.load(session.root_id).active_experiment_id
    self.recovery.run_phase(
        session, "abort:mark", session.issue(MutationOperation.ABORT_PHASE, experiment_id, "abort:mark"),
        lambda: self.state.mark_aborting(session.scope),
    )
    bind_capability = session.issue(
        MutationOperation.PROCESS_RECONCILE, experiment_id, "abort:bind-launches",
    )
    self.recovery.run_phase(
        session, "abort:bind-launches", bind_capability,
        lambda: self.processes.reconcile_experiment_launches(experiment_id, bind_capability),
    )
    terminate_capability = session.issue(
        MutationOperation.PROCESS_TERMINATE, experiment_id, "abort:terminate",
    )
    termination = self.recovery.run_phase(
        session, "abort:terminate", terminate_capability,
        lambda: self.processes.terminate_experiment(experiment_id, terminate_capability),
    )
    archive_capability = session.issue(
        MutationOperation.ARTIFACT_PERSIST, experiment_id, "abort:archive",
    )
    archive = self.recovery.run_phase(
        session, "abort:archive", archive_capability,
        lambda: self.processes.archive_experiment(experiment_id, archive_capability),
    )
    terminal = self.recovery.run_phase(
        session, "abort:terminal",
        session.issue(MutationOperation.RECEIPT_PERSIST, experiment_id, "abort:terminal"),
        lambda: self.experiment_receipts.commit_aborted(session, experiment_id, termination, archive),
    )
    self.recovery.run_phase(
        session, "abort:resources",
        session.issue(MutationOperation.BUDGET_RELEASE, experiment_id, "abort:resources"),
        lambda: self.resources.reconcile_all(session, experiment_id, conservative=True),
    )
    workspace = self.candidates.for_experiment(experiment_id)
    if workspace is not None and workspace.disposable:
        remove_capability = session.issue(
            MutationOperation.WORKTREE_REMOVE, workspace.candidate_id, "abort:remove-worktree",
        )
        self.recovery.run_phase(
            session, "abort:remove-worktree", remove_capability,
            lambda: self.candidates.remove(workspace.candidate_id, remove_capability),
        )
    self.recovery.run_phase(
        session, "abort:unlock",
        session.issue(MutationOperation.ROOT_UNLOCK, session.root_id, "abort:unlock"),
        lambda: self.locks.release(session.lock_receipt),
    )
    return self.aborted_response(terminal)
```

`ExperimentFinalizer.finalize` resolves the raw event, exact card/selection and champion events, candidate/champion `release_id + source_attestation_digest + receipt_digest`, raw artifacts, Git commit/diff, process/grant/budget/reservation/review/foundation events, and current queue row. It requires an exact `EXPERIMENT_FINALIZE` capability for the reserved experiment ID and constructs the correct final class from protected evidence only. `FinalizationRepository.commit` writes queue/learning/search updates and `experiment.finalized` in one SQLite transaction; it refuses zero/multiple raw events or any later invalidation. Every kind-specific terminal class has the same mandated terminal key set; DIAGNOSE and pre-gate failures use explicit nulls plus exact field-specific protected reasons, never omitted fields or optional supersets.

`RecoveryManager.run_phase` journals each capability-derived phase before the effect and persists the raw receipt afterward. Resume first binds any spawn handshakes, reopens every candidate/champion release with `open_verified(release_id, source_attestation_digest)`, compares path-independent receipt digests, and then reuses completed phases. Abort preserves the selected card and all prior evidence, appends the aborted/terminal-failed experiment receipt before cleanup, reconciles process/grant/builder/agent/candidate/repair receipts, removes only the recorded disposable worktree, and releases the root lock last. A crash at any abort phase re-enters that phase; it never unlocks with an unbound child or unreconciled reservation.

- [ ] **Step 4: Run invocation and adjacent recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_research_invocation.py tests/selfloop/test_recovery.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit invocation recovery**

```bash
git add scripts/selfloop_supervisor/process_registry.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/experiment_receipts.py scripts/selfloop_supervisor/candidates.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/opportunity_queue.py scripts/selfloop_supervisor/operator_contract.py scripts/selfloop_supervisor/selection_policy.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/recovery.py tests/selfloop/test_research_invocation.py
git commit -m "feat(selfloop): require terminal experiments per invocation"
```

### Task 5: Wire CLI and MCP to the completed C2 controller

**Files:**
- Modify: `scripts/selfloop_supervisor/controller_requests.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Create: `scripts/selfloop_supervisor/conformance.py`
- Modify: `commands/selfloop.md`
- Modify: `skills/sips-selfloop/SKILL.md`
- Test: `tests/selfloop/test_adapter_c2.py`
- Test: `tests/selfloop/test_c2_conformance.py`

**Interfaces:**
- CLI mutating actions are `start|advance|pause|resume|abort|stop|complete|clear|record|rollback --root PATH --idempotency-key KEY --json`; read-only `status --root PATH --json` omits and rejects `--idempotency-key`. CLI also exposes P05's TTY-only supervisor-upgrade administration without adding it to MCP.
- MCP v2 imports the same `ControllerAction` enum and exposes `start`, bare `advance`, `status`, `pause`, `resume`, `abort`, `stop`, `complete`, `clear`, `record`, and schema-valid unavailable `rollback`; v1 remains byte-compatible. MCP `status` rejects `idempotency_key`; every mutating action requires it. Both adapters call `ControllerRequest.parse_v2` and have no independent action/payload table.
- At C2, v2 `abort`, `stop`, and `clear` enter the same evidence-preserving, unlock-last abort implementation and return preserved campaign/experiment/receipt IDs. `record` requires exactly `root`, `experiment_id`, `terminal_experiment_event_digest`, and idempotency key and derives outcome/summary. `rollback` returns `action_unavailable_until_C4`; P00 v1 semantics remain frozen.
- Produces `C2ConformanceService.issue_from_ledger(scope: ObjectScope, final_experiment_event_digest: str, acceptance_intent_id: str) -> C2ConformanceReceipt`, `ConformanceRegistry.current_for_scope(scope, loaded_runtime: SupervisorBundleReceipt) -> C2ConformanceReceipt | None`, and `run_c2_acceptance(temp_root: Path) -> C2ConformanceReceipt`.
- `issue_from_ledger` accepts no receipt object, booleans, artifact paths, or source identity. It resolves the exact final event and all raw/learning/budget/reservation/process/sandbox events, opens candidate and champion with `open_verified(release_id, source_attestation_digest)`, compares their path-independent `receipt_digest` values, verifies active supervisor bundle/policies/spec, and appends `conformance.c2.passed` in one `BEGIN IMMEDIATE`. The returned receipt is constructed only from that event.
- `run_c2_acceptance` creates a committed temporary Git root and temporary `SIPS_HOME`, activates the P08 fixture bundle through the prior-runtime protocol, and drives the real typed controller through campaign start, preparation/selection, one registered/sandboxed experiment, protected finalization, and ledger-derived C2 issuance under one phase-journaled acceptance intent. External phases are not held inside a long SQLite transaction; each is intent/receipt journaled, and final experiment/learning plus conformance issuance use their declared atomic transactions. It never reads or mutates live state.

- [ ] **Step 1: Write failing CLI/MCP parity and free-text record rejection tests**

```python
def test_cli_and_mcp_return_equivalent_terminal_experiment(tmp_sips_home, repo_root):
    cli = run_cli("advance", "--root", str(repo_root), "--idempotency-key", "adapter-1", "--json")
    mcp = call_mcp("homebase_selfloop", {"version": "v2", "action": "advance", "root": str(repo_root), "idempotency_key": "adapter-1"})
    assert cli["schema"] == mcp["schema"] == "homebase.selfloop.v2"
    assert cli["receipt"]["experimentId"] == mcp["receipt"]["experimentId"]
    assert cli["receipt"]["terminal"] is True

def test_status_omits_idempotency_and_mutations_require_it(repo_root):
    cli = run_cli("status", "--root", str(repo_root), "--json")
    mcp = call_mcp("homebase_selfloop", {"version": "v2", "action": "status", "root": str(repo_root)})
    assert cli["status"] == mcp["status"]
    assert run_cli(
        "status", "--root", str(repo_root), "--idempotency-key", "not-allowed", "--json",
    )["error"]["code"] == "request_schema_error"
    assert call_mcp("homebase_selfloop", {
        "version": "v2", "action": "status", "root": str(repo_root), "idempotency_key": "not-allowed",
    })["receipt"]["error"]["code"] == "request_schema_error"
    assert call_mcp("homebase_selfloop", {
        "version": "v2", "action": "pause", "root": str(repo_root),
    })["receipt"]["error"]["code"] == "request_schema_error"

def test_cli_and_mcp_share_action_enum_including_stop_complete_and_clear():
    expected = {"start", "advance", "status", "pause", "resume", "abort", "stop", "complete", "clear", "record", "rollback"}
    assert cli_v2_action_values() == mcp_v2_action_values() == expected

def test_v2_record_rejects_free_text_and_requires_exact_terminal_reference(repo_root):
    response = call_mcp("homebase_selfloop", {
        "version": "v2", "action": "record", "root": str(repo_root),
        "idempotency_key": "record-free-text", "summary": "looks improved",
    })
    assert response["status"] == "failed"
    assert response["receipt"]["error"]["code"] == "request_schema_error"

    recorded = call_mcp("homebase_selfloop", {
        "version": "v2", "action": "record", "root": str(repo_root),
        "idempotency_key": "record-terminal", "experiment_id": "experiment-1",
        "terminal_experiment_event_digest": terminal_experiment_event(repo_root).digest,
    })
    assert recorded["receipt"]["outcome"] == terminal_experiment_event(repo_root).payload["outcome"]

@pytest.mark.parametrize("action", ["abort", "stop", "clear"])
def test_c2_stop_aliases_preserve_evidence(action, repo_root):
    cleared = call_mcp("homebase_selfloop", {
        "version": "v2", "action": action, "root": str(repo_root), "idempotency_key": f"{action}-1",
    })
    assert cleared["status"] == "aborted" and cleared["receipt"]["evidencePreserved"] is True

def test_rollback_is_not_yet_claimed(repo_root):
    rollback = call_mcp("homebase_selfloop", {"version": "v2", "action": "rollback", "root": str(repo_root), "idempotency_key": "rollback-1"})
    assert rollback["status"] == "failed"
    assert rollback["receipt"]["error"] == "action_unavailable_until_C4"

def test_v1_adapter_bytes_remain_equal_to_frozen_p00_fixture(repo_root):
    assert call_mcp_raw("homebase_selfloop", frozen_v1_request(repo_root)) == frozen_v1_response_bytes(repo_root)

def test_c2_is_not_advertised_without_current_executable_acceptance_receipt(adapter, loaded_runtime):
    assert adapter.status(loaded_runtime=loaded_runtime)["conformance"] == "C1"
    receipt = run_c2_acceptance(adapter.temp_root)
    assert adapter.status(loaded_runtime=loaded_runtime)["conformance"] == "C2"
    assert receipt.event_digest and receipt.final_experiment_event_digest
    assert receipt.sandbox_receipt_digest and receipt.active_supervisor_bundle_digest
    assert receipt.candidate_source_attestation_digest and receipt.candidate_release_bundle_receipt_digest
    assert receipt.champion_source_attestation_digest and receipt.champion_release_bundle_receipt_digest
    assert adapter.ledger.count("conformance.c2.passed") == 1

def test_c2_issue_rejects_raw_event_and_arbitrary_receipt(conformance_service, raw_candidate_event):
    with pytest.raises(ConformanceDenied, match="final experiment event required"):
        conformance_service.issue_from_ledger(scope(), raw_candidate_event.digest, "acceptance-raw")
    with pytest.raises(TypeError, match="event digest"):
        conformance_service.issue_from_ledger(scope(), fake_c2_receipt(), "acceptance-fake")
```

- [ ] **Step 2: Run and verify adapter parity is red**

Run: `python3 -m pytest -q tests/selfloop/test_adapter_c2.py tests/selfloop/test_c2_conformance.py`

Expected: tests fail because adapters do not share the typed parser and C2 conformance still accepts constructed receipts/source presence instead of ledger-derived final events.

- [ ] **Step 3: Make every adapter construct the same `ControllerRequest`**

```python
request = ControllerRequest.parse_v2(arguments)
response = controller.handle(request)
return tool_result(response.to_dict(), render(response.to_dict(), "SIPS Selfloop"), is_error=response.status == "failed")

def issue_from_ledger(self, scope, final_experiment_event_digest, acceptance_intent_id):
    final = self.experiment_validator.require_c2_terminal(final_experiment_event_digest, scope.invocation_identity)
    candidate = self.release_bundles.open_verified(
        final.candidate_release_id, final.candidate_source_attestation_digest,
    )
    champion = self.release_bundles.open_verified(
        final.champion_release_id, final.champion_source_attestation_digest,
    )
    if candidate.receipt_digest != final.candidate_release_bundle_receipt_digest:
        raise ConformanceDenied("candidate release-bundle receipt digest mismatch")
    if champion.receipt_digest != final.champion_release_bundle_receipt_digest:
        raise ConformanceDenied("champion release-bundle receipt digest mismatch")
    payload = self.evidence.resolve_c2_payload(
        scope, final.event_digest, candidate, champion, self.runtime.load_active(scope.root_id),
    )
    with self.ledger.immediate_transaction() as transaction:
        event = transaction.append(
            scope.root_id, scope.campaign_id, "conformance.c2.passed", payload,
            f"{acceptance_intent_id}:conformance-c2",
        )
    return C2ConformanceReceipt.from_event(event)
```

The CLI normalizes flag names to the same wire keys used by MCP, then calls `parse_v2`; neither adapter catches missing fields by filling empty strings. The controller's injected channel policy permits the upgrade-authorization action only from its pinned CLI/TTY dependency and rejects it in MCP. Status performs only ledger/runtime verification and never acquires a mutation session.

`run_c2_acceptance` uses one deterministic acceptance ID and phase journal. It initializes a real committed fixture repo, bootstrap ledger, active P08 bundle, budget profile, fixed DIAGNOSE fixture card, real restricted launcher, and sandbox backend. It calls `controller.handle(start_request)`, then `controller.handle(advance_request)`, verifies the returned event is final rather than raw/failed, and calls `issue_from_ledger`. A crash resumes from phase receipts without a second experiment or conformance event. The acceptance receipt records fixture repo commit, temporary `SIPS_HOME`, candidate/champion release/source-attestation/release-bundle receipt digests, active supervisor digest/path proof, policy/spec digests, sandbox receipt, ledger head, final experiment event, and zero live paths.

- [ ] **Step 4: Run the C2 acceptance slice and full selfloop tests**

Run: `python3 -m pytest -q tests/selfloop/test_candidates.py tests/selfloop/test_experiment_execution.py tests/selfloop/test_experiment_review.py tests/selfloop/test_research_invocation.py tests/selfloop/test_adapter_c2.py tests/selfloop/test_c2_conformance.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit C2 adapter parity**

```bash
git add scripts/selfloop_supervisor/controller_requests.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py scripts/selfloop_supervisor/conformance.py commands/selfloop.md skills/sips-selfloop/SKILL.md tests/selfloop/test_adapter_c2.py tests/selfloop/test_c2_conformance.py
git commit -m "feat(selfloop): expose terminal C2 experiments"
```

### Task 6: Roll and prove the P08 protected C2 bundle through the active P07 controller

**Files:**
- Modify: `scripts/selfloop_supervisor/runtime_registry.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Test: `tests/selfloop/test_p08_supervisor_rollover.py`

**Interfaces:**
- Consumes the active P07 runtime, P02 `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, P05 `SupervisorUpgradeAuthorizationReceipt`/`PendingSupervisorUpgrade`, session-bound stage/activate, and P08 host/conformance probes.
- Produces an active P08 `SupervisorBundleReceipt`, activation receipt, and host-load proof for exact resolved bundle bytes, including bundle/manifest digests and source release/source-attestation/path-independent release-bundle receipt digests. The bundled CLI and external MCP adapter must both dispatch to the same active `bundle_digest`; CLI/MCP source paths are recorded separately and cannot substitute for the loaded-runtime proof.
- C2 conformance remains unavailable until activation, host proof, and executable `run_c2_acceptance` all refer to the same P08 bundle digest, manifest digest, source release ID, source-attestation digest, and release-bundle receipt digest. Failure restores P07 and keeps conformance at C1.

- [ ] **Step 1: Write failing P07-authority, exact-runtime, adapter-routing, replay, and rollback tests**

```python
def test_active_p07_authorizes_and_activates_exact_p08_runtime(p07_controller, p08_release_bundle):
    prior = p07_controller.runtime.load_active("root-1")
    p07_controller.tty.confirm_commit(p08_release_bundle.release_identity.commit_sha)
    authorization = p07_controller.handle(authorize_upgrade_request(
        source_commit=p08_release_bundle.release_identity.commit_sha,
        release_id=p08_release_bundle.release_identity.release_id,
        source_attestation_digest=p08_release_bundle.source_attestation_digest,
        idempotency_key="authorize-p08",
    )).receipt
    assert authorization.release_bundle_receipt_digest == p08_release_bundle.receipt_digest
    pending = p07_controller.handle(prepare_upgrade_request(
        authorization_receipt_digest=authorization.event_digest,
        expected_prior_digest=prior.bundle_digest, idempotency_key="prepare-p08",
    )).receipt
    activate = activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p08",
    )
    first = p07_controller.handle(activate).receipt
    assert p07_controller.handle(activate).receipt == first
    active = p07_controller.runtime.load_active("root-1")
    assert active.bundle_digest == first.active_bundle_digest
    assert active.path == p07_controller.runtime.bundles_root / active.bundle_digest
    assert active.path.joinpath("scripts/selfloop_supervisor/experiment_receipts.py").is_file()
    assert active.path.joinpath("scripts/selfloop_supervisor/conformance.py").is_file()
    assert bundled_cli_status(active.path)["supervisorBundleDigest"] == active.bundle_digest
    assert mcp_status()["supervisorBundleDigest"] == active.bundle_digest

def test_failed_p08_host_or_acceptance_proof_restores_p07_and_never_claims_c2(
    p07_controller, p08_release_bundle,
):
    prior = p07_controller.runtime.load_active("root-1")
    pending = authorized_pending_upgrade(p07_controller, p08_release_bundle, prior, "p08-failed")
    p07_controller.host_probe.fail_with("MCP dispatched to mutable source runtime")
    failed = p07_controller.handle(activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p08-failed",
    ))
    assert failed.status == "failed" and failed.receipt.stage == "terminal-failed"
    assert p07_controller.runtime.load_active("root-1").bundle_digest == prior.bundle_digest
    assert mcp_status()["conformance"] == "C1"
```

- [ ] **Step 2: Run and confirm the P08 rollover proof is red**

Run: `python3 -m pytest -q tests/selfloop/test_p08_supervisor_rollover.py`

Expected: tests fail because the active P07 bundle lacks P08 experiment/finalizer/conformance modules and adapters cannot prove dispatch through an active P08 digest.

- [ ] **Step 3: Implement the three-phase rollover and bind C2 to loaded P08 bytes**

The active P07 controller performs direct-TTY authorization and records commit, release, manifest, source-attestation, path-independent release-bundle receipt, and current P07 digest. Preparation resolves that authorization, calls `open_verified(release_id, source_attestation_digest)`, checks `receipt_digest`, stages with `SUPERVISOR_STAGE`, rehashes the resolved bundle, and persists `PendingSupervisorUpgrade`. Activation resolves the pending ID inside `handle`, consumes `SUPERVISOR_ACTIVATE`, and retains P07 as rescue.

The host probe launches the bundled CLI from the resolved P08 directory and calls MCP status through its normal adapter, requiring both receipts to name the same active digest/path and loaded supervisor module root. It imports `experiment_receipts`, `experiments`, `review`, `recovery`, and `conformance` from that root. Persist the raw proof. Any digest/path/module/adapter mismatch or executable C2 acceptance failure appends a terminal-failed activation receipt, compensates to P07, and invalidates/downgrades C2. Success appends `supervisor.host-load.proved`; replay performs no restage.

- [ ] **Step 4: Run rollover, executable C2 acceptance, and adapter parity**

Run: `python3 -m pytest -q tests/selfloop/test_p08_supervisor_rollover.py tests/selfloop/test_research_invocation.py tests/selfloop/test_adapter_c2.py tests/selfloop/test_c2_conformance.py`

Expected: all tests pass and pytest exits `0`; the executable acceptance receipt and both adapters name the active P08 digest.

- [ ] **Step 5: Commit the P08 protected-bundle rollover**

```bash
git add scripts/selfloop_supervisor/runtime_registry.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py tests/selfloop/test_p08_supervisor_rollover.py
git commit -m "feat(selfloop): activate protected P08 C2 runtime"
```

## Plan Verification

- [ ] Run `python3 -m pytest -q tests/selfloop`; expected: all selfloop tests pass.
- [ ] Run `python3 -m pytest -q tests/selfloop/test_p08_supervisor_rollover.py`; expected: active P08 bundle/host/adapter proofs pass, P07 remains verified rescue, replay is idempotent, and injected mismatch restores P07 without C2.
- [ ] Run `python3 -c 'from pathlib import Path; from scripts.selfloop_supervisor.conformance import run_c2_acceptance; print(run_c2_acceptance(Path("/tmp/selfloop-c2-acceptance")).to_json())'` with a fresh temporary fixture root; expected: a persisted `C2` receipt bound to the loaded release/policy digests, real sandbox receipt, complete terminal experiment digest, learning-transition digests, and zero live-state mutations.
- [ ] Run `python3 scripts/selfloop_cli.py advance --root . --idempotency-key c2-smoke --json` against that disposable committed fixture repository and temporary `SIPS_HOME`; expected: `homebase.selfloop.v2`, `conformance: C2`, one complete terminal experiment receipt, and either a fixed probe receipt or candidate commit plus passed C1 foundation receipt. Running the same source without the current acceptance receipt reports at most C1.
- [ ] Run `python3 scripts/selfloop_cli.py status --root . --json`; expected: source, candidate root, release, budget, card, lineage, mechanism, experiment, receipt path/hash, and blocker proof boundaries are explicit.
- [ ] Run `python3 scripts/validate_v2.py --check-eval && python3 scripts/run_tests.py homebase_mcp --verbose && git diff --check`; expected: every command exits `0`, custom tests report zero failures, and diff check emits no output.
- [ ] Verify no test mutated the primary checkout, live `${SIPS_HOME}`, installed plugin cache, host config, or external system.
