# Selfloop Sealed G4 and Lexicographic Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete C3 by resolving the exact ledger-backed G0-G3 survivor, running sealed paired G4 under the pinned campaign policy bundle, deriving all decision evidence in the protected supervisor, and persisting an executable hash-linked C3 receipt.

**Architecture:** The pinned supervisor owns policy loading, sealed manifests, case selection, graders, statistics, evaluator evolution, evidence derivation, and decisions. G4 accepts only a `GateScope` plus the event digest of Plan 9's persisted `development.g0_g3.ready`; it resolves every other identity and proof from the anchored campaign ledger. Unit tests may use deterministic fake process adapters, but C3 issuance additionally requires a temp-root integration run through the real P03 OS sandbox and a read-only executable validator.

**Tech Stack:** Python 3.10+, standard-library dataclasses/hashlib/json/math/random/statistics/pathlib, P03 restricted processes, P05 protected SQLite ledger, P09 gate store/artifacts, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- Acceptance, probation, sealed cases, graders, seeds, evaluator registry, ledger, meter, and decision code execute from a pinned immutable `${SIPS_HOME}/selfloop/supervisor/bundles/<supervisor-digest>/` outside candidate worktrees.
- After source tests pass, the active P09 controller must TTY-authorize, prepare, and activate the exact P10 release through the roadmap's protected rollover checkpoint. C3 issuance and adapter checks run only after a fresh loader proves the P10 gate/policy/evaluator module hashes; source presence cannot stand in for that activation.
- Every ledger mutation uses `Ledger.append(root_id, campaign_id, event_type, payload, idempotency_key)`. Evaluator registration, activation, audits, G4 phases, and C3 are campaign-scoped.
- Every mutating policy, sealed-run, evidence, decision, evaluator, audit, and conformance service is obtained from the P05 controller's live `SessionBoundMutationContext`; each phase consumes a distinct operation/resource-scoped `MutationCapability`. Public method signatures intentionally omit caller-supplied capabilities because the protected service instance holds and validates the non-serializable context. Direct/unbound construction, closed-intent reuse, and cross-session recovery fail; read-only `resolve`/`verify_existing` remain capability-free.
- A protected `campaign.policy.pinned` event fixes the G4 policy file digest, probation policy file digest, evaluator/grader identity, supervisor digest, and spec digest before G0. Missing or changed pins fail G4; callers never pass a `G4Policy` object to `G4Runner`.
- G4 resolves the exact Plan 9 readiness event and its ordered G0-G3 chain for the same root, campaign, generation, experiment, candidate release, champion release, diff, pairing base, evaluator, policy bundle, and supervisor.
- Candidate/champion processes receive only individual sealed envelopes and fixed runtime grants. They receive no sealed root, grader, policy path, acceptance threshold, ledger, evaluator registry, full membership, or supervisor credentials.
- Raw process results contain observations only. Integrity, correctness, protected-family deltas, resource compliance, critical failures, candidate kind, and promotion eligibility are derived by a protected evidence builder from raw artifacts and ledger events; caller booleans are ignored and rejected by schema.
- Promotion is lexicographic: integrity, correctness, protected-family bounds, resource caps, then benefit. Ambiguity retains the stable champion.
- Default quality promotion requires challenger-only critical failures `0` and a one-sided 95% paired lower confidence bound greater than `0.01`. Efficiency requires lower bound at least `-0.01` and at least `10%` median token or latency reduction without another cap violation.
- The default confidence method is deterministic paired bootstrap with exactly `10000` resamples and a seed derived from the experiment ID.
- Evaluator repairs are accepted only after old-supervisor frozen tests, adversarial fixtures, and independent review resolve from the same campaign ledger. Activation occurs in a later generation only after an exact champion baseline recomputation under the new evaluator identity.
- G4 and C3 are phase-journaled. Resume reuses Plan 9 content-addressed raw artifacts and never repeats a completed sealed process or reconciled grant.
- A hash-looking string, fabricated receipt object, fake sandbox `status`, source-file existence, or JSON projection cannot satisfy C3.
- Tests use temporary sealed and candidate roots. The C3 integration test uses the real P03 enforcement backend, actual subprocess receipts, actual ledger events, and computed artifact digests; if the backend is unavailable, C3 remains unavailable and the acceptance gate fails closed.

---

### Task 1: Pin the complete campaign policy bundle before G0

**Files:**
- Create: `references/selfloop/policies/g4-policy-v1.json`
- Create: `references/selfloop/policies/probation-policy-v1.json`
- Create: `scripts/selfloop_supervisor/gates/acceptance_policy.py`
- Create: `tests/selfloop/fixtures/g4-policy.v1.json`
- Create: `tests/selfloop/fixtures/probation-policy.v1.json`
- Test: `tests/selfloop/test_acceptance_policy.py`

**Interfaces:**
- Consumes: protected policy files copied into the pinned supervisor bundle, P05 current campaign state and `SessionBoundMutationContext`, and current evaluator/grader/supervisor/spec identities.
- Produces: `CampaignPolicyScope(root_id, campaign_id, generation_id, supervisor_digest)`, `G4Policy`, `ProbationPolicyPin`, `CampaignPolicyBundle`, `CampaignPolicyService.pin(campaign_scope, g4_path, probation_path, evaluator_identity, idempotency_key)`, and `CampaignPolicyService.resolve(gate_scope) -> CampaignPolicyBundle`.
- `pin` is legal only before the first G0 intent. `resolve` verifies the anchored event and both file digests on every use.
- `CampaignPolicyScope` deliberately has no policy digest; `GateScope` is constructed only after `pin` returns the bundle digest, avoiding a circular trust input.

- [ ] **Step 1: Add exact policy fixtures and failing pin/tamper tests**

```json
{
  "schema": "selfloop.g4-policy.v1",
  "policyId": "local-auto-v1:g4.v1",
  "sealedCaseSetId": "holdout.v1",
  "requiredQualityGain": 0.01,
  "bootstrapResamples": 10000,
  "confidenceLevel": 0.95,
  "efficiencyNoninferiority": -0.01,
  "efficiencyReduction": 0.10,
  "protectedFamilies": [
    {"name": "state-integrity", "critical": true, "maxLoss": 0.0},
    {"name": "memory-recall", "critical": false, "maxLoss": 0.01}
  ]
}
```

```json
{
  "schema": "selfloop.probation-policy.v1",
  "policyId": "probation.v1",
  "smallMedium": {"minimumTasks": 20, "minimumHours": 48},
  "extended": {"classes": ["large", "meta", "architecture", "permission", "persistence"], "minimumTasks": 50, "minimumHours": 168},
  "shadowFraction": 0.20,
  "minimumShadows": 5,
  "familyCoverageMinimumEligibleTasks": 5,
  "eligibilityRuleId": "probation-eligibility.v1",
  "requireCompleteOutcomeAndResourceReceipt": true,
  "requirePermissionProfileMatch": true,
  "excludeUnrelatedInfrastructureFailure": true,
  "shadowReplayPolicyId": "disposable-no-external-effects.v1",
  "forbiddenShadowEffects": ["external-write", "message", "purchase", "publish", "production-mutation"],
  "requiredMetrics": ["correctness", "protected-families", "crashes", "timeouts", "tokens", "latency", "memory", "tool-calls", "state-integrity"],
  "qualityNoninferiority": -0.01,
  "criticalIncidentAllowance": 0,
  "incidentDeltaMax": 0.01,
  "protectedFamilyAllowanceSource": "g4-policy-v1",
  "resourceCapRuleId": "pinned-campaign-budget-no-violation.v1",
  "immediateRollbackTriggers": [
    "integrity-failure",
    "permission-expansion",
    "state-or-evidence-corruption",
    "critical-regression",
    "repeated-crash-or-timeout",
    "budget-or-metering-bypass",
    "install-hash-or-capability-failure",
    "incompatible-memory-or-configuration-migration",
    "watchdog-or-rescue-canary-failure"
  ]
}
```

```python
def test_policy_bundle_is_persisted_with_real_file_digests(policy_campaign):
    pinned = policy_campaign.pin()
    assert pinned.g4_policy_digest == sha256_path(policy_campaign.g4_path)
    assert pinned.probation_policy_digest == sha256_path(policy_campaign.probation_path)
    event = policy_campaign.ledger.event_by_digest(
        policy_campaign.scope.root_id, policy_campaign.scope.campaign_id,
        pinned.pin_event_digest,
    )
    assert event.event_type == "campaign.policy.pinned"
    assert pinned.resource_cap_policy_digest == policy_campaign.canonical_budget_policy_digest
    assert event.payload["resourceCapPolicyDigest"] == policy_campaign.canonical_budget_policy_digest

def test_policy_cannot_change_after_g0_intent(policy_campaign):
    policy_campaign.pin()
    policy_campaign.append_g0_intent()
    policy_campaign.change_required_gain(0.0)
    with pytest.raises(PolicyPinMismatch, match="G4 policy digest"):
        policy_campaign.resolve()

def test_probation_pin_contains_complete_pre_g4_inclusion_and_g5_policy(policy_campaign):
    bundle = policy_campaign.pin()
    policy = policy_campaign.service.load_probation_policy(bundle)
    assert policy.family_coverage_minimum_eligible_tasks == 5
    assert policy.eligibility_rule_id == "probation-eligibility.v1"
    assert policy.shadow_replay_policy_id == "disposable-no-external-effects.v1"
    assert policy.critical_incident_allowance == 0
    assert policy.resource_cap_rule_id == "pinned-campaign-budget-no-violation.v1"
    assert set(policy.required_metrics) >= {"correctness", "state-integrity", "memory"}
    assert "watchdog-or-rescue-canary-failure" in policy.immediate_rollback_triggers

def test_unbound_policy_service_cannot_pin(policy_campaign):
    unbound = CampaignPolicyService(
        policy_campaign.ledger, policy_campaign.campaign_state,
    )
    with pytest.raises(MutationDenied, match="controller mutation session required"):
        unbound.pin(
            policy_campaign.scope, policy_campaign.g4_path,
            policy_campaign.probation_path, policy_campaign.evaluator,
            "policy:unbound",
        )

```

- [ ] **Step 2: Run the tests and confirm the policy service is absent**

Run: `python3 -m pytest -q tests/selfloop/test_acceptance_policy.py`

Expected: collection fails because `selfloop_supervisor.gates.acceptance_policy` does not exist.

- [ ] **Step 3: Implement strict parsing, canonical bundle digest, and campaign-scoped persistence**

```python
@dataclass(frozen=True)
class CampaignPolicyBundle:
    policy_bundle_digest: str
    g4_policy: G4Policy
    g4_policy_digest: str
    probation_policy_id: str
    probation_policy_digest: str
    evaluator_version: str
    grader_bundle_sha: str
    evaluator_digest: str
    resource_cap_policy_digest: str
    supervisor_digest: str
    spec_digest: str
    pin_event_digest: str

class CampaignPolicyService:
    def pin(self, campaign_scope, g4_path, probation_path, evaluator_identity,
            idempotency_key):
        if self.gates.has_intent(campaign_scope):
            raise PolicyAlreadyInUse("campaign policy must be pinned before G0")
        g4 = load_g4_policy(g4_path)
        probation = load_probation_policy_pin(probation_path)
        resource_caps = self.campaign_state.require_budget_policy(campaign_scope)
        body = {
            "schema": "selfloop.campaign-policy-bundle.v1",
            "generationId": campaign_scope.generation_id,
            "g4PolicyId": g4.policy_id,
            "g4PolicyDigest": sha256_path(g4_path),
            "probationPolicyId": probation.policy_id,
            "probationPolicyDigest": sha256_path(probation_path),
            "evaluatorVersion": evaluator_identity.version,
            "graderBundleSha": evaluator_identity.grader_bundle_sha,
            "evaluatorDigest": evaluator_identity.digest,
            "resourceCapPolicyDigest": resource_caps.policy_digest,
            "supervisorDigest": campaign_scope.supervisor_digest,
            "specDigest": SPEC_DIGEST,
        }
        body["policyBundleDigest"] = sha256_canonical(body)
        event = self.ledger.append(
            campaign_scope.root_id, campaign_scope.campaign_id,
            "campaign.policy.pinned",
            body, idempotency_key,
        )
        return CampaignPolicyBundle.from_event_and_files(event, g4_path, probation_path)
```

Strict loaders reject unknown keys, missing fields, duplicate/empty protected families/triggers/metrics, nonfinite numbers, thresholds different from the versioned policy, a nonzero critical allowance, resamples other than `10000`, confidence other than `0.95`, and probation values different from the normative windows. The probation loader requires the exact eligibility, permission, infrastructure, replay-safety, forbidden-effect, protected-family, resource-cap, metric, and immediate-trigger rules shown above; none may be supplied or defaulted after the pin. `pin` resolves the exact canonical campaign budget/resource-cap policy and includes its digest in the bundle event. `resolve` reads the unique pin event for the exact campaign, verifies its event digest, current supervisor-bundle files, and still-registered resource-cap policy, and compares its bundle digest with `GateScope.policy_bundle_digest`.

- [ ] **Step 4: Run policy schema, campaign, tamper, and late-change tests**

Run: `python3 -m pytest -q tests/selfloop/test_acceptance_policy.py tests/selfloop/test_gate_store.py`

Expected: all tests pass; wrong campaign, changed file, changed evaluator, changed supervisor, unknown field, and post-G0 repin fail closed.

- [ ] **Step 5: Commit the pinned policy bundle**

```bash
git add references/selfloop/policies/g4-policy-v1.json references/selfloop/policies/probation-policy-v1.json scripts/selfloop_supervisor/gates/acceptance_policy.py tests/selfloop/fixtures/g4-policy.v1.json tests/selfloop/fixtures/probation-policy.v1.json tests/selfloop/test_acceptance_policy.py
git commit -m "feat(selfloop): pin G4 and probation campaign policy"
```

### Task 2: Broker sealed cases and persist real OS-sandbox attestations

**Files:**
- Create: `scripts/selfloop_supervisor/gates/sealed_cases.py`
- Create: `scripts/selfloop_supervisor/gates/sealed_sandbox_audit.py`
- Test: `tests/selfloop/test_sealed_cases.py`

**Interfaces:**
- Consumes: supervisor-only sealed root, `CampaignPolicyBundle.g4_policy.sealed_case_set_id`, selection seed, P03 `RestrictedProcessLauncher`, and `GateLedger`.
- Produces: `SealedCaseEnvelope`, `SealedCaseBroker.select`, and `SealedSandboxAuditService.issue(scope, g4_execution_id, process_receipt_event_digests, idempotency_key)`.
- The audit service resolves each P03 process event from the same campaign, verifies its backend attestation and denied roots, and appends `sealed.sandbox.audited`. It does not accept status strings.

- [ ] **Step 1: Write failing exposure and real-backend tests**

```python
def test_envelope_exposes_no_path_grader_policy_or_full_seed(sealed_broker):
    envelope = sealed_broker.select("holdout.v1", "experiment-a:sealed-order")[0]
    serialized = json.dumps(dataclasses.asdict(envelope), sort_keys=True)
    assert "prompt" in serialized
    assert "sealed" not in serialized
    assert "grader" not in serialized
    assert "policy" not in serialized

def test_candidate_process_cannot_read_sealed_ledger_or_policy(
    real_restricted_launcher, real_process_limits, sealed_layout, candidate_root,
):
    result = real_restricted_launcher.run(
        command=(sys.executable, "-c", sealed_layout.adversarial_probe),
        cwd=candidate_root,
        readable_roots=(candidate_root,), writable_roots=(candidate_root / "work",),
        denied_roots=(sealed_layout.sealed_root, sealed_layout.ledger_root,
                      sealed_layout.policy_root),
        environment={}, limits=real_process_limits,
    )
    assert result.exit_code != 0
    assert result.sandbox_backend_receipt.backend_id == "darwin-sandbox-exec.v1"
    assert result.sandbox_backend_receipt.status == "enforced"

def test_audit_rejects_fabricated_enforced_object(sealed_audit, gate_scope):
    with pytest.raises(ProofTypeMismatch, match="process receipt event"):
        sealed_audit.issue(
            gate_scope, "execution-a",
            (types.SimpleNamespace(status="enforced"),), "sandbox:audit"
        )
```

- [ ] **Step 2: Run the tests and confirm sealed brokering is absent**

Run: `python3 -m pytest -q tests/selfloop/test_sealed_cases.py`

Expected: collection fails because `selfloop_supervisor.gates.sealed_cases` does not exist.

- [ ] **Step 3: Implement opaque envelopes and event-backed sandbox auditing**

```python
@dataclass(frozen=True)
class SealedCaseEnvelope:
    opaque_case_id: str
    case_version: int
    protected_family: str
    prompt: str

class SealedSandboxAuditService:
    def issue(self, scope, execution_id, process_event_digests, idempotency_key):
        if not process_event_digests:
            raise MissingSandboxProof("sealed G4 requires process receipts")
        receipts = tuple(
            self.process_receipts.resolve(scope, event_digest)
            for event_digest in process_event_digests
        )
        for receipt in receipts:
            self.backend_attestor.verify(receipt.sandbox_backend_receipt)
            require_denied_roots(receipt, self.protected_roots)
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "sealed.sandbox.audited",
            {"experimentId": scope.experiment_id, "executionId": execution_id,
             "processReceiptEventDigests": list(process_event_digests),
             "backendAttestationDigests": [
                 row.sandbox_backend_receipt.attestation_digest for row in receipts
             ]}, idempotency_key,
        )
        return SandboxAuditReceipt.from_event(event)
```

`SealedCaseBroker` validates the manifest schema, exact case-set ID, nonempty unique cases, relative grader paths contained by the sealed root, and a selection seed derived from the experiment. It returns envelopes only; grader resolution stays in the protected parent process.

- [ ] **Step 4: Run real denial, unavailable-backend, audit, and sealed-integrity tests**

Run: `python3 -m pytest -q tests/selfloop/test_sealed_cases.py tests/selfloop/test_runtime_isolation.py`

Expected: on the supported Darwin target all tests pass and `/usr/bin/sandbox-exec` denies absolute sealed/ledger/policy access. When the backend is absent, the launcher raises `SandboxUnavailable`, no audit event is appended, and C3 remains unavailable.

- [ ] **Step 5: Commit sealed brokering and attestation**

```bash
git add scripts/selfloop_supervisor/gates/sealed_cases.py scripts/selfloop_supervisor/gates/sealed_sandbox_audit.py tests/selfloop/test_sealed_cases.py
git commit -m "feat(selfloop): attest sealed G4 sandbox enforcement"
```

### Task 3: Derive protected G4 evidence and lexicographic decisions

**Files:**
- Create: `scripts/selfloop_supervisor/gates/paired_statistics.py`
- Create: `scripts/selfloop_supervisor/gates/g4_evidence.py`
- Create: `scripts/selfloop_supervisor/gates/decision.py`
- Test: `tests/selfloop/test_paired_statistics.py`
- Test: `tests/selfloop/test_g4_evidence.py`
- Test: `tests/selfloop/test_lexicographic_decision.py`

**Interfaces:**
- Consumes: P09 verified `RawPairArtifact`, protected grader receipts, P08 experiment/card event, P05 usage/grant receipts, `CampaignPolicyBundle`, and sandbox audit.
- Produces: `PairedStatistics`, `G4EvidenceReceipt`, `G4EvidenceBuilder.build(scope, raw_pair_event_digest, sandbox_audit_event_digest, idempotency_key)`, `G4Decision`, and `G4DecisionService.decide(scope, evidence_event_digest, idempotency_key)`.
- Production decision code accepts only a persisted `g4.evidence.built` event digest. The raw runner schema rejects `integrity_ok`, `correctness_ok`, `resources_ok`, `candidate_kind`, family deltas, confidence bounds, and promotion fields.

- [ ] **Step 1: Write failing derivation, precedence, and caller-boolean tests**

```python
def test_raw_pair_summary_booleans_are_rejected(g4_campaign):
    raw = g4_campaign.raw_pair_payload()
    raw["integrity_ok"] = True
    with pytest.raises(UnknownRawResultField, match="integrity_ok"):
        g4_campaign.evidence_builder.build_from_payload(raw)

def test_evidence_derives_candidate_kind_from_card_event(g4_campaign):
    g4_campaign.card_event.payload["candidateKind"] = "efficiency"
    evidence = g4_campaign.build_evidence()
    assert evidence.candidate_kind == "efficiency"
    assert evidence.source_card_event_digest == g4_campaign.card_event.digest

def test_integrity_failure_precedes_large_quality_gain(g4_campaign):
    g4_campaign.raw_candidate_attempts_sealed_read()
    g4_campaign.raw_scores(candidate=(1.0,) * 8, champion=(0.0,) * 8)
    evidence = g4_campaign.build_evidence()
    decision = g4_campaign.decide(evidence)
    assert decision.outcome == "reject"
    assert decision.failed_class == "integrity"

def test_incomplete_pairs_and_unknown_usage_never_build_evidence(g4_campaign):
    g4_campaign.remove_champion_pair()
    g4_campaign.mark_candidate_tokens_unknown()
    with pytest.raises(IncompleteG4Evidence):
        g4_campaign.build_evidence()
```

- [ ] **Step 2: Run the tests and verify the evidence builder is absent**

Run: `python3 -m pytest -q tests/selfloop/test_paired_statistics.py tests/selfloop/test_g4_evidence.py tests/selfloop/test_lexicographic_decision.py`

Expected: collection fails because `selfloop_supervisor.gates.g4_evidence` does not exist.

- [ ] **Step 3: Implement deterministic statistics and source-linked evidence**

```python
def paired_bootstrap(candidate, champion, experiment_id, resamples=10000, confidence=0.95):
    if not candidate or len(candidate) != len(champion):
        raise ValueError("paired bootstrap requires complete equal-length pairs")
    if resamples != 10000 or confidence != 0.95:
        raise ValueError("paired-bootstrap.v1 requires 10000 resamples at 95% confidence")
    deltas = tuple(require_finite(left) - require_finite(right)
                   for left, right in zip(candidate, champion))
    seed = int.from_bytes(hashlib.sha256(experiment_id.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(deltas) for _ in deltas)
        for _ in range(resamples)
    )
    lower_index = int((1.0 - confidence) * resamples)
    return PairedStatistics(
        pair_count=len(deltas), mean_delta=statistics.fmean(deltas),
        lower_bound=means[lower_index], method="paired-bootstrap.v1", seed=seed,
    )
```

```python
class G4EvidenceBuilder:
    def build(self, scope, raw_pair_event_digest, sandbox_audit_event_digest,
              idempotency_key):
        raw_event = self.store.resolve_event(scope, raw_pair_event_digest, "gate.raw_pair.sealed")
        raw = self.artifacts.load_and_verify(raw_event.payload["manifestDigest"])
        raw.reject_summary_fields()
        sandbox = self.store.resolve_event(
            scope, sandbox_audit_event_digest, "sealed.sandbox.audited"
        )
        require_same_execution(raw_event, sandbox)
        card = self.store.resolve_exact_card(scope)
        policy = self.policies.resolve(scope)
        graded = self.graders.grade_all(raw, policy.g4_policy)
        usage = self.meter.resolve_and_verify_all(scope, raw.usage_receipt_event_digests)
        statistics = paired_bootstrap(
            graded.candidate_scores, graded.champion_scores, scope.experiment_id,
            policy.g4_policy.bootstrap_resamples, policy.g4_policy.confidence_level,
        )
        evidence = G4EvidenceReceipt.derive(
            scope=scope, raw=raw, graded=graded, usage=usage, statistics=statistics,
            candidate_kind=card.payload["candidateKind"], policy=policy,
            sandbox_audit_event_digest=sandbox.digest,
            source_card_event_digest=card.digest,
        )
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "g4.evidence.built",
            evidence.to_payload(), idempotency_key,
        )
        return G4EvidenceReceipt.from_event(event)
```

`G4DecisionService.decide` resolves the evidence event and current policy pin, verifies every source event/artifact again, then applies integrity → correctness → protected families → resource caps → benefit. It appends `g4.decision.made` with the evidence event digest, evidence receipt digest, policy bundle digest, outcome, failed class, champion-stays flag, and reason.

```python
decision_event = self.ledger.append(
    scope.root_id, scope.campaign_id, "g4.decision.made",
    decision.to_payload(evidence_event_digest=evidence.event_digest,
                        policy_bundle_digest=policy.policy_bundle_digest),
    idempotency_key,
)
```

- [ ] **Step 4: Run derivation, statistics, policy, and lexicographic tests**

Run: `python3 -m pytest -q tests/selfloop/test_paired_statistics.py tests/selfloop/test_g4_evidence.py tests/selfloop/test_lexicographic_decision.py tests/selfloop/test_acceptance_policy.py`

Expected: all tests pass; summary injection, wrong card, wrong campaign, incomplete pairing, unknown usage, artifact tamper, and missing protected families fail before a decision event.

- [ ] **Step 5: Commit protected G4 evidence and decision derivation**

```bash
git add scripts/selfloop_supervisor/gates/paired_statistics.py scripts/selfloop_supervisor/gates/g4_evidence.py scripts/selfloop_supervisor/gates/decision.py tests/selfloop/test_paired_statistics.py tests/selfloop/test_g4_evidence.py tests/selfloop/test_lexicographic_decision.py
git commit -m "feat(selfloop): derive sealed G4 decisions from raw proof"
```

### Task 4: Resolve the exact G0-G3 handoff and journal sealed G4

**Files:**
- Create: `scripts/selfloop_supervisor/gates/g4.py`
- Test: `tests/selfloop/test_g4_runner.py`

**Interfaces:**
- Consumes: P09 `development.g0_g3.ready` event digest, `CampaignPolicyService`, `SealedCaseBroker`, P09 `ProtectedPairedGateExecutor`, `SealedSandboxAuditService`, `G4EvidenceBuilder`, and `G4DecisionService`.
- Produces: `G4RunReceipt` and `G4Runner.run(scope, development_ready_event_digest, idempotency_key) -> G4RunReceipt`.
- The runner has no policy, readiness object, evidence booleans, receipt list, case-set ID, or candidate-kind parameter.
- `G4Runner` is created only by the controller's session-bound service factory. Its clean three-argument call surface is not a bypass: every internal phase requests and consumes a capability from that bound context, and recovery must rebind the recorded P05 intent before replay.

- [ ] **Step 1: Write failing exact-handoff, policy-injection, and crash tests**

```python
def test_g4_rejects_readiness_from_other_candidate_or_campaign(g4_harness):
    wrong = g4_harness.development_ready_for(candidate="release-other")
    with pytest.raises(ProofScopeMismatch, match="candidate"):
        g4_harness.runner.run(g4_harness.scope, wrong.event_digest, "g4:run")
    cross_campaign = g4_harness.development_ready_for(campaign="campaign-other")
    with pytest.raises(ProofScopeMismatch, match="campaign"):
        g4_harness.runner.run(g4_harness.scope, cross_campaign.event_digest, "g4:run")

@pytest.mark.parametrize("phase", (
    "intent_committed", "sealed_cases_selected", "raw_pair_event_committed",
    "sandbox_audit_committed", "evidence_committed", "decision_committed",
    "terminal_receipt_committed",
))
def test_g4_resume_reuses_raw_artifacts(g4_harness, phase):
    g4_harness.crash_after(phase)
    with pytest.raises(SimulatedCrash):
        g4_harness.run()
    receipt = g4_harness.restart().run()
    assert receipt.status == "terminal"
    assert g4_harness.sealed_candidate_process_calls <= 1
    assert g4_harness.sealed_champion_process_calls <= 1

def test_g4_runner_cannot_accept_permissive_policy(g4_harness):
    permissive = dataclasses.replace(
        g4_harness.policies.resolve(g4_harness.scope).g4_policy,
        required_quality_gain=-1.0,
    )
    with pytest.raises(TypeError):
        g4_harness.runner.run(
            g4_harness.scope, g4_harness.development_ready.event_digest,
            permissive, "g4:run",
        )

def test_g4_runner_exposes_no_policy_or_evidence_injection_parameter():
    assert tuple(inspect.signature(G4Runner.run).parameters) == (
        "self", "scope", "development_ready_event_digest", "idempotency_key"
    )
```

- [ ] **Step 2: Run the test and confirm the exact G4 runner is absent**

Run: `python3 -m pytest -q tests/selfloop/test_g4_runner.py`

Expected: collection fails because `selfloop_supervisor.gates.g4` does not exist.

- [ ] **Step 3: Implement ledger resolution and phase-complete replay**

```python
class G4Runner:
    def run(self, scope, development_ready_event_digest, idempotency_key):
        if terminal := self.store.resolve_terminal_for_key(scope, idempotency_key):
            return G4RunReceipt.from_event(terminal)
        ready = self.store.resolve_event(
            scope, development_ready_event_digest, "development.g0_g3.ready"
        )
        self.store.verify_development_chain(scope, ready)
        policy = self.policies.resolve(scope)
        require_equal(ready.payload["policyBundleDigest"], policy.policy_bundle_digest)
        require_equal(ready.payload["evaluatorDigest"], policy.evaluator_digest)
        execution_id = sha256_canonical({
            "scope": dataclasses.asdict(scope),
            "developmentReadyEventDigest": ready.digest,
            "policyBundleDigest": policy.policy_bundle_digest,
            "gate": "G4",
        })
        self.store.append_phase(
            scope, "G4", "intent", {"executionId": execution_id,
             "developmentReadyEventDigest": ready.digest}, f"{idempotency_key}:intent",
        )
        cases = self.case_selection.select_and_persist(
            scope, policy.g4_policy.sealed_case_set_id,
            f"{scope.experiment_id}:sealed-order", f"{idempotency_key}:cases",
        )
        raw = self.paired_executor.run_or_resume(
            self.requests.for_g4(scope, ready, policy, cases, execution_id)
        )
        sandbox = self.sandbox_audit.issue(
            scope, execution_id, raw.process_receipt_event_digests,
            f"{idempotency_key}:sandbox-audit",
        )
        evidence = self.evidence.build(
            scope, raw.event_digest, sandbox.event_digest,
            f"{idempotency_key}:evidence",
        )
        decision = self.decisions.decide(
            scope, evidence.event_digest, f"{idempotency_key}:decision"
        )
        receipt = G4RunReceipt.build(
            scope, ready, policy, raw, sandbox, evidence, decision
        )
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "g4.terminal",
            receipt.to_payload(), idempotency_key,
        )
        return G4RunReceipt.from_event(event)
```

`verify_development_chain` resolves all four Plan 9 receipt event digests and its baseline audit, rechecks previous-receipt links, full pairing-base identity, candidate/champion releases, diff, evaluator, supervisor, policy bundle, and spec. `select_and_persist` stores only opaque membership hashes in the campaign ledger; candidates receive one envelope at a time.
`G4RunReceipt.build` hashes and records the development-ready, policy-pin, case-selection, raw-pair, sandbox-audit, evidence, and decision event digests plus exact candidate/champion release, manifest, source-attestation, and P02 release-bundle receipt identities and outcome. Its terminal event payload exposes those source event digests for Plan 11 and C3; it never stores only a decision label.

- [ ] **Step 4: Run handoff, sealed, evidence, decision, and recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_g4_runner.py tests/selfloop/test_sealed_cases.py tests/selfloop/test_g4_evidence.py tests/selfloop/test_lexicographic_decision.py tests/selfloop/test_progressive_gates.py`

Expected: all tests pass; wrong/cross-campaign readiness, policy substitution, unknown releases, zero cases, incomplete pairs, artifact tamper, and every injected crash fail closed or return the original terminal receipt without duplicate processes.

- [ ] **Step 5: Commit exact sealed G4 orchestration**

```bash
git add scripts/selfloop_supervisor/gates/g4.py tests/selfloop/test_g4_runner.py
git commit -m "feat(selfloop): journal exact ledger-backed G4"
```

### Task 5: Verify evaluator repairs and activate them campaign-safely

**Files:**
- Create: `scripts/selfloop_supervisor/evaluator_registry.py`
- Test: `tests/selfloop/test_evaluator_registry.py`

**Interfaces:**
- Consumes: P05 `Ledger`, exact evaluator-repair release event, old-supervisor frozen-test event, adversarial-fixture event, P08 accepted independent-review event, and P09 recomputed champion-baseline event.
- Produces: `EvaluatorRepairEvidenceService.issue(scope, repair_release_event_digest, frozen_test_event_digest, adversarial_event_digest, review_event_digest, idempotency_key)`, `EvaluatorRegistry.accept_repair(scope, evidence_event_digest, idempotency_key)`, `activate_for_generation(scope, registration_event_digest, target_generation_id, baseline_event_digest, idempotency_key)`, `audit(scope, idempotency_key)`, and `rebuild_projection(root_id)`.
- Every mutation includes both root and campaign. The JSON registry is a disposable projection and is never accepted as input.

- [ ] **Step 1: Write failing proof-lookup, campaign, delayed-activation, and projection tests**

```python
def test_repair_acceptance_resolves_real_same_campaign_proofs(evaluator_campaign):
    evidence = evaluator_campaign.issue_repair_evidence()
    registration = evaluator_campaign.registry.accept_repair(
        evaluator_campaign.scope, evidence.event_digest, "evaluator:accept"
    )
    assert registration.evidence_event_digest == evidence.event_digest
    assert registration.accepted_in_generation == evaluator_campaign.scope.generation_id

def test_wrong_type_or_cross_campaign_proof_is_not_accepted(evaluator_campaign):
    wrong_type = evaluator_campaign.ledger.append(
        evaluator_campaign.scope.root_id, evaluator_campaign.scope.campaign_id,
        "unrelated.proof", {"purpose": "negative type test"}, "unrelated:proof",
    )
    with pytest.raises(ProofTypeMismatch, match="evaluator.repair.evidence"):
        evaluator_campaign.registry.accept_repair(
            evaluator_campaign.scope, wrong_type.digest, "evaluator:accept"
        )
    other = evaluator_campaign.issue_repair_evidence(campaign_id="campaign-other")
    with pytest.raises(ProofScopeMismatch, match="campaign"):
        evaluator_campaign.registry.accept_repair(
            evaluator_campaign.scope, other.event_digest, "evaluator:accept-other"
        )

def test_activation_requires_later_generation_and_exact_recomputed_baseline(evaluator_campaign):
    registration = evaluator_campaign.accept_repair()
    baseline = evaluator_campaign.recompute_champion_baseline_for_new_evaluator()
    with pytest.raises(ValueError, match="later generation"):
        evaluator_campaign.registry.activate_for_generation(
            evaluator_campaign.scope, registration.event_digest,
            evaluator_campaign.scope.generation_id, baseline.event_digest,
            "evaluator:activate:same",
        )
    evaluator_campaign.mutate_baseline_evaluator_identity()
    with pytest.raises(StaleGateEvidence, match="baseline evaluator"):
        evaluator_campaign.activate_next_generation(registration, baseline)

def test_projection_tamper_is_rebuilt_from_anchored_ledger(evaluator_campaign):
    accepted = evaluator_campaign.accept_repair()
    evaluator_campaign.write_projection([{"evaluatorVersion": "attacker.v9"}])
    rebuilt = evaluator_campaign.registry.rebuild_projection(evaluator_campaign.scope.root_id)
    assert accepted.event_digest in rebuilt.source_event_digests
    assert "attacker.v9" not in evaluator_campaign.projection_text()
```

- [ ] **Step 2: Run the tests and confirm the verified registry is absent**

Run: `python3 -m pytest -q tests/selfloop/test_evaluator_registry.py`

Expected: collection fails because `selfloop_supervisor.evaluator_registry` does not exist.

- [ ] **Step 3: Implement repair evidence resolution and five-argument ledger appends**

```python
class EvaluatorRegistry:
    def accept_repair(self, scope, evidence_event_digest, idempotency_key):
        evidence = self.proofs.resolve(
            scope, evidence_event_digest, "evaluator.repair.evidence"
        )
        self.proofs.reverify_old_supervisor_sources(scope, evidence)
        payload = {
            "status": "accepted_pending_generation",
            "generationId": scope.generation_id,
            "evaluatorVersion": evidence.payload["evaluatorVersion"],
            "graderBundleSha": evidence.payload["graderBundleSha"],
            "repairReleaseId": evidence.payload["repairReleaseId"],
            "evidenceEventDigest": evidence.digest,
            "frozenTestEventDigest": evidence.payload["frozenTestEventDigest"],
            "adversarialEventDigest": evidence.payload["adversarialEventDigest"],
            "reviewEventDigest": evidence.payload["reviewEventDigest"],
        }
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "evaluator.repair.accepted",
            payload, idempotency_key,
        )
        self.rebuild_projection(scope.root_id)
        return EvaluatorRegistration.from_event(event)

    def activate_for_generation(self, scope, registration_event_digest,
                                target_generation_id, baseline_event_digest,
                                idempotency_key):
        registration = self.proofs.resolve(
            scope, registration_event_digest, "evaluator.repair.accepted"
        )
        require_later_generation(scope, registration, target_generation_id)
        baseline = self.proofs.resolve(
            scope, baseline_event_digest, "baseline.recomputed"
        )
        require_exact_new_evaluator_champion_baseline(registration, baseline)
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "evaluator.activated",
            {"generationId": target_generation_id,
             "evaluatorVersion": registration.payload["evaluatorVersion"],
             "graderBundleSha": registration.payload["graderBundleSha"],
             "registrationEventDigest": registration.digest,
             "baselineEventDigest": baseline.digest},
            idempotency_key,
        )
        self.rebuild_projection(scope.root_id)
        return EvaluatorActivation.from_event(event)
```

`EvaluatorRepairEvidenceService.issue` resolves and validates all four source events under the old pinned supervisor, verifies the repair did not select or generate its own fixtures, then appends `evaluator.repair.evidence` with the five-argument campaign-scoped signature. `audit` verifies the anchor, folds accepted/activated events, verifies their source events, and appends `evaluator.registry.audited` with the examined event digests and active evaluator identity.

- [ ] **Step 4: Run proof, activation, projection, baseline, and ledger tests**

Run: `python3 -m pytest -q tests/selfloop/test_evaluator_registry.py tests/selfloop/test_g2_and_baseline_cache.py tests/selfloop/test_ledger.py`

Expected: all tests pass; fabricated strings, wrong campaign, same-generation activation, wrong evaluator baseline, projection tamper, anchor mismatch, and idempotency conflict fail closed.

- [ ] **Step 5: Commit delayed ledger-backed evaluator evolution**

```bash
git add scripts/selfloop_supervisor/evaluator_registry.py tests/selfloop/test_evaluator_registry.py
git commit -m "feat(selfloop): verify and delay evaluator repairs"
```

### Task 6: Persist hash-linked C3 and validate it against an executable temp root

**Files:**
- Create: `scripts/selfloop_supervisor/gates/c3_conformance.py`
- Modify: `scripts/selfloop_supervisor/conformance.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `commands/selfloop.md`
- Modify: `skills/sips-selfloop/SKILL.md`
- Modify: `scripts/validate_v2.py`
- Test: `tests/selfloop/test_c3_conformance.py`
- Test: `tests/selfloop/test_c3_runtime_integration.py`
- Test: `tests/selfloop/test_adapter_c3.py`

**Interfaces:**
- Consumes: current anchored ledger, unique Plan 9 readiness event, terminal G4 event, real sealed-sandbox audit, baseline-cache audit, evaluator-registry audit, campaign policy pin, pinned supervisor digest, and approved spec digest.
- Produces: `C3ConformanceService.issue(scope, idempotency_key) -> C3ConformanceReceipt`, `C3ConformanceService.verify_existing(scope) -> C3ConformanceReceipt`, `ConformanceRegistry.current_for_scope(scope, loaded_runtime) -> ConformanceReceipt`, and validator CLI `--check-selfloop-c3 --sips-home PATH --root-id ID --campaign-id ID --generation-id ID --experiment-id ID`.
- `issue` accepts no receipt objects or proof digest parameters. It resolves the unique current events, appends `conformance.c3.passed`, and returns that persisted event. `verify_existing` is read-only and rejects later invalidation events.
- CLI, MCP, command, and skill adapters read the same `ConformanceRegistry.current_for_scope` result. They advertise C3 only while `verify_existing` succeeds; a stale C3 immediately downgrades to the latest still-current lower receipt and reports the invalidating event as a blocker.

- [ ] **Step 1: Write failing no-fake-hash, persistence, real-sandbox, and CLI tests**

```python
def test_c3_is_persisted_from_current_ledger_events(real_c3_campaign):
    receipt = real_c3_campaign.conformance.issue(
        real_c3_campaign.scope, "conformance:c3"
    )
    event = real_c3_campaign.ledger.event_by_digest(
        real_c3_campaign.scope.root_id, real_c3_campaign.scope.campaign_id,
        receipt.event_digest,
    )
    assert event.event_type == "conformance.c3.passed"
    assert receipt.g4_event_digest == real_c3_campaign.g4_terminal.event_digest
    assert receipt.sandbox_audit_event_digest == real_c3_campaign.real_sandbox_audit.event_digest
    assert all(real_c3_campaign.ledger_has_event(value) for value in receipt.proof_event_digests)

def test_c3_api_has_no_caller_proof_parameters():
    assert tuple(inspect.signature(C3ConformanceService.issue).parameters) == (
        "self", "scope", "idempotency_key"
    )

def test_fake_sandbox_unit_fixture_cannot_issue_c3(fake_g4_campaign):
    fake_g4_campaign.complete_with_fake_sandbox_status("enforced")
    with pytest.raises(MissingSandboxProof, match="attested process event"):
        fake_g4_campaign.conformance.issue(fake_g4_campaign.scope, "conformance:c3")

def test_validator_executes_against_temp_ledger(real_c3_campaign, repository_root):
    before = real_c3_campaign.validator_command(repository_root)
    assert subprocess.run(before, text=True, capture_output=True).returncode == 1
    real_c3_campaign.conformance.issue(real_c3_campaign.scope, "conformance:c3")
    after = subprocess.run(before, text=True, capture_output=True)
    assert after.returncode == 0
    assert "selfloop C3: verified" in after.stdout

def test_cli_and_mcp_downgrade_together_when_c3_becomes_stale(real_c3_campaign):
    real_c3_campaign.conformance.issue(real_c3_campaign.scope, "conformance:c3")
    cli_before = real_c3_campaign.cli_status()
    mcp_before = real_c3_campaign.mcp_status()
    assert cli_before["conformance"] == mcp_before["conformance"] == "C3"
    invalidation = real_c3_campaign.append_evaluator_activation_without_baseline()
    cli_after = real_c3_campaign.cli_status()
    mcp_after = real_c3_campaign.mcp_status()
    assert cli_after["conformance"] == mcp_after["conformance"] == "C2"
    assert cli_after["blocker"]["eventDigest"] == invalidation.digest
    assert mcp_after["blocker"] == cli_after["blocker"]
```

The `real_c3_campaign` fixture must build a temporary `SIPS_HOME`, open a real P05 ledger, pin actual fixture policy files by computed SHA-256, run P09 G0-G3 services, execute deterministic local candidate/champion programs through the real P03 restricted launcher, run sealed G4, and issue actual baseline/registry/sandbox audits. It must not instantiate `GateReceipt`, `G4RunReceipt`, `SandboxAuditReceipt`, or `C3ConformanceReceipt` directly.

- [ ] **Step 2: Run the tests and confirm executable C3 verification is absent**

Run: `python3 -m pytest -q tests/selfloop/test_c3_conformance.py tests/selfloop/test_c3_runtime_integration.py`

Expected: collection fails because `selfloop_supervisor.gates.c3_conformance` does not exist.

- [ ] **Step 3: Implement current-proof resolution, persistence, and read-only CLI verification**

```python
class C3ConformanceService:
    def issue(self, scope, idempotency_key):
        self.ledger.verify()
        policy = self.policies.resolve(scope)
        development = self.store.resolve_unique_current(
            scope, "development.g0_g3.ready"
        )
        g4 = self.store.resolve_unique_current(scope, "g4.terminal")
        self.store.verify_development_chain(scope, development)
        self.store.verify_g4_chain(scope, development, g4)
        sandbox = self.store.resolve_event(
            scope, g4.payload["sandboxAuditEventDigest"], "sealed.sandbox.audited"
        )
        self.sandbox_attestor.reverify(scope, sandbox)
        baseline = self.store.resolve_event(
            scope, development.payload["baselineAuditEventDigest"],
            "baseline.cache.audited",
        )
        registry = self.registry.audit(scope, f"{idempotency_key}:registry-audit")
        verify_current_policy_evaluator_supervisor_spec(
            scope, policy, development, g4, baseline, registry
        )
        proof_events = (
            *development.payload["gateReceiptEventDigests"], development.digest,
            baseline.digest, g4.payload["rawPairEventDigest"], sandbox.digest,
            g4.payload["caseSelectionEventDigest"],
            g4.payload["evidenceEventDigest"], g4.payload["decisionEventDigest"],
            g4.digest, registry.event_digest, policy.pin_event_digest,
        )
        payload = {
            "schema": "selfloop.conformance.v1", "conformance": "C3",
            "status": "passed", "lastCompletedGate": "G4",
            "generationId": scope.generation_id, "experimentId": scope.experiment_id,
            "candidateReleaseId": scope.candidate_release_id,
            "championReleaseId": scope.champion_release_id,
            "g4Outcome": g4.payload["outcome"],
            "championStays": g4.payload["championStays"],
            "policyBundleDigest": policy.policy_bundle_digest,
            "supervisorDigest": policy.supervisor_digest,
            "specDigest": policy.spec_digest,
            "developmentReadyEventDigest": development.digest,
            "g4EventDigest": g4.digest,
            "sandboxAuditEventDigest": sandbox.digest,
            "baselineAuditEventDigest": baseline.digest,
            "evaluatorRegistryAuditEventDigest": registry.event_digest,
            "proofEventDigests": list(proof_events),
        }
        payload["receiptDigest"] = sha256_canonical(payload)
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "conformance.c3.passed",
            payload, idempotency_key,
        )
        return C3ConformanceReceipt.from_event(event)
```

`verify_existing` verifies the anchor, resolves the unique latest C3 event in the exact campaign, recomputes its receipt digest, resolves and type-checks every proof event, re-verifies all artifacts and real backend attestations, and rejects any later policy/evaluator/supervisor/spec/candidate invalidation. It performs no append.

Extend the P08 `ConformanceRegistry` with one shared adapter path:

```python
class ConformanceRegistry:
    def current_for_scope(self, scope, loaded_runtime):
        try:
            c3 = self.c3.verify_existing(scope)
            require_equal(c3.supervisor_digest, loaded_runtime.supervisor_digest)
            return c3
        except (ProofNotFound, StaleConformance) as error:
            lower = self.current(
                stage="C2", release=loaded_runtime.release_identity,
                policy_digest=scope.policy_bundle_digest,
            )
            return lower.with_blocker(conformance_blocker(error))
        except LedgerCorruption as error:
            return ConformanceStatus.unverified(conformance_blocker(error))
```

`scripts/selfloop_cli.py status` and the v2 `homebase_selfloop` MCP status action must both call the controller's single `current_for_scope` path and serialize the same `conformance`, `proofReceiptDigest`, and `blocker` fields. `commands/selfloop.md` and `skills/sips-selfloop/SKILL.md` document that C3 is receipt-derived and may downgrade after invalidation; they do not inspect source files or policy JSON directly. Preserve frozen v1 adapter bytes.

Modify `scripts/validate_v2.py` so `--check-selfloop-c3` opens the supplied temporary or live `SIPS_HOME`, constructs `GateScope` only from canonical ledger state plus the explicit identity selectors, calls `verify_existing`, prints the verified C3 event/receipt digests, and exits nonzero on absent, stale, fake, corrupt, or cross-campaign proof. Remove the source-file-existence check as a conformance criterion.

- [ ] **Step 4: Run unit, real-sandbox integration, executable validator, and complete Plan 10 gates**

Run:

```bash
python3 -m pytest -q \
  tests/selfloop/test_acceptance_policy.py \
  tests/selfloop/test_sealed_cases.py \
  tests/selfloop/test_paired_statistics.py \
  tests/selfloop/test_g4_evidence.py \
  tests/selfloop/test_lexicographic_decision.py \
  tests/selfloop/test_g4_runner.py \
  tests/selfloop/test_evaluator_registry.py \
  tests/selfloop/test_c3_conformance.py \
  tests/selfloop/test_c3_runtime_integration.py \
  tests/selfloop/test_adapter_c3.py
python3 scripts/validate_v2.py --check-eval
git diff --check
```

Expected: all tests pass on the supported Darwin target; the integration test's temp-root validator exits `1` before persisted C3 and `0` after it; CLI and MCP both advertise C3 while current and both downgrade to C2 with the same blocker after invalidation; `--check-eval` exits `0`; diff check is silent. If the real enforcement backend is unavailable, the C3 integration test and Plan 10 acceptance gate fail closed rather than substituting a fake.

- [ ] **Step 5: Commit executable persisted C3 conformance**

```bash
git add scripts/selfloop_supervisor/gates/c3_conformance.py scripts/selfloop_supervisor/conformance.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py commands/selfloop.md skills/sips-selfloop/SKILL.md scripts/validate_v2.py tests/selfloop/test_c3_conformance.py tests/selfloop/test_c3_runtime_integration.py tests/selfloop/test_adapter_c3.py
git commit -m "feat(selfloop): persist and execute C3 verification"
```

## Plan 10 Completion Gate

- [ ] The campaign policy event pins G4, probation, evaluator, supervisor, and spec digests before G0; G4 cannot accept a caller policy object.
- [ ] G4 resolves the exact same-campaign Plan 9 readiness event and its complete G0-G3/baseline chain.
- [ ] Candidate processes receive no sealed, policy, grader, registry, ledger, or supervisor capability, and every sealed process carries a verified real backend attestation.
- [ ] G4 evidence is derived from raw artifacts, protected graders, protected card classification, authoritative usage, and exact policy; caller booleans and summary fields are rejected.
- [ ] Sealed G4 is phase-journaled and resume reuses process/grant/raw artifacts without duplicate work.
- [ ] Evaluator repairs resolve real old-supervisor, adversarial, review, and baseline events and use campaign-scoped five-argument ledger appends.
- [ ] C3 is a persisted event containing every proof event digest and a recomputable receipt digest; adapters advertise it only after `verify_existing` succeeds.
- [ ] Every P10 mutation runs through a live controller session-bound service and phase capability; unbound, closed-intent, and cross-session calls fail while read-only verification remains available.
- [ ] A real restricted-process temp-root integration and executable validator prove the C3 boundary; fake hashes, fake sandbox status, source existence, and projections cannot pass.
- [ ] Execute the roadmap's **Shared protected-runtime rollover execution task** with `SOURCE_STAGE=P09`, `TARGET_STAGE=P10`, and the exact committed P10 SHA; verify its authorization/pending/activation/rescue/fresh-loader receipt chain before runtime-facing C3 verification is accepted.
