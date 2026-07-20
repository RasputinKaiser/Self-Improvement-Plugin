# Selfloop G5 Probation, Shadowing, and Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete C4 from the persisted Plan 11 trial-control handoff by consuming P10's probation policy pin, journaling every real-task route/outcome and shadow comparison, persisting a protected G5 decision, promoting from canonical state, and retaining verifiable rollback/rescue history.

**Architecture:** P10's one `campaign.policy.pinned` event immutably fixes both G4 and probation policy files before G0; P12 resolves and extends that exact authority rather than creating another policy event. Its probation digest is carried through G4, promotion authorization, probation start, routing, evidence, and G5. Probation starts only by resolving Plan 11's persisted `trial_control.ready` receipt against current canonical state. Protected routing/outcome repositories hash complete receipt bodies and append them to the anchored ledger. A protected evidence builder folds those events and real P03 shadow receipts; a typed G5 store persists open/pass/rolled-back decisions. Stable promotion and C4 conformance resolve their inputs from canonical history, never caller state or status booleans.

**Tech Stack:** Python 3.10+, standard-library dataclasses/datetime/hashlib/hmac/json/math/statistics, P03 restricted launcher, P05 anchored ledger/state, P10 paired statistics, P11 promotion/trial-control interfaces, pytest 8+.

## Global Constraints

- Contract: `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- Probation policy, start, routing, outcome recording, shadow selection, evidence, watchdog, G5, champion pointers, retention, rollback calls, and conformance execute from the pinned immutable supervisor bundle.
- After source tests pass, the active P11 controller must TTY-authorize, prepare, and activate the exact P12 release through the roadmap's protected rollover checkpoint. Probation routing, watchdog, and C4 adapter acceptance run only after a fresh loader proves the P12 modules; source presence is not probation authority.
- Every P12 mutation runs through `ProbationServices.for_session(session)`, constructed only by the P05 controller from a live ledger intent. The bound services privately issue a distinct operation/resource/phase `MutationCapability` for each route, outcome, shadow, evidence, watchdog, promotion, retention, rollback, and conformance effect. Their public-looking method signatures below never accept a serializable caller capability; unbound construction, closed-intent reuse, and cross-session recovery fail. Read-only `require`, `list`, `current`, and policy resolution remain capability-free.
- Probation cannot start from a receipt-shaped dictionary. `ProbationStartStore` must resolve the exact persisted Plan 11 trial-control digest, verify its P05 event/anchor, and require that its active trial tuple is current.
- P10's single `campaign.policy.pinned` event fixes the immutable probation policy file and inclusion rules before G0. Runtime code resolves that exact event/digest through `CampaignPolicyService`; P12 never appends `probation.policy.pinned`, recomputes thresholds from an unpinned object, or accepts a caller policy.
- The same pinned P10 probation document supplies the eligibility rule ID, family-coverage threshold `5`, shadow replay policy, critical-incident allowance `0`, resource-cap rule ID, required metric set, immediate rollback trigger set, complete-outcome/resource requirement, permission-profile matching requirement, unrelated-infrastructure exclusion rule, forbidden shadow effects, and protected-family allowance source; P10's campaign bundle supplies the canonical resource-cap policy digest. P12 carries every exact value and has no post-G4 defaults.
- Small/medium trials require at least `20` eligible completed tasks and `48` elapsed hours. Large/meta/architecture/permission/persistence trials require `50` tasks and `168` hours.
- At least `max(5, ceil(0.20 * all_probation_eligible_routes))` comparable shadows are required. Selection covers each task family with at least five eligible routes. Missing replay-safe rows keep G5 open; they never shrink the denominator.
- Every route, outcome, shadow selection, shadow result, evidence build, G5 decision, stable promotion, retention action, runtime probe, and C4 decision is a typed, canonical-hash, ledger-backed receipt. Digest-looking strings without matching verified events/artifacts are rejected.
- Routing eligibility is derived from current canonical probation state, the exact task permission manifest, pinned inclusion rules, and protected task metadata. Callers cannot submit eligibility, selected release/slot, family, or summary verdicts.
- Inconclusive/infrastructure-failed outcomes are preserved but do not count as completed tasks. The evidence builder derives correctness, critical failures, incident/resource deltas, and paired confidence intervals from raw receipts.
- Integrity failure, permission expansion, state corruption, critical regression, meter bypass, install hash failure, incompatible migration, watchdog failure, or rescue-canary failure invokes P11 rollback immediately and persists the rollback-linked terminal G5 receipt.
- Passing G5 alone does not mutate champion state. `StablePromotionManager` re-resolves a current passed G5 receipt and current canonical trial tuple, then atomically promotes the complete tuple and clears trial.
- A C4 claim exists only as a persisted, currently re-verifiable `conformance.c4.achieved` event. Source-file presence, constructed dataclasses, fake status values, literal hash strings, or skipped sandbox/runtime checks cannot produce C4.
- Unit tests may use deterministic supervisor-owned clocks/adapters. The C4 acceptance test uses a real temporary Git root, actual P02 bundles/snapshots, actual P05 SQLite/anchor, actual filesystem activation/rollback, actual task-local subprocess receipts, and the real supported P03 OS sandbox; it never mutates live SIPS state.

---

### Task 1: Resolve P10's campaign policy pin and consume trial control

**Files:**
- Create: `scripts/selfloop_supervisor/probation/session.py`
- Create: `scripts/selfloop_supervisor/probation/policy.py`
- Create: `scripts/selfloop_supervisor/probation/start.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/gates/acceptance_policy.py`
- Test: `tests/selfloop/test_probation_mutation_boundary.py`
- Test: `tests/selfloop/test_probation_policy_resolution.py`
- Test: `tests/selfloop/test_probation_start.py`
- Modify: `tests/selfloop/test_acceptance_policy.py`

**Interfaces:**
- Consumes: P05 `MutationSession`/controller service factory, P10 `CampaignPolicyService.resolve(GateScope) -> CampaignPolicyBundle`, `ProbationPolicyPin`, the one `campaign.policy.pinned` event, P11 `PromotionAuthorizationReceipt`/`TrialControlStore`, and the authorized P08 change class.
- Produces: `ProbationServices.for_session(session) -> ProbationServices`, `ResolvedProbationPolicy`, `ProbationPolicyLoader.for_promotion(root_id, promotion_id, authorization_receipt_digest)`, `ProbationStartReceipt`, and session-bound `ProbationStartStore.start(root_id, promotion_id, trial_control_receipt_digest, idempotency_key)`.
- `ProbationPolicyLoader` is a verified view over P10's event and pinned supervisor file. It writes no policy event and returns the same pin event/bundle/probation digests.

- [ ] **Step 1: Write failing single-authority and handoff tests**

```python
def test_probation_resolves_p10_single_campaign_policy_event(policy_campaign):
    bundle = policy_campaign.pin_before_g0()
    pinned = policy_campaign.service.load_probation_policy(bundle)
    policy = policy_campaign.probation_loader.for_promotion(
        "root-1", "promotion-7",
        policy_campaign.promotion_authorization.receipt_digest,
    )
    assert policy.minimum_tasks == 50 and policy.minimum_hours == 168
    assert policy.probation_policy_digest == bundle.probation_policy_digest
    assert policy.campaign_policy_pin_event_digest == bundle.pin_event_digest
    assert policy.family_coverage_threshold == 5
    assert policy.critical_incident_allowance == 0
    assert policy.eligibility_rule_id == pinned.eligibility_rule_id
    assert policy.shadow_replay_policy_id == pinned.shadow_replay_policy_id
    assert policy.resource_cap_rule_id == pinned.resource_cap_rule_id
    assert policy.resource_cap_policy_digest == bundle.resource_cap_policy_digest
    assert policy.required_metrics == pinned.required_metrics
    assert policy.immediate_rollback_triggers == pinned.immediate_rollback_triggers
    assert policy.require_complete_outcome_and_resource_receipt is True
    assert policy.require_permission_profile_match is True
    assert policy.exclude_unrelated_infrastructure_failure is True
    assert policy.forbidden_shadow_effects == pinned.forbidden_shadow_effects
    assert policy.protected_family_allowance_source == (
        pinned.protected_family_allowance_source
    )
    assert policy_campaign.ledger.count("campaign.policy.pinned") == 1
    assert policy_campaign.ledger.count("probation.policy.pinned") == 0
    with pytest.raises(TypeError):
        policy_campaign.probation_loader.for_promotion(
            "root-1", "promotion-7",
            policy_campaign.promotion_authorization.receipt_digest,
            change_class="small",
        )

def test_probation_start_resolves_persisted_trial_control(ready_trial_control):
    started = ready_trial_control.probation.start(
        "root-1", "promotion-7",
        ready_trial_control.receipt.receipt_digest, "probation-start-7",
    )
    assert started.trial_control_receipt_digest == ready_trial_control.receipt.receipt_digest
    assert started.active_trial_tuple == ready_trial_control.receipt.active_trial_tuple
    assert started.campaign_policy_pin_event_digest == (
        ready_trial_control.receipt.campaign_policy_pin_event_digest
    )
    assert started.policy_bundle_digest == ready_trial_control.receipt.policy_bundle_digest

def test_probation_start_rejects_unbacked_or_stale_trial_control(
    ready_trial_control
):
    ready_trial_control.change_active_pointer()
    with pytest.raises(ProbationStartError, match="current trial control"):
        ready_trial_control.probation.start(
            "root-1", "promotion-7", "sha256:" + "0" * 64,
            "probation-start-7",
        )

def test_unbound_or_closed_probation_service_cannot_mutate(
    probation_fixture, closed_mutation_session,
):
    with pytest.raises(MutationDenied, match="controller mutation session required"):
        ProbationStartStore(probation_fixture.ledger).start(
            "root-1", "promotion-7", probation_fixture.trial_control_digest,
            "probation:unbound",
        )
    services = ProbationServices.for_session(closed_mutation_session)
    with pytest.raises(MutationDenied, match="intent is not open"):
        services.starts.start(
            "root-1", "promotion-7", probation_fixture.trial_control_digest,
            "probation:closed",
        )
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_probation_policy_resolution.py tests/selfloop/test_probation_start.py tests/selfloop/test_probation_mutation_boundary.py tests/selfloop/test_acceptance_policy.py`

Expected: collection fails because the P10-backed probation loader and probation start store do not exist.

- [ ] **Step 3: Load the pinned P10 policy and verify the P11 handoff**

```python
@dataclass(frozen=True)
class ResolvedProbationPolicy:
    schema: str; policy_id: str; change_class: str
    minimum_tasks: int; minimum_hours: int
    shadow_fraction: float; minimum_shadows: int
    family_coverage_threshold: int
    quality_noninferiority: float; incident_delta_max: float
    eligibility_rule_id: str; shadow_replay_policy_id: str
    critical_incident_allowance: int
    resource_cap_rule_id: str; resource_cap_policy_digest: str
    required_metrics: tuple[str, ...]
    immediate_rollback_triggers: tuple[str, ...]
    require_complete_outcome_and_resource_receipt: bool
    require_permission_profile_match: bool
    exclude_unrelated_infrastructure_failure: bool
    forbidden_shadow_effects: tuple[str, ...]
    protected_family_allowance_source: str
    campaign_policy_pin_event_digest: str
    policy_bundle_digest: str; probation_policy_digest: str

class ProbationPolicyLoader:
    def for_promotion(
        self, root_id: str, promotion_id: str,
        authorization_receipt_digest: str,
    ) -> ResolvedProbationPolicy:
        authorization = self.promotions.require(
            root_id, promotion_id, authorization_receipt_digest
        )
        bundle = self.campaign_policies.resolve(authorization.gate_scope)
        pinned = self.campaign_policies.load_probation_policy(bundle)
        change_class = authorization.change_class
        window = pinned.extended if change_class in pinned.extended.classes \
            else pinned.small_medium
        return ResolvedProbationPolicy.from_p10(
            pinned=pinned, window=window, change_class=change_class,
            campaign_policy_pin_event_digest=bundle.pin_event_digest,
            policy_bundle_digest=bundle.policy_bundle_digest,
            probation_policy_digest=bundle.probation_policy_digest,
            shadow_fraction=pinned.shadow_fraction,
            minimum_shadows=pinned.minimum_shadows,
            quality_noninferiority=pinned.quality_noninferiority,
            incident_delta_max=pinned.incident_delta_max,
            eligibility_rule_id=pinned.eligibility_rule_id,
            family_coverage_threshold=pinned.family_coverage_threshold,
            shadow_replay_policy_id=pinned.shadow_replay_policy_id,
            critical_incident_allowance=pinned.critical_incident_allowance,
            resource_cap_rule_id=pinned.resource_cap_rule_id,
            resource_cap_policy_digest=bundle.resource_cap_policy_digest,
            required_metrics=pinned.required_metrics,
            immediate_rollback_triggers=pinned.immediate_rollback_triggers,
            require_complete_outcome_and_resource_receipt=(
                pinned.require_complete_outcome_and_resource_receipt
            ),
            require_permission_profile_match=pinned.require_permission_profile_match,
            exclude_unrelated_infrastructure_failure=(
                pinned.exclude_unrelated_infrastructure_failure
            ),
            forbidden_shadow_effects=pinned.forbidden_shadow_effects,
            protected_family_allowance_source=(
                pinned.protected_family_allowance_source
            ),
        )
```

Extend P10 `CampaignPolicyService` only with `load_probation_policy(bundle)`, which re-hashes and strictly parses the policy file already named by `CampaignPolicyBundle`. It must require every field listed above, reject unknown/missing/duplicate values, require family coverage `5` and critical incident allowance `0`, and return no defaulted value. It must not append an event. P10 already proves `campaign.policy.pinned` precedes G0 and carries its pin event digest through `G4RunReceipt`; P11 carries that same digest/bundle into `promotion.authorized.v1` and `trial_control.ready`.

```python
class ProbationStartStore:
    def start(self, root_id, promotion_id, trial_control_digest, key):
        self.ledger.verify()
        trial = self.trial_controls.resolve(
            root_id, promotion_id, trial_control_digest
        )
        current = self.trial_controls.resolve_current(root_id, promotion_id)
        if current.receipt_digest != trial.receipt_digest:
            raise ProbationStartError("current trial control required")
        authorization = self.promotions.require_authorization(
            root_id, promotion_id
        )
        bundle = self.campaign_policies.resolve(
            authorization.gate_scope
        )
        policy = self.probation_policies.for_promotion(
            root_id, promotion_id, authorization.receipt_digest
        )
        if len({
            bundle.pin_event_digest,
            trial.campaign_policy_pin_event_digest,
            authorization.campaign_policy_pin_event_digest,
        }) != 1:
            raise ProbationStartError("campaign policy pin mismatch")
        if (
            bundle.policy_bundle_digest != trial.policy_bundle_digest
            or bundle.probation_policy_digest != trial.probation_policy_digest
        ):
            raise ProbationStartError("pinned probation policy mismatch")
        self.campaign_policies.require_pin_precedes_g0(authorization.gate_scope)
        return self.commit_started(trial, authorization, policy, key)
```

`ProbationServices.for_session` validates the P05 intent, root/campaign scope, lock owner, authorization digest, and active pinned supervisor, then constructs the start/routing/outcome/shadow/evidence/G5/promotion/C4 stores with a private capability issuer. Before each mutation the owning store derives the exact operation/resource/phase capability and consumes it with the typed terminal receipt. Recovery reconstructs the same service set only from the persisted intent; task or meta inputs cannot serialize this context.

`ProbationStartReceipt` carries root/campaign/generation/experiment/promotion, trial-control/authorization/G4 digests, P10 campaign-policy pin event/bundle/probation digests, every parsed eligibility/outcome/permission/infrastructure/shadow/family/resource rule above, resolved change class/window, full stable/trial/active tuple identities, permission-manifest digest, protected start timestamp, ledger sequence/head, and its canonical receipt digest. Routing enforces the pinned permission/eligibility rules, outcome inclusion enforces complete outcome/resource proof, shadowing denies the pinned forbidden effects, and evidence applies the pinned infrastructure/family source; none of those services redefines the values.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_probation_policy_resolution.py tests/selfloop/test_probation_start.py tests/selfloop/test_probation_mutation_boundary.py tests/selfloop/test_acceptance_policy.py tests/selfloop/test_g4_runner.py tests/selfloop/test_trial_control_receipt.py`

Expected: one campaign policy event, pre-G0 ordering, strict file re-hash, extended thresholds, no second probation pin event, policy drift, forged/stale trial control, and exact active tuple tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/probation/session.py scripts/selfloop_supervisor/probation/policy.py scripts/selfloop_supervisor/probation/start.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/gates/acceptance_policy.py tests/selfloop/test_probation_policy_resolution.py tests/selfloop/test_probation_start.py tests/selfloop/test_probation_mutation_boundary.py tests/selfloop/test_acceptance_policy.py
git commit -m "feat(selfloop): resolve pinned campaign probation policy"
```

### Task 2: Persist complete hashed routing and outcome receipts

**Files:**
- Create: `scripts/selfloop_supervisor/probation/routing.py`
- Create: `scripts/selfloop_supervisor/probation/outcomes.py`
- Test: `tests/selfloop/test_probation_routing.py`
- Test: `tests/selfloop/test_probation_outcomes.py`

**Interfaces:**
- Consumes: verified `ProbationStartReceipt`, current P05 pointer fold, protected task descriptor/input artifacts, exact task permission digest, P03 runtime execution receipt, raw grader/resource artifacts, and protected replay-safety classifier receipt.
- Produces: `TaskRouteRequest`, `RoutingReceipt`, `RoutingStore.route`/`require`/`list_for_promotion`, `TaskOutcomeInput`, `TaskOutcomeReceipt`, and `OutcomeStore.record`/`require`/`list_for_promotion`.
- Canonical `receipt_digest` hashes all semantic fields. `event_sequence`/`event_digest` form the P05 storage envelope and are verified on every read.

- [ ] **Step 1: Write failing persistence, exact-runtime, and tamper tests**

```python
def test_route_is_hashed_persisted_and_derived_from_current_state(
    probation_runtime, protected_task
):
    receipt = probation_runtime.routes.route(
        TaskRouteRequest(
            root_id="root-1", promotion_id="promotion-7",
            task_id=protected_task.task_id,
            task_descriptor_digest=protected_task.descriptor_digest,
            input_artifact_digest=protected_task.input_digest,
            permission_manifest_digest=protected_task.permission_digest,
            idempotency_key="route-task-7",
        )
    )
    assert receipt.probation_eligible is True
    assert receipt.selected_release_id == probation_runtime.trial_release_id
    assert probation_runtime.routes.require(
        "root-1", receipt.receipt_digest
    ) == receipt

def test_permission_mismatch_routes_stable_and_is_not_counted(
    probation_runtime, protected_task
):
    receipt = probation_runtime.route(
        protected_task, permission_manifest_digest=protected_task.other_permission_digest
    )
    assert receipt.selected_release_id == probation_runtime.stable_release_id
    assert receipt.probation_eligible is False
    assert receipt.exclusion_reason == "permission_manifest_mismatch"

def test_outcome_is_derived_from_linked_raw_execution_artifacts(
    probation_runtime, routed_task, real_task_execution
):
    receipt = probation_runtime.outcomes.record(TaskOutcomeInput(
        routing_receipt_digest=routed_task.receipt_digest,
        runtime_execution_receipt_digest=real_task_execution.receipt_digest,
        recorded_input_artifact_digest=real_task_execution.input_artifact_digest,
        grader_artifact_digest=real_task_execution.grader_artifact_digest,
        replay_safety_receipt_digest=real_task_execution.replay_safety_receipt_digest,
        incident_artifact_digest=real_task_execution.incident_artifact_digest,
        idempotency_key="outcome-task-7",
    ))
    assert receipt.loaded_release_id == routed_task.selected_release_id
    assert receipt.family == routed_task.task_family
    assert receipt.recorded_input_artifact_digest == routed_task.input_artifact_digest

def test_ledger_or_artifact_tamper_invalidates_route_and_outcome(
    persisted_route_and_outcome
):
    persisted_route_and_outcome.tamper_one_byte()
    with pytest.raises((LedgerCorruption, ReceiptIntegrityError)):
        persisted_route_and_outcome.read_both()
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_probation_routing.py tests/selfloop/test_probation_outcomes.py`

Expected: collection fails because the ledger-backed routing/outcome repositories do not exist.

- [ ] **Step 3: Define complete schemas and append verified receipts**

```python
@dataclass(frozen=True)
class TaskRouteRequest:
    root_id: str; promotion_id: str; task_id: str
    task_descriptor_digest: str; input_artifact_digest: str
    permission_manifest_digest: str; idempotency_key: str

@dataclass(frozen=True)
class RoutingReceipt:
    schema: str
    root_id: str; campaign_id: str; generation_id: str; experiment_id: str
    promotion_id: str; probation_start_receipt_digest: str
    trial_control_receipt_digest: str
    task_id: str; task_descriptor_digest: str; task_family: str
    input_artifact_digest: str
    task_permission_manifest_digest: str
    approved_permission_manifest_digest: str
    probation_eligible: bool; exclusion_reason: str | None
    stable_release_id: str; stable_slot_id: str
    trial_release_id: str; trial_slot_id: str
    selected_release_id: str; selected_slot_id: str
    selected_config_generation_id: str; selected_runtime_generation_id: str
    campaign_policy_pin_event_digest: str; policy_bundle_digest: str
    probation_policy_id: str; probation_policy_digest: str
    routed_at: str; receipt_digest: str
    event_sequence: int; event_digest: str

class RoutingStore:
    def route(self, request: TaskRouteRequest) -> RoutingReceipt:
        self.ledger.verify()
        start = self.starts.require_current(
            request.root_id, request.promotion_id
        )
        state = self.state.load(request.root_id)
        descriptor = self.artifacts.require_task_descriptor(
            request.task_descriptor_digest, request.task_id
        )
        self.artifacts.require_input(request.input_artifact_digest)
        permission_ok = hmac.compare_digest(
            request.permission_manifest_digest,
            start.approved_permission_manifest_digest,
        )
        eligible = (
            state.status == "probation"
            and state.active_tuple == start.active_trial_tuple
            and permission_ok
            and start.policy.includes(descriptor)
        )
        body = RoutingReceiptBody.from_canonical(
            start, state, descriptor, request, eligible
        )
        return self.receipts.append(body, request.idempotency_key)
```

```python
@dataclass(frozen=True)
class TaskOutcomeInput:
    routing_receipt_digest: str
    runtime_execution_receipt_digest: str
    recorded_input_artifact_digest: str
    grader_artifact_digest: str
    replay_safety_receipt_digest: str
    incident_artifact_digest: str
    idempotency_key: str

@dataclass(frozen=True)
class TaskOutcomeReceipt:
    schema: str
    root_id: str; campaign_id: str; generation_id: str; experiment_id: str
    promotion_id: str; probation_start_receipt_digest: str
    trial_control_receipt_digest: str
    campaign_policy_pin_event_digest: str
    policy_bundle_digest: str; probation_policy_digest: str
    task_id: str; routing_receipt_digest: str; task_family: str
    probation_eligible: bool; exclusion_reason: str | None
    stable_release_id: str; stable_slot_id: str
    trial_release_id: str; trial_slot_id: str
    selected_release_id: str; selected_slot_id: str
    selected_config_generation_id: str; selected_runtime_generation_id: str
    task_permission_manifest_digest: str
    approved_permission_manifest_digest: str
    recorded_input_artifact_digest: str
    runtime_execution_receipt_digest: str
    loaded_release_id: str; loaded_slot_id: str
    grader_artifact_digest: str; grader_status: str
    grader_case_ids: tuple[str, ...]
    critical_failure_case_ids: tuple[str, ...]
    crash_count: int; timeout_count: int
    tokens: int; latency_ms: float; peak_memory_bytes: int; tool_calls: int
    replay_safety_receipt_digest: str; replay_safe: bool
    infrastructure_status: str
    incident_artifact_digest: str
    authenticated_trigger_ids: tuple[str, ...]
    stdout_artifact_digest: str; stderr_artifact_digest: str
    output_artifact_digest: str
    started_at: str; finished_at: str
    receipt_digest: str; event_sequence: int; event_digest: str
```

`OutcomeStore.record` resolves `RoutingReceipt` from the ledger, verifies every content-addressed raw artifact, derives all numeric/status fields from the protected P03 execution/grader/replay-classifier receipts, and requires loaded release/slot plus recorded input to match routing. It rejects duplicate task outcomes, changed idempotency payloads, caller summary booleans, wrong permission manifests, and unbacked artifacts. The declared fields above are the only fields Task 3 shadow code uses.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_probation_routing.py tests/selfloop/test_probation_outcomes.py tests/selfloop/test_ledger.py`

Expected: derived eligibility, exact runtime identity, schema round-trip, idempotency conflict, duplicate task, ledger tamper, artifact tamper, and hash verification tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/probation/routing.py scripts/selfloop_supervisor/probation/outcomes.py tests/selfloop/test_probation_routing.py tests/selfloop/test_probation_outcomes.py
git commit -m "feat(selfloop): persist probation routes and outcomes"
```

### Task 3: Persist safe representative shadow comparisons

**Files:**
- Create: `scripts/selfloop_supervisor/probation/shadow.py`
- Test: `tests/selfloop/test_probation_shadowing.py`

**Interfaces:**
- Consumes: verified eligible `RoutingReceipt` rows, linked `TaskOutcomeReceipt` rows, protected input artifact store/replay-safety receipts, P03 `RestrictedProcessLauncher`, and registered stable bundle.
- Produces: `required_shadow_count`, `ShadowSelectionReceipt`, `ShadowReceipt`, `ShadowStore.select`, and `ShadowStore.run`.
- The denominator is all eligible routing receipts as of the selection cutoff. Only complete replay-safe outcome rows may run; unavailable rows remain in the denominator and keep selection incomplete.

- [ ] **Step 1: Write failing denominator, family, sandbox, and persistence tests**

```python
def test_shadow_quota_uses_all_eligible_routes(shadow_fixture):
    shadow_fixture.add_eligible_routes(20)
    shadow_fixture.add_replay_safe_outcomes(2)
    selection = shadow_fixture.shadows.select(
        "root-1", "promotion-7", "shadow-select-7"
    )
    assert selection.eligible_route_count == 20
    assert selection.required_count == 5
    assert len(selection.selected_outcome_digests) == 2
    assert selection.incomplete_reason == "insufficient_replay_safe_outcomes"

def test_each_family_with_five_eligible_routes_is_covered(shadow_fixture):
    shadow_fixture.add_family("memory", 5)
    shadow_fixture.add_family("routing", 5)
    selection = shadow_fixture.complete_selection()
    assert set(selection.covered_families) >= {"memory", "routing"}

def test_shadow_receipt_is_real_sandboxed_and_ledger_backed(real_shadow_fixture):
    receipt = real_shadow_fixture.run_one()
    assert receipt.sandbox_backend_status == "enforced"
    assert receipt.credentials_present is False
    assert receipt.external_write_probe == "denied"
    assert receipt.disposable_state_removed is True
    assert real_shadow_fixture.shadows.require(
        "root-1", receipt.receipt_digest
    ) == receipt

def test_unbacked_replay_safe_boolean_cannot_enable_shadow(shadow_fixture):
    with pytest.raises(ShadowSafetyError):
        shadow_fixture.run_unbacked_outcome(replay_safe=True)
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_probation_shadowing.py`

Expected: FAIL importing `selfloop_supervisor.probation.shadow`.

- [ ] **Step 3: Select deterministically and execute through P03**

```python
def required_shadow_count(
    eligible_count: int, policy: ResolvedProbationPolicy
) -> int:
    return max(policy.minimum_shadows,
               math.ceil(policy.shadow_fraction * eligible_count))

class ShadowStore:
    def select(self, root_id, promotion_id, key):
        start = self.starts.require(root_id, promotion_id)
        routes = self.routes.list_verified_eligible(
            root_id, promotion_id, cutoff=self.ledger.verify().sequence
        )
        outcomes = self.outcomes.linked_complete_replay_safe(routes)
        ranked = sorted(
            outcomes,
            key=lambda row: sha256_text(
                f"{start.probation_policy_digest}:{promotion_id}:{row.task_id}"
            ),
        )
        selected = select_required_families_then_fill(
            routes, ranked, required_shadow_count(len(routes), start.policy)
        )
        return self.selection_receipts.append(
            start, routes, selected, key
        )

    def run(self, root_id, selection_digest, outcome_digest, key):
        selection = self.selection_receipts.require(root_id, selection_digest)
        outcome = self.outcomes.require(root_id, outcome_digest)
        selection.require_selected(outcome)
        replay = self.replay_safety.require(
            outcome.replay_safety_receipt_digest
        )
        replay.require_safe_and_credential_free()
        with self.artifacts.materialize_readonly(
            outcome.recorded_input_artifact_digest
        ) as recorded_input, disposable_shadow_state() as state_root:
            raw = self.runner.run_stable(
                recorded_input=recorded_input,
                release_id=outcome.stable_release_id,
                slot_id=outcome.stable_slot_id,
                launcher=self.restricted_launcher,
                writable_roots=(state_root,),
                denied_roots=protected_credential_and_external_roots(),
                environment=sanitized_environment_without_credentials(),
            )
        return self.shadow_receipts.append_verified(
            selection, outcome, raw, key
        )
```

`ShadowSelectionReceipt` stores policy/cutoff, all eligible route digests, all candidate outcome digests, required count, selected digests, family denominator/coverage, incomplete reason, canonical digest, and event envelope. `ShadowReceipt` stores selection/outcome/input digests, stable and trial identities, stable task-local load receipt, raw grader/resource artifact digests, P03 backend receipt/digest/status, network/external-write/credential probes, disposable-state deletion receipt, timestamps, canonical digest, and event envelope.

The real P03 backend is mandatory for any shadow used by G5/C4. A scheduling fake may exercise ranking only; its receipt type is marked `test_only` and `ProbationEvidenceBuilder` rejects it.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_probation_shadowing.py tests/selfloop/test_runtime_isolation.py`

Expected: quota, family coverage, missing-outcome denominator, deterministic selection, credential/network/write denial, exact stable load, persistence, and cleanup tests pass. If the supported OS backend is unavailable, the conformance-capable test fails closed with `SandboxUnavailable`.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/probation/shadow.py tests/selfloop/test_probation_shadowing.py
git commit -m "feat(selfloop): persist enforced probation shadows"
```

### Task 4: Build protected evidence and persist typed G5 decisions

**Files:**
- Create: `scripts/selfloop_supervisor/probation/evidence.py`
- Create: `scripts/selfloop_supervisor/probation/g5.py`
- Create: `scripts/selfloop_supervisor/probation/watchdog.py`
- Test: `tests/selfloop/test_probation_evidence.py`
- Test: `tests/selfloop/test_g5_and_watchdog.py`

**Interfaces:**
- Consumes: only verified P05 policy/start/route/outcome/shadow/trigger events, protected clock, P10 `paired_bootstrap`, and P11 `rollback_trial`. No caller policy, G4 policy, receipt collection, derived counter, or verdict.
- Produces: `ProbationEvidenceReceipt`, `ProbationEvidenceBuilder.build(root_id, promotion_id, cutoff_sequence, idempotency_key)`, `G5Receipt`, `G5Store.evaluate_and_commit`/`require_terminal`, and `ProbationWatchdog.observe`.

- [ ] **Step 1: Write failing protected-builder and terminal-receipt tests**

```python
def test_builder_resolves_policy_and_counts_from_ledger_only(probation_records):
    probation_records.add_complete_tasks(20, elapsed_hours=48)
    probation_records.add_real_shadows(5)
    evidence = probation_records.builder.build(
        "root-1", "promotion-7",
        probation_records.ledger.verify().sequence, "evidence-7",
    )
    assert evidence.completed_eligible_tasks == 20
    assert evidence.required_shadow_count == 5
    assert evidence.probation_policy_digest == probation_records.pinned_policy_digest

def test_builder_rejects_forged_summary_or_unbacked_receipt(probation_records):
    with pytest.raises(TypeError):
        probation_records.builder.build(
            "root-1", "promotion-7", 42, "evidence-7",
            completed_eligible_tasks=20,
        )
    probation_records.insert_digest_shaped_shadow_without_event()
    with pytest.raises(EvidenceIntegrityError):
        probation_records.build()

def test_passed_g5_is_typed_persisted_and_hash_linked(complete_probation):
    evidence = complete_probation.build_evidence()
    g5 = complete_probation.g5.evaluate_and_commit(
        "root-1", "promotion-7", evidence.receipt_digest, "g5-7"
    )
    assert g5.gate is GateName.G5
    assert g5.outcome == "pass" and g5.status is GateStatus.PASSED
    assert complete_probation.g5.require_terminal(
        "root-1", "promotion-7", g5.receipt_digest
    ) == g5

def test_integrity_trigger_rolls_back_once_and_persists_terminal_g5(
    triggered_probation
):
    triggered_probation.append_authenticated_trigger("integrity-failure")
    first = triggered_probation.watchdog.observe(
        "root-1", "promotion-7", "watchdog-7"
    )
    second = triggered_probation.watchdog.observe(
        "root-1", "promotion-7", "watchdog-7"
    )
    assert first == second
    assert first.outcome == "rollback"
    assert first.rollback_receipt_digest
    assert triggered_probation.rollback_calls == 1
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_probation_evidence.py tests/selfloop/test_g5_and_watchdog.py`

Expected: collection fails because the protected evidence/G5 stores do not exist.

- [ ] **Step 3: Fold raw events, derive evidence, and persist every decision**

```python
@dataclass(frozen=True)
class ProbationEvidenceReceipt:
    schema: str
    root_id: str; campaign_id: str; generation_id: str; promotion_id: str
    trial_control_receipt_digest: str; probation_start_receipt_digest: str
    campaign_policy_pin_event_digest: str
    policy_bundle_digest: str; probation_policy_digest: str
    cutoff_sequence: int; cutoff_head_digest: str
    eligible_route_digests: tuple[str, ...]
    included_outcome_digests: tuple[str, ...]
    excluded_outcomes: tuple[tuple[str, str], ...]
    shadow_receipt_digests: tuple[str, ...]
    completed_eligible_tasks: int; elapsed_hours: float
    required_shadow_count: int; comparable_shadow_count: int
    covered_families: tuple[str, ...]; missing_family_shadows: tuple[str, ...]
    challenger_only_critical_failures: tuple[str, ...]
    protected_family_deltas: tuple[tuple[str, float], ...]
    quality_statistics: PairedStatistics
    incident_rate_delta: float; resource_violations: tuple[str, ...]
    immediate_trigger_event_digests: tuple[str, ...]
    resource_cap_rule_id: str; resource_cap_policy_digest: str
    required_metrics: tuple[str, ...]
    derivation_artifact_digest: str
    receipt_digest: str; event_sequence: int; event_digest: str

class ProbationEvidenceBuilder:
    def build(self, root_id, promotion_id, cutoff_sequence, idempotency_key):
        head = self.ledger.verify()
        if cutoff_sequence > head.sequence:
            raise EvidenceIntegrityError("cutoff exceeds verified head")
        start = self.starts.require(root_id, promotion_id)
        policy = self.policies.require_digest(
            root_id, start.probation_policy_digest
        )
        routes = self.routes.list_verified(
            root_id, promotion_id, cutoff_sequence
        )
        outcomes = self.outcomes.list_verified(
            root_id, promotion_id, cutoff_sequence
        )
        shadows = self.shadows.list_verified(
            root_id, promotion_id, cutoff_sequence
        )
        derived = derive_probation_evidence(
            start, policy, routes, outcomes, shadows,
            self.triggers.list_authenticated(root_id, cutoff_sequence),
            self.clock.now(),
        )
        return self.receipts.append(derived, idempotency_key)
```

The builder rejects duplicate task IDs, summary-only events, wrong permission/runtime identities, receipt/event hash mismatches, shadows without `enforced` P03 receipts, and evidence after a terminal G5. It counts all eligible routes for shadow quota, only complete exact-permission outcomes for task thresholds, and preserves every exclusion/inconclusive reason. It computes exact stable/trial pairs and calls P10 `paired_bootstrap` with a promotion/policy-derived seed.

```python
@dataclass(frozen=True)
class G5Receipt:
    schema: str
    root_id: str; campaign_id: str; generation_id: str; promotion_id: str
    gate: GateName; status: GateStatus
    trial_control_receipt_digest: str
    policy_bundle_digest: str; probation_policy_digest: str
    evidence_receipt_digest: str; evidence_cutoff_sequence: int
    outcome: str; reason: str
    completed_tasks: int; required_tasks: int
    elapsed_hours: float; required_hours: int
    comparable_shadows: int; required_shadows: int
    immediate_trigger_event_digests: tuple[str, ...]
    protected_family_regressions: tuple[str, ...]
    resource_cap_rule_id: str; resource_cap_policy_digest: str
    rollback_receipt_digest: str | None
    decided_at: str; receipt_digest: str
    event_sequence: int; event_digest: str

class G5Store:
    def evaluate_and_commit(
        self, root_id, promotion_id, evidence_digest, key
    ) -> G5Receipt:
        evidence = self.evidence.require(
            root_id, promotion_id, evidence_digest
        )
        decision = decide_g5(evidence, self.policies.require_digest(
            root_id, evidence.probation_policy_digest
        ))
        if decision.outcome == "rollback":
            intent = self.ledger.record_intent(
                root_id, evidence.campaign_id, "g5.rollback",
                {"evidenceDigest": evidence.receipt_digest,
                 "reason": decision.reason},
                f"{key}:rollback",
            )
            rollback = self.rollback(
                PromotionRequest(root_id, promotion_id, f"{key}:p11"),
                trigger_event_digest=decision.trigger_event_digest,
            )
            return self.receipts.commit_terminal(
                evidence, decision, rollback.receipt_digest, intent, key
            )
        return self.receipts.commit(
            evidence, decision, rollback_receipt_digest=None, key=key
        )
```

`decide_g5` applies this order using the exact pinned policy fields: authenticated triggers intersecting `immediate_rollback_triggers`; task/time completeness; shadow quota/family completeness; critical incidents against allowance `0` and protected-family regression; paired quality lower bound; required metrics and pinned resource-cap policy; incident/resource limits; pass. Open, pass, and rollback each persist `gate=GateName.G5` with `GateStatus.OPEN`, `GateStatus.PASSED`, or `GateStatus.FAILED` respectively. Only passed/failed are terminal; exactly one terminal G5 receipt is allowed per promotion.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_probation_evidence.py tests/selfloop/test_g5_and_watchdog.py tests/selfloop/test_activation_and_rollback.py`

Expected: forged inputs fail; incomplete evidence persists open; full evidence persists pass; each immediate trigger invokes P11 rollback once and persists its linked terminal G5 receipt.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/probation/evidence.py scripts/selfloop_supervisor/probation/g5.py scripts/selfloop_supervisor/probation/watchdog.py tests/selfloop/test_probation_evidence.py tests/selfloop/test_g5_and_watchdog.py
git commit -m "feat(selfloop): persist protected G5 decisions"
```

### Task 5: Promote from canonical state and persist current C4 proof

**Files:**
- Create: `scripts/selfloop_supervisor/probation/retention.py`
- Create: `scripts/selfloop_supervisor/probation/c4_conformance.py`
- Create: `scripts/verify_selfloop_c4.py`
- Modify: `scripts/selfloop_supervisor/conformance.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `scripts/validate_v2.py`
- Test: `tests/selfloop/test_c4_retention.py`
- Test: `tests/selfloop/test_c4_acceptance.py`
- Test: `tests/selfloop/test_adapter_c4.py`
- Modify: `tests/selfloop/conftest.py`

**Interfaces:**
- Produces: `StablePromotionReceipt`, `StablePromotionManager.promote(root_id, promotion_id, g5_receipt_digest, idempotency_key)`, `retained_release_ids`, `RetentionReceipt`, `C4ConformanceReceipt`, `C4ConformanceStore.evaluate_and_commit`, and `current`.
- Neither stable promotion nor C4 accepts caller state, receipt objects, proof lists, policy digests, or outcome booleans.

- [ ] **Step 1: Write failing canonical-promotion, currentness, and real-stack tests**

```python
def test_stable_promotion_has_no_caller_state_argument(passed_probation):
    g5 = passed_probation.g5_receipt
    receipt = passed_probation.promotions.promote(
        "root-1", "promotion-7", g5.receipt_digest, "stable-promote-7"
    )
    assert receipt.stable_tuple == passed_probation.former_trial_tuple
    assert receipt.trial_tuple is None
    with pytest.raises(TypeError):
        passed_probation.promotions.promote(
            "root-1", "promotion-7", g5.receipt_digest,
            "stable-promote-8", state=passed_probation.forged_state,
        )

def test_c4_is_persisted_and_reverified_as_current(promoted_probation):
    receipt = promoted_probation.c4.evaluate_and_commit(
        "root-1", "promotion-7", "c4-7"
    )
    assert receipt.conformance == "C4"
    assert receipt.last_completed_gate == "G5"
    assert promoted_probation.c4.current("root-1") == receipt

@pytest.mark.parametrize("invalidation", (
    "active_pointer", "stable_pointer", "policy", "supervisor",
    "retained_release", "rescue_release", "runtime_proof", "ledger_anchor",
))
def test_c4_stops_being_current_after_proof_invalidation(
    current_c4, invalidation
):
    current_c4.invalidate(invalidation)
    with pytest.raises(C4NotCurrent):
        current_c4.store.current("root-1")

def test_cli_and_mcp_status_advertise_only_current_c4_and_downgrade_stale(
    current_c4
):
    cli = current_c4.run_cli_status()
    mcp = current_c4.call_mcp_status()
    assert cli["conformance"] == mcp["conformance"] == "C4"
    assert cli["conformanceReceiptDigest"] == current_c4.receipt.receipt_digest
    current_c4.invalidate("active_pointer")
    cli = current_c4.run_cli_status()
    mcp = current_c4.call_mcp_status()
    assert cli["conformance"] == mcp["conformance"] == "C3"
    assert cli["blocker"] == "current_c4_receipt_unavailable"
    assert cli["conformanceReceiptDigest"] == current_c4.current_c3.receipt_digest
    assert cli["conformanceReceiptDigest"] != current_c4.receipt.receipt_digest

def test_c4_acceptance_uses_real_temp_stack(real_c4_stack):
    receipt = real_c4_stack.execute()
    assert receipt.conformance == "C4"
    assert real_c4_stack.sqlite_path.is_file()
    assert real_c4_stack.anchor_path.is_file()
    assert real_c4_stack.shadow_backend_statuses == {"enforced"}
    assert real_c4_stack.task_subprocess_count >= 20
    assert real_c4_stack.shadow_subprocess_count >= 5
    assert real_c4_stack.verifier_exit_code == 0
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_c4_retention.py tests/selfloop/test_c4_acceptance.py tests/selfloop/test_adapter_c4.py`

Expected: collection fails because canonical stable promotion, persisted C4, and the executable verifier do not exist.

- [ ] **Step 3: Promote one canonical tuple and re-verify C4 dependencies**

```python
def retained_release_ids(current, prior, rescue):
    ordered = [current, *prior[:3]]
    if rescue not in ordered:
        ordered.append(rescue)
    return tuple(ordered)

class StablePromotionManager:
    def promote(self, root_id, promotion_id, g5_digest, key):
        self.ledger.verify()
        g5 = self.g5.require_terminal(
            root_id, promotion_id, g5_digest
        )
        if (
            g5.gate is not GateName.G5
            or g5.status is not GateStatus.PASSED
            or g5.outcome != "pass"
        ):
            raise StablePromotionError("persisted passed G5 required")
        trial = self.trial_controls.resolve(
            root_id, promotion_id, g5.trial_control_receipt_digest
        )
        state = self.state.load(root_id)
        start = self.starts.require(root_id, promotion_id)
        require_exact_current_trial(state, trial, start, g5)
        retained = retained_release_ids(
            state.trial_tuple.release_id,
            state.stable_history_release_ids,
            state.rescue_release_id,
        )
        switched = self.pointer_store.commit_stable_promotion_transaction(
            root_id=root_id, promotion_id=promotion_id,
            expected_trial_tuple=state.trial_tuple,
            stable_tuple=state.trial_tuple, active_tuple=state.trial_tuple,
            trial_tuple=None, retained_release_ids=retained,
            g5_receipt_digest=g5.receipt_digest, idempotency_key=key,
        )
        self.projection.rebuild_atomic(root_id, switched)
        loaded = self.host_probe.require_exact(switched.active_tuple)
        retention = self.retention.apply_journaled(switched, retained)
        return self.receipts.commit(switched, loaded, retention, key)
```

Deletion/permission changes for retention are external effects and use the P11 phase-journal pattern. Current plus three prior stable champions and rescue are verified before any older slot is quarantined. Rescue remains read-only and independently launchable.

```python
@dataclass(frozen=True)
class C4ConformanceReceipt:
    schema: str; root_id: str; campaign_id: str; generation_id: str
    promotion_id: str; conformance: str; status: str
    last_completed_gate: str
    stable_promotion_receipt_digest: str
    g5_receipt_digest: str; evidence_receipt_digest: str
    trial_control_receipt_digest: str
    campaign_policy_pin_event_digest: str
    routing_receipt_digests: tuple[str, ...]
    outcome_receipt_digests: tuple[str, ...]
    shadow_receipt_digests: tuple[str, ...]
    rollback_drill_receipt_digest: str
    active_runtime_receipt_digest: str
    retention_receipt_digest: str; rescue_receipt_digest: str
    active_tuple: ActiveTuple
    supervisor_digest: str; spec_digest: str
    policy_bundle_digest: str; probation_policy_digest: str
    achieved_at: str; achieved_sequence: int
    achieved_head_digest: str; receipt_digest: str

class C4ConformanceStore:
    def evaluate_and_commit(self, root_id, promotion_id, key):
        self.ledger.verify()
        proof = self.fold_required_persisted_proofs(root_id, promotion_id)
        proof.require_p10_campaign_policy_pin_precedes_g0()
        proof.require_trial_control_and_real_rollback_drill()
        proof.require_complete_routes_outcomes_and_enforced_shadows()
        proof.require_terminal_g5(
            gate=GateName.G5, status=GateStatus.PASSED, outcome="pass"
        )
        proof.require_canonical_stable_promotion_and_exact_runtime()
        proof.require_retention_and_rescue()
        return self.receipts.append_achieved(proof, key)

    def current(self, root_id):
        self.ledger.verify()
        receipt = self.receipts.latest_achieved(root_id)
        self.revalidate_every_digest_and_current_identity(receipt)
        return receipt
```

`current` reopens every referenced event/artifact, recomputes receipt digests, verifies the C4 event remains on the anchored chain, and compares current stable/active tuple, supervisor, spec, policy, retained champions, rescue, and task-local runtime receipt. Any later invalidating pointer/policy/supervisor/retention event makes C4 unavailable until a new `conformance.c4.achieved` receipt is committed.

Extend the shared P08 `ConformanceRegistry` rather than adding an adapter-local stage flag:

```python
def current_for_root(self, root_id, loaded_release, policy_bundle_digest):
    try:
        c4 = self.c4.current(root_id)
    except C4NotCurrent:
        c4 = None
    if (
        c4 is not None
        and c4.active_tuple.release_id == loaded_release.release_id
        and c4.policy_bundle_digest == policy_bundle_digest
    ):
        return CurrentConformance("C4", c4.receipt_digest, None)
    c3 = self.c3.current(root_id, loaded_release, policy_bundle_digest)
    if c3 is not None:
        return CurrentConformance(
            "C3", c3.receipt_digest, "current_c4_receipt_unavailable"
        )
    return self.highest_lower_current(root_id, loaded_release)
```

`SelfloopController.status` resolves the loaded release/runtime receipt and calls `ConformanceRegistry.current_for_root` on every request. CLI and MCP serialize that one controller payload and never infer C4 from `state.yaml`, source files, a prior response, or a raw `conformance.c4.achieved` row. When any C4 dependency becomes stale, the next CLI/MCP status response downgrades to the highest currently verified lower receipt (C3 in the test), replaces the stale C4 digest with that verified lower receipt digest, and exposes `current_c4_receipt_unavailable`.

Implement `scripts/verify_selfloop_c4.py --sips-home PATH --root-id ID` by opening `Ledger` and printing `C4ConformanceStore.current` as canonical JSON. Extend `validate_v2.py` with `--verify-c4` that calls the same verifier. The normal source validator may report that the verifier is installed; it must not report C4 without `--sips-home`, `--root-id`, and a current persisted receipt.

Define `real_c4_stack` in `tests/selfloop/conftest.py` without preconstructed proof objects. It must:

1. Create a real temporary Git root, build two actual P02 release bundles/manifests, seed actual immutable slots, and open an actual P05 SQLite ledger plus external anchor.
2. Pin one P10 campaign policy bundle before G0, run the real G0-G4 and executable C3 APIs, persist/verify the current P10 C3 receipt, authorize/install/activate the trial, perform the actual P11 rollback drill, and reactivate it through atomic filesystem projections.
3. Launch at least 20 tiny task processes through the normal runtime launcher and record their actual load/stdout/stderr/grader/resource/replay-safety artifacts. The supervisor-owned deterministic test clock advances past 48 hours; callers never submit timestamps.
4. Run at least five selected stable shadows through the real supported P03 OS backend with credential/network/external-write denial probes and disposable state.
5. Build evidence, persist passed G5, promote from canonical state, verify task-local loaded stable identity, apply retention, persist C4, and invoke `verify_selfloop_c4.py` before temporary cleanup.

The fixture computes every digest from bytes and obtains every status from the invoked subsystem. It may not instantiate `RoutingReceipt`, `TaskOutcomeReceipt`, `ShadowReceipt`, `G5Receipt`, or `C4ConformanceReceipt` directly; may not use literal `sha256:...` proof strings; and may not monkeypatch `status="enforced"`, runtime identity, ledger reads, or conformance checks. If the real P03 backend is unavailable, the acceptance test fails closed and C4 remains unproven rather than skipping or substituting a fake receipt.

- [ ] **Step 4: Run the Plan 12 gate**

Run:

```bash
python3 -m pytest -q \
  tests/selfloop/test_probation_mutation_boundary.py \
  tests/selfloop/test_probation_policy_resolution.py \
  tests/selfloop/test_probation_start.py \
  tests/selfloop/test_probation_routing.py \
  tests/selfloop/test_probation_outcomes.py \
  tests/selfloop/test_probation_shadowing.py \
  tests/selfloop/test_probation_evidence.py \
  tests/selfloop/test_g5_and_watchdog.py \
  tests/selfloop/test_c4_retention.py \
  tests/selfloop/test_c4_acceptance.py \
  tests/selfloop/test_adapter_c4.py
python3 scripts/validate_v2.py --check-eval
git diff --check
```

Expected on the supported target: all selected tests pass, including the real temp-root C4 stack and subprocess verifier; source validator exits `0` without inferring a live C4 claim; diff check is silent. Without the required OS sandbox backend, the acceptance test fails explicitly and C4 remains C3/G5-unproven.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/probation/retention.py scripts/selfloop_supervisor/probation/c4_conformance.py scripts/verify_selfloop_c4.py scripts/selfloop_supervisor/conformance.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py scripts/validate_v2.py tests/selfloop/conftest.py tests/selfloop/test_c4_retention.py tests/selfloop/test_c4_acceptance.py tests/selfloop/test_adapter_c4.py
git commit -m "feat(selfloop): persist and verify current C4 conformance"
```

## Plan 12 Completion Gate

- [ ] Every P12 mutation is performed by a live session-bound controller service and consumes a phase-scoped capability; direct, closed-intent, cross-session, and task-input attempts cannot mutate probation state.
- [ ] Probation resolves the exact persisted/current Plan 11 trial-control receipt and the same P10 `campaign.policy.pinned` event; no second policy authority exists and the pin provably precedes G0.
- [ ] Every ordinary probation task has a complete canonical-hash routing event, and each recorded outcome links exact runtime, permission, input, grader, resource, replay-safety, and artifact evidence in the ledger.
- [ ] Shadow quota uses all eligible routes, family coverage is enforced, and every counted comparison has a real persisted P03 denial/runtime receipt.
- [ ] `ProbationEvidenceBuilder` accepts only verified ledger history and persists its derivation; callers cannot inject policy, counters, summaries, or verdicts.
- [ ] Open/pass/rollback G5 decisions are typed and persisted; terminal rollback links one actual P11 rollback receipt, and terminal pass is unique.
- [ ] Stable promotion reads canonical current state plus the persisted passed G5 receipt, atomically promotes the complete former trial tuple, clears trial, and preserves current plus three prior champions and rescue.
- [ ] C4 is a persisted current receipt whose dependencies are reverified; controller/CLI/MCP status exposes its digest only while current and immediately downgrades on stale proof; the executable real temp-root acceptance passes without constructed proof objects, literal proof hashes, fake sandbox/runtime statuses, skipped checks, or live-state mutation.
- [ ] Execute the roadmap's **Shared protected-runtime rollover execution task** with `SOURCE_STAGE=P11`, `TARGET_STAGE=P12`, and the exact committed P12 SHA; verify its authorization/pending/activation/rescue/fresh-loader receipt chain before runtime-facing probation/C4 verification is accepted.
