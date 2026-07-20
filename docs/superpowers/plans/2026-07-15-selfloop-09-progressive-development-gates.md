# Selfloop Progressive Development Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement protected, resumable G0-G3 gates whose checks, paired identities, baseline reuse, raw artifacts, and readiness receipt are all derived from and persisted to the campaign-scoped canonical ledger.

**Architecture:** Gate code executes from the pinned immutable supervisor bundle. A campaign-scoped `GateLedger` resolves P08 experiment/release/review evidence, journals every phase with P05's five-argument `Ledger.append`, and binds every receipt to the exact root, campaign, experiment, releases, diff, policy, evaluator, and pairing identity. Champion baselines and raw pair outputs are content-addressed; resume verifies and reuses sealed artifacts instead of repeating model or tool calls.

**Tech Stack:** Python 3.10+, standard-library dataclasses/hashlib/json/random/pathlib, P05 protected SQLite ledger, P03 isolated runtime, P08 committed releases and reviews, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- `scripts/selfloop_supervisor/**` is protected and executes from `${SIPS_HOME}/selfloop/supervisor/bundles/<digest>/`; candidate code cannot construct checks, evidence, receipts, or ledger events.
- After source tests pass, the currently active P08 bundle must TTY-authorize, prepare, and controller-activate the exact P09 release through the roadmap's protected rollover checkpoint. A fresh loader must prove the P09 bundle/module hashes before any runtime-facing G0-G3 or readiness claim; source imports are insufficient.
- Every ledger mutation calls `Ledger.append(root_id, campaign_id, event_type, payload, idempotency_key)` exactly. A root-only append is a type and proof error.
- Every mutating gate/cache/conformance service is created through P05's controller-only session factory with a live `MutationSession`; each intended-action, process, artifact, budget, and terminal append consumes its own operation/resource/phase-scoped `MutationCapability`. Method signatures below may keep that capability on a session-bound service instance rather than repeat it as a caller argument. Constructing an unbound mutator or calling it after intent closure fails; read-only resolution remains capability-free.
- G0 and G1 run for every implemented candidate; G2 requires the exact passed G1 receipt; G3 requires the exact passed G2 receipt.
- G0 covers parse, compile, manifest, dependency lock, changed-path policy, whole-release completeness, promotion authorization, security, permissions, sealed-data denial, and budget instrumentation.
- G1 derives target-failure, hypothesis-specific, critical-regression, and independent-review results through protected runners and ledger lookups. It never accepts caller-authored `CheckReceipt` objects or summary booleans.
- Candidate and champion pairing binds release/manifest/root/code identities, exact source-attestation digests, and path-independent P02 release-bundle receipt digests; model and parameters; evaluator/grader; case set and versions; configuration; dependency environment; permission manifest; case/order/environment/model-seed controls; seed set; and token/time/memory/tool-call budgets. Protected setup reopens both exact `(release_id, source_attestation_digest)` pairs and compares their recomputed receipt digests before launch; a detached identity or ambiguous attestation is ineligible.
- Zero eligible/executed cases, incomplete pairs, missing provenance, unknown loaded release, unbounded or unknown usage, corrupt artifacts, or cross-root/cross-campaign evidence fails closed.
- G2 runs every protected-family stratum below four cases; otherwise it selects `ceil(0.30 * cases)` per family from a recorded deterministic seed. Duplicate case identities are rejected.
- Baseline reuse requires equality of every spec section 13.3 key field plus a verified content-addressed raw baseline artifact. Cache JSON, if emitted, is a disposable projection; ledger events remain authoritative.
- Before every evaluation side effect, append an intended-action event. Seal each process/usage/artifact receipt before the next phase. Resume verifies candidate commit, release manifest, budget ledger, prior gate, and artifact hashes, then starts only the first incomplete phase.
- This plan persists `development.g0_g3.ready` with conformance `C2`. It does not advertise C3; Plan 10 must resolve this exact event and prove sealed G4.
- Tests use temporary roots and deterministic fake paired processes. They may prove orchestration, but no fake runner or hash-shaped string can create a readiness event without ledger-resolved source receipts.

---

### Task 1: Define exact gate identities and a campaign-scoped proof store

**Files:**
- Modify: `scripts/selfloop_supervisor/ledger.py`
- Create: `scripts/selfloop_supervisor/gates/__init__.py`
- Create: `scripts/selfloop_supervisor/gates/types.py`
- Create: `scripts/selfloop_supervisor/gates/store.py`
- Test: `tests/selfloop/test_gate_store.py`

**Interfaces:**
- Consumes: P05 `Ledger.append(root_id, campaign_id, event_type, payload, idempotency_key)`, `MutationSession`, controller-issued `MutationCapability`, and verified anchored head.
- Produces: `Ledger.event_by_digest(root_id: str, campaign_id: str, digest: str) -> EventRecord`, `GateScope`, `PairingIdentity`, `CheckReceipt`, `GateReceipt`, `RawArtifactManifest`, and `GateLedger.resolve_event/append_phase/commit_receipt`.
- `GateScope` is the only caller-visible identity input. `GateLedger` rejects an event whose root, campaign, generation, experiment, candidate, champion, or policy bundle differs from the scope.
- `GateLedger.for_session(ledger, artifacts, mutation_context)` is the only mutating constructor. It validates the open P05 intent before every call and privately issues/consumes the phase capability; `GateLedger.read_only(...)` exposes only resolver methods.

- [ ] **Step 1: Write failing campaign-isolation and digest-binding tests**

```python
def test_gate_receipt_digest_changes_with_candidate_or_campaign(gate_scope, pairing_identity):
    first = GateReceipt.build(gate_scope, GateName.G0, pairing_identity, checks=passing_checks())
    other_candidate = dataclasses.replace(gate_scope, candidate_release_id="release-b")
    other_campaign = dataclasses.replace(gate_scope, campaign_id="campaign-b")
    assert first.receipt_digest != GateReceipt.build(
        other_candidate, GateName.G0, pairing_identity, checks=passing_checks()
    ).receipt_digest
    assert first.receipt_digest != GateReceipt.build(
        other_campaign, GateName.G0, pairing_identity, checks=passing_checks()
    ).receipt_digest

def test_gate_store_never_resolves_cross_campaign_event(
    tmp_path, gate_scope, pairing_identity, gate_mutation_context,
):
    ledger = Ledger.open(tmp_path)
    store = GateLedger.for_session(
        ledger, tmp_path / "artifacts", gate_mutation_context,
    )
    receipt = GateReceipt.build(gate_scope, GateName.G0, pairing_identity, passing_checks())
    committed = store.commit_receipt(gate_scope, receipt, "experiment-a:G0:receipt")
    wrong = dataclasses.replace(gate_scope, campaign_id="campaign-b")
    with pytest.raises(ProofScopeMismatch, match="campaign"):
        store.resolve_event(wrong, committed.event_digest, "gate.receipt")

def test_campaign_id_is_passed_to_p05_append(
    recording_ledger, gate_scope, tmp_path, gate_mutation_context,
):
    store = GateLedger.for_session(
        recording_ledger, tmp_path / "artifacts", gate_mutation_context,
    )
    store.append_phase(gate_scope, "G0", "intent", {"requestDigest": digest("request")}, "g0:intent")
    call = recording_ledger.append_calls[0]
    assert call[:3] == (gate_scope.root_id, gate_scope.campaign_id, "gate.phase")
    assert call[4] == "g0:intent"

def test_unbound_or_closed_session_cannot_mutate_gate_store(
    ledger, artifacts, gate_scope, closed_mutation_context,
):
    with pytest.raises(MutationDenied, match="controller mutation session required"):
        GateLedger(ledger, artifacts).append_phase(
            gate_scope, "G0", "intent", {}, "g0:unbound",
        )
    bound = GateLedger.for_session(ledger, artifacts, closed_mutation_context)
    with pytest.raises(MutationDenied, match="intent is not open"):
        bound.append_phase(gate_scope, "G0", "intent", {}, "g0:closed")
```

- [ ] **Step 2: Run the focused test and verify the missing contracts**

Run: `python3 -m pytest -q tests/selfloop/test_gate_store.py`

Expected: collection fails because `selfloop_supervisor.gates.store` does not exist.

- [ ] **Step 3: Implement canonical identities, full-envelope hashes, and scoped ledger lookup**

```python
# scripts/selfloop_supervisor/gates/types.py
import dataclasses
from dataclasses import dataclass
from enum import Enum

class GateName(str, Enum):
    G0 = "G0"
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"

class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    OPEN = "open"
    INCONCLUSIVE = "inconclusive"

@dataclass(frozen=True)
class GateScope:
    root_id: str
    campaign_id: str
    generation_id: str
    experiment_id: str
    candidate_release_id: str
    champion_release_id: str
    candidate_diff_hash: str
    builder_id: str
    policy_bundle_digest: str
    supervisor_digest: str

@dataclass(frozen=True)
class PairingIdentity:
    candidate_release_id: str
    candidate_manifest_digest: str
    candidate_source_attestation_digest: str
    candidate_release_bundle_receipt_digest: str
    candidate_root_digest: str
    candidate_code_sha: str
    champion_release_id: str
    champion_manifest_digest: str
    champion_source_attestation_digest: str
    champion_release_bundle_receipt_digest: str
    champion_root_digest: str
    champion_code_sha: str
    model_id: str
    model_parameters_digest: str
    evaluator_version: str
    grader_bundle_sha: str
    case_set_version: str
    case_versions_digest: str
    configuration_digest: str
    dependency_environment_digest: str
    permission_manifest_digest: str
    case_seed: str
    order_seed: str
    environment_seed: str
    seed_set_digest: str
    model_seed_control: str
    model_seed: str | None
    resource_budget_policy_digest: str
    token_cap: int
    time_cap_ms: int
    memory_cap_bytes: int
    tool_call_cap: int

    def digest(self) -> str:
        return sha256_canonical(dataclasses.asdict(self))

    def base_digest(self) -> str:
        values = dataclasses.asdict(self)
        for field in (
            "case_set_version", "case_versions_digest", "case_seed", "order_seed",
            "environment_seed", "seed_set_digest", "model_seed_control", "model_seed",
        ):
            values.pop(field)
        return sha256_canonical(values)

@dataclass(frozen=True)
class CheckReceipt:
    check_id: str
    status: str
    producer_receipt_digest: str
    raw_artifact_digest: str
    detail_digest: str

@dataclass(frozen=True)
class GateReceipt:
    schema: str
    scope: GateScope
    gate: GateName
    status: GateStatus
    pairing_identity: PairingIdentity
    checks: tuple[CheckReceipt, ...]
    eligible_cases: int
    executed_cases: int
    raw_artifact_manifest_digest: str
    previous_gate_receipt_digest: str | None
    receipt_digest: str
    event_digest: str | None = None

    @classmethod
    def build(cls, scope, gate, pairing_identity, checks, eligible_cases=0,
              executed_cases=0, raw_artifact_manifest_digest="",
              previous_gate_receipt_digest=None):
        status = GateStatus.PASSED if checks and all(row.status == "passed" for row in checks) else GateStatus.FAILED
        body = {
            "schema": "selfloop.gate-receipt.v1", "scope": dataclasses.asdict(scope),
            "gate": gate.value, "status": status.value,
            "pairingIdentity": dataclasses.asdict(pairing_identity),
            "checks": [dataclasses.asdict(row) for row in checks],
            "eligibleCases": eligible_cases, "executedCases": executed_cases,
            "rawArtifactManifestDigest": raw_artifact_manifest_digest,
            "previousGateReceiptDigest": previous_gate_receipt_digest,
        }
        return cls(
            schema=body["schema"], scope=scope, gate=gate, status=status,
            pairing_identity=pairing_identity, checks=tuple(checks),
            eligible_cases=eligible_cases, executed_cases=executed_cases,
            raw_artifact_manifest_digest=raw_artifact_manifest_digest,
            previous_gate_receipt_digest=previous_gate_receipt_digest,
            receipt_digest=sha256_canonical(body),
            event_digest=None,
        )

    def to_payload(self):
        return {
            "schema": self.schema, "scope": dataclasses.asdict(self.scope),
            "gate": self.gate.value, "status": self.status.value,
            "pairingIdentity": dataclasses.asdict(self.pairing_identity),
            "checks": [dataclasses.asdict(row) for row in self.checks],
            "eligibleCases": self.eligible_cases, "executedCases": self.executed_cases,
            "rawArtifactManifestDigest": self.raw_artifact_manifest_digest,
            "previousGateReceiptDigest": self.previous_gate_receipt_digest,
            "receiptDigest": self.receipt_digest,
        }

    def recompute_digest(self):
        payload = self.to_payload()
        payload.pop("receiptDigest")
        return sha256_canonical(payload)
```

Add `Ledger.event_by_digest(root_id, campaign_id, digest)` as a read-only anchored-ledger query. It verifies the chain and external head first, then filters by all three arguments; it never searches another campaign as a fallback.

```python
# scripts/selfloop_supervisor/gates/store.py
class GateLedger:
    def append_phase(self, scope, gate, phase, payload, idempotency_key):
        return self.ledger.append(
            scope.root_id, scope.campaign_id, "gate.phase",
            {"generationId": scope.generation_id, "experimentId": scope.experiment_id,
             "candidateReleaseId": scope.candidate_release_id,
             "championReleaseId": scope.champion_release_id,
             "gate": gate, "phase": phase, **payload},
            idempotency_key,
        )

    def resolve_event(self, scope, digest, expected_type):
        row = self.ledger.event_by_digest(scope.root_id, scope.campaign_id, digest)
        require_event_scope(row, scope)
        if row.event_type != expected_type:
            raise ProofTypeMismatch(f"expected {expected_type}, got {row.event_type}")
        return row

    def commit_receipt(self, scope, receipt, idempotency_key):
        if receipt.scope != scope or receipt.receipt_digest != receipt.recompute_digest():
            raise ProofScopeMismatch("gate receipt envelope mismatch")
        return self.ledger.append(
            scope.root_id, scope.campaign_id, "gate.receipt",
            {"generationId": scope.generation_id, "experimentId": scope.experiment_id,
             "candidateReleaseId": scope.candidate_release_id,
             "championReleaseId": scope.champion_release_id,
             "gate": receipt.gate.value, "receiptDigest": receipt.receipt_digest,
             "receipt": receipt.to_payload()}, idempotency_key,
        )

    def commit_raw_pair(self, scope, gate, execution_id, manifest, usage_digests,
                        idempotency_key):
        return self.ledger.append(
            scope.root_id, scope.campaign_id, "gate.raw_pair.sealed",
            {"generationId": scope.generation_id,
             "experimentId": scope.experiment_id,
             "candidateReleaseId": scope.candidate_release_id,
             "championReleaseId": scope.champion_release_id,
             "gate": gate, "executionId": execution_id,
             "manifestDigest": manifest.digest,
             "requestDigest": manifest.request_digest,
             "pairingIdentityDigest": manifest.pairing_identity_digest,
             "caseMembershipDigest": manifest.case_membership_digest,
             "usageReceiptEventDigests": list(usage_digests)},
            idempotency_key,
        )
```

Export all public contracts from `gates/__init__.py`. Reject empty identity fields, nonpositive caps, a model-seed value when control is `unavailable`, and absent receipt/artifact digests.
`GateLedger.resolve_gate_receipt` reconstructs the payload, recomputes `receipt_digest`, and returns `dataclasses.replace(receipt, event_digest=event.digest)`; the ledger event digest is never included in the inner receipt hash.

- [ ] **Step 4: Run identity, campaign-scope, anchor, and tamper tests**

Run: `python3 -m pytest -q tests/selfloop/test_gate_store.py tests/selfloop/test_ledger.py`

Expected: all tests pass; wrong-root, wrong-campaign, altered-context, altered-receipt, and anchored-head cases fail closed.

- [ ] **Step 5: Commit the exact gate proof boundary**

```bash
git add scripts/selfloop_supervisor/ledger.py scripts/selfloop_supervisor/gates/__init__.py scripts/selfloop_supervisor/gates/types.py scripts/selfloop_supervisor/gates/store.py tests/selfloop/test_gate_store.py
git commit -m "feat(selfloop): bind gate receipts to campaign evidence"
```

### Task 2: Derive G0-G1 evidence through protected check runners

**Files:**
- Create: `scripts/selfloop_supervisor/gates/checks.py`
- Create: `scripts/selfloop_supervisor/gates/evidence.py`
- Create: `scripts/selfloop_supervisor/gates/g0_g1.py`
- Test: `tests/selfloop/test_g0_g1.py`

**Interfaces:**
- Consumes: P08 terminal experiment/release/review-acceptance event digests, including candidate/champion release IDs, source-attestation digests, and release-bundle receipt digests; P02 `ReleaseBundleStore.open_verified`; P08 `classify_changed_paths`; P03 runtime receipts; and `GateLedger`.
- Produces: `ProtectedCheckRunner.run(check_id: str, request: ProtectedCheckRequest) -> CheckReceipt`, `GateEvidenceBuilder.build_g0(scope)`, `GateEvidenceBuilder.build_g1(scope, g0_receipt_digest)`, `run_g0(scope, evidence_builder, idempotency_key)`, and `run_g1(scope, g0_receipt_digest, evidence_builder, idempotency_key)`.
- Neither public gate function accepts changed paths, provenance mappings, check receipts, pass/fail booleans, or reviewer objects. Those are resolved from exact P08 ledger events.

- [ ] **Step 1: Write failing substitution, missing-check, and stale-review tests**

```python
def test_g0_reads_changed_paths_from_exact_experiment_event(gate_harness):
    gate_harness.commit_candidate(changed_paths=("scripts/selfloop_supervisor/kernel.py",))
    with pytest.raises(CandidatePolicyDenied, match="protected path"):
        gate_harness.run_g0()
    assert "changed_paths" not in inspect.signature(run_g0).parameters

def test_caller_cannot_submit_passing_check_receipts():
    assert tuple(inspect.signature(run_g1).parameters) == (
        "scope", "g0_receipt_digest", "evidence_builder", "idempotency_key"
    )

def test_g0_requires_every_normative_protected_check(gate_harness):
    gate_harness.check_runner.remove("dependency_lock")
    with pytest.raises(MissingProtectedCheck, match="dependency_lock"):
        gate_harness.run_g0()

def test_g1_rejects_review_for_prior_diff(gate_harness):
    stale = gate_harness.accept_review_for_current_diff()
    gate_harness.commit_repair_after_review()
    gate_harness.attach_review_acceptance_to_release(stale.event_digest)
    with pytest.raises(ReviewRequired, match=gate_harness.current_diff_hash):
        gate_harness.run_g1()

@pytest.mark.parametrize("subject", ("candidate", "champion"))
def test_gate_rejects_changed_source_attestation_or_bundle_receipt(
    gate_harness, subject,
):
    gate_harness.replace_registered_attestation(subject)
    with pytest.raises(ProofScopeMismatch, match="release bundle receipt changed"):
        gate_harness.run_g0()
```

- [ ] **Step 2: Run the tests and confirm protected evidence does not exist**

Run: `python3 -m pytest -q tests/selfloop/test_g0_g1.py`

Expected: collection fails because `selfloop_supervisor.gates.evidence` does not exist.

- [ ] **Step 3: Implement the fixed check registry and ledger-derived evidence**

```python
# scripts/selfloop_supervisor/gates/checks.py
G0_CHECK_IDS = (
    "parse", "compile", "manifest", "dependency_lock", "changed_path_policy",
    "release_completeness", "promotion_authorization", "security",
    "permissions", "sealed_data_denial", "budget_instrumentation",
)
G1_CHECK_IDS = (
    "target_failure", "hypothesis_specific", "critical_regressions", "independent_review",
)

class ProtectedCheckRunner:
    def run(self, check_id, request):
        implementation = self.registry.get(check_id)
        if implementation is None:
            raise MissingProtectedCheck(check_id)
        result = implementation(request)
        if result.producer != "pinned-supervisor" or not result.raw_artifact_digest:
            raise UntrustedCheckResult(check_id)
        return CheckReceipt(
            check_id=check_id, status="passed" if result.passed else "failed",
            producer_receipt_digest=result.producer_receipt_digest,
            raw_artifact_digest=result.raw_artifact_digest,
            detail_digest=sha256_canonical(result.detail),
        )
```

```python
# scripts/selfloop_supervisor/gates/evidence.py
class GateEvidenceBuilder:
    def _source(self, scope):
        experiment = self.store.resolve_exact_experiment(scope)
        release = self.store.resolve_release(scope, experiment.payload["releaseReceiptDigest"])
        candidate_bundle = self.release_bundles.open_verified(
            release.payload["releaseId"], release.payload["sourceAttestationDigest"],
        )
        if candidate_bundle.receipt_digest != release.payload["releaseBundleReceiptDigest"]:
            raise ProofScopeMismatch("candidate release bundle receipt changed")
        champion_record = self.store.resolve_stable_champion(scope)
        champion_bundle = self.release_bundles.open_verified(
            champion_record.payload["releaseId"],
            champion_record.payload["sourceAttestationDigest"],
        )
        if champion_bundle.receipt_digest != champion_record.payload["releaseBundleReceiptDigest"]:
            raise ProofScopeMismatch("champion release bundle receipt changed")
        provenance = self.store.resolve_runtime_receipt(
            scope, experiment.payload["foundationRuntimeReceiptDigest"]
        )
        if release.payload["diffHash"] != scope.candidate_diff_hash:
            raise ProofScopeMismatch("candidate diff changed after experiment receipt")
        return experiment, release, candidate_bundle, champion_bundle, provenance

    def build_g0(self, scope):
        experiment, release, candidate, champion, provenance = self._source(scope)
        request = ProtectedCheckRequest.from_events(
            scope, experiment, release, candidate, champion, provenance,
        )
        checks = tuple(self.runner.run(check_id, request) for check_id in G0_CHECK_IDS)
        return GateReceipt.build(scope, GateName.G0, request.pairing_identity, checks)

    def build_g1(self, scope, g0_receipt_digest):
        g0 = self.store.resolve_gate_receipt(scope, g0_receipt_digest, GateName.G0)
        experiment, release, candidate, champion, provenance = self._source(scope)
        review = self.store.resolve_required_review(scope, release.payload["reviewAcceptanceDigest"])
        request = ProtectedCheckRequest.from_events(
            scope, experiment, release, candidate, champion, provenance,
            review=review,
        )
        checks = tuple(self.runner.run(check_id, request) for check_id in G1_CHECK_IDS)
        return GateReceipt.build(
            scope, GateName.G1, request.pairing_identity, checks,
            previous_gate_receipt_digest=g0.receipt_digest,
        )
```

`ProtectedCheckRequest.from_events` derives the complete `PairingIdentity` from the two reopened `ReleaseBundleReceipt` values plus ledger-backed runtime/policy identities; it never trusts a receipt object, path, or pairing supplied by a caller. `resolve_required_review` invokes P08 `ReviewRegistry.verify` against the current diff, builder ID, independent reviewer identity, and separate protected grant, then verifies the accepted-review event belongs to the same root and campaign. Missing review is permitted only when the protected path classifier says it is not required.

`run_g0` and `run_g1` call the builder, persist the resulting receipt with `GateLedger.commit_receipt`, and return the persisted receipt. Failed gates are still terminal evidence and use their own idempotency key.

- [ ] **Step 4: Run G0/G1 and P08 review integration tests**

Run: `python3 -m pytest -q tests/selfloop/test_g0_g1.py tests/selfloop/test_experiment_review.py tests/selfloop/test_runtime_isolation.py`

Expected: all tests pass; safe-path substitution, caller booleans, missing checks, stale review, wrong campaign, and incomplete runtime provenance fail closed.

- [ ] **Step 5: Commit protected G0-G1 derivation**

```bash
git add scripts/selfloop_supervisor/gates/checks.py scripts/selfloop_supervisor/gates/evidence.py scripts/selfloop_supervisor/gates/g0_g1.py tests/selfloop/test_g0_g1.py
git commit -m "feat(selfloop): derive G0 G1 evidence in supervisor"
```

### Task 3: Persist deterministic G2 membership and authoritative baseline cache entries

**Files:**
- Create: `scripts/selfloop_supervisor/gates/g2.py`
- Create: `scripts/selfloop_supervisor/gates/baseline_cache.py`
- Test: `tests/selfloop/test_g2_and_baseline_cache.py`

**Interfaces:**
- Produces: `DevelopmentCase`, `G2SelectionReceipt`, `select_g2_cases`, `BaselineCacheKey`, `BaselineCache.lookup/store/audit`.
- `BaselineCache.store(scope, key, manifest, idempotency_key)` appends `baseline.cached` with both root and campaign. `lookup` resolves the event in the same campaign, verifies every key field and every content hash, and never imports a JSON projection into authority.

- [ ] **Step 1: Write failing deterministic, duplicate, corruption, and campaign tests**

```python
def test_g2_is_deterministic_and_rejects_duplicate_identity(cases):
    assert select_g2_cases(cases, "generation-7:seed") == select_g2_cases(
        tuple(reversed(cases)), "generation-7:seed"
    )
    with pytest.raises(ValueError, match="duplicate development case"):
        select_g2_cases((*cases, cases[0]), "generation-7:seed")

@pytest.mark.parametrize("field", tuple(BaselineCacheKey.__dataclass_fields__))
def test_cache_misses_when_any_field_changes(cache, cache_scope, baseline_key, manifest, field):
    cache.store(cache_scope, baseline_key, manifest, "baseline:store")
    changed = dataclasses.replace(
        baseline_key, **{field: changed_value(getattr(baseline_key, field))}
    )
    assert cache.lookup(cache_scope, changed) is None

def test_cache_rejects_corrupt_artifact_and_cross_campaign(cache_harness):
    stored = cache_harness.store_real_manifest()
    cache_harness.mutate_artifact(stored.manifest_digest)
    with pytest.raises(ArtifactCorruption):
        cache_harness.lookup_current()
    with pytest.raises(ProofScopeMismatch):
        cache_harness.lookup_from_campaign("campaign-other")
```

- [ ] **Step 2: Run the tests and verify the cache boundary is absent**

Run: `python3 -m pytest -q tests/selfloop/test_g2_and_baseline_cache.py`

Expected: collection fails because `selfloop_supervisor.gates.baseline_cache` does not exist.

- [ ] **Step 3: Implement deterministic membership and ledger-indexed artifacts**

```python
@dataclass(frozen=True, order=True)
class DevelopmentCase:
    case_id: str
    case_version: int
    family: str

def select_g2_cases(cases, seed):
    identities = [(row.case_id, row.case_version) for row in cases]
    if not identities:
        raise ValueError("G2 requires eligible cases")
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate development case identity")
    selected = []
    for family in sorted({row.family for row in cases}):
        rows = sorted(row for row in cases if row.family == family)
        count = len(rows) if len(rows) < 4 else math.ceil(0.30 * len(rows))
        family_seed = int.from_bytes(
            hashlib.sha256(f"{seed}:{family}".encode()).digest()[:8], "big"
        )
        selected.extend(random.Random(family_seed).sample(rows, count))
    return tuple(sorted(selected))

@dataclass(frozen=True)
class BaselineCacheKey:
    champion_release_id: str
    champion_manifest_digest: str
    champion_source_attestation_digest: str
    champion_release_bundle_receipt_digest: str
    champion_root_digest: str
    model_id: str
    model_parameters_digest: str
    case_set_version: str
    case_versions_digest: str
    evaluator_version: str
    grader_bundle_sha: str
    configuration_digest: str
    permission_manifest_digest: str
    dependency_environment_digest: str
    seed_set_digest: str
    resource_budget_policy_digest: str

    def digest(self):
        values = dataclasses.asdict(self)
        if any(value in (None, "") for value in values.values()):
            raise ValueError("baseline cache key fields must be nonempty")
        return sha256_canonical(values)
```

`BaselineCache.store` first seals the raw baseline manifest under `${SIPS_HOME}/selfloop/roots/<root-id>/runs/artifacts/sha256/<digest>`, verifies every row/process/usage hash, then calls:

```python
self.ledger.append(
    scope.root_id, scope.campaign_id, "baseline.cached",
    {"experimentId": scope.experiment_id, "key": dataclasses.asdict(key),
     "keyDigest": key.digest(), "manifestDigest": manifest.digest,
     "artifactDigests": list(manifest.artifact_digests)},
    idempotency_key,
)
```

`audit` folds only verified `baseline.cached` events for the campaign, rehashes their manifests, and appends a `baseline.cache.audited` event containing the examined event digests. It does not accept a caller-provided audit digest.

- [ ] **Step 4: Run selection, cache, artifact, and ledger tests**

Run: `python3 -m pytest -q tests/selfloop/test_g2_and_baseline_cache.py tests/selfloop/test_gate_store.py`

Expected: all tests pass; every key-field change misses, corruption fails, and the audit names only verified same-campaign entries.

- [ ] **Step 5: Commit deterministic selection and authoritative baseline reuse**

```bash
git add scripts/selfloop_supervisor/gates/g2.py scripts/selfloop_supervisor/gates/baseline_cache.py tests/selfloop/test_g2_and_baseline_cache.py
git commit -m "feat(selfloop): persist exact development baselines"
```

### Task 4: Run phase-journaled paired G2-G3 with raw artifact reuse

**Files:**
- Create: `scripts/selfloop_supervisor/gates/progressive.py`
- Create: `scripts/selfloop_supervisor/gates/recovery.py`
- Test: `tests/selfloop/test_progressive_gates.py`

**Interfaces:**
- Consumes: `GateLedger`, `BaselineCache`, P03 paired runtime, P05 budget/grant ledger, and exact prior `GateReceipt` digest.
- Produces: `PairExecutionRequest`, `RawPairArtifact`, `ProtectedPairedGateExecutor.run_or_resume`, `GateRecoveryVerifier.verify`, and `ProgressiveGateRunner.run_g2/run_g3`.
- `run_g2(scope, g1_receipt_digest, cases, selection_seed, idempotency_key)` and `run_g3(scope, g2_receipt_digest, cases, idempotency_key)` accept receipt digests, not receipt objects.

- [ ] **Step 1: Write failing crash-phase and full-identity tests**

```python
@pytest.mark.parametrize("phase", (
    "intent_committed", "champion_artifact_sealed", "candidate_artifact_sealed",
    "raw_pair_event_committed", "evidence_built", "gate_receipt_committed",
))
def test_resume_reuses_sealed_process_artifacts(progressive_fakes, phase):
    progressive_fakes.crash_after(phase)
    with pytest.raises(SimulatedCrash):
        progressive_fakes.run_g2()
    resumed = progressive_fakes.restart().run_g2()
    assert resumed.status == GateStatus.PASSED
    assert progressive_fakes.process_calls("champion") <= 1
    assert progressive_fakes.process_calls("candidate") <= 1

def test_pair_fails_when_any_runtime_identity_differs(progressive_fakes):
    progressive_fakes.candidate_result.permission_manifest_digest = digest("other")
    with pytest.raises(PairingIdentityMismatch, match="permission_manifest_digest"):
        progressive_fakes.run_g2()

def test_resume_rejects_changed_commit_budget_or_prior_gate(progressive_fakes):
    progressive_fakes.crash_after("raw_pair_event_committed")
    with pytest.raises(SimulatedCrash):
        progressive_fakes.run_g2()
    progressive_fakes.replace_candidate_commit()
    with pytest.raises(RecoveryMismatch, match="candidate commit"):
        progressive_fakes.restart().run_g2()
```

- [ ] **Step 2: Run the tests and confirm the resumable executor is absent**

Run: `python3 -m pytest -q tests/selfloop/test_progressive_gates.py`

Expected: collection fails because `selfloop_supervisor.gates.progressive` does not exist.

- [ ] **Step 3: Implement intended-action phases, deterministic execution IDs, and replay**

```python
@dataclass(frozen=True)
class PairExecutionRequest:
    scope: GateScope
    gate: GateName
    pairing_identity: PairingIdentity
    case_membership_digest: str
    previous_gate_receipt_digest: str
    baseline_key: BaselineCacheKey

    @property
    def execution_id(self):
        return sha256_canonical(dataclasses.asdict(self))

    @property
    def baseline_key_digest(self):
        return self.baseline_key.digest()

class ProtectedPairedGateExecutor:
    def run_or_resume(self, request):
        self.recovery.verify(request)
        self.store.append_phase(
            request.scope, request.gate.value, "intent",
            {"executionId": request.execution_id,
             "requestDigest": sha256_canonical(dataclasses.asdict(request))},
            f"{request.execution_id}:intent",
        )
        if sealed := self.store.resolve_raw_pair_for_execution(request.scope, request.execution_id):
            return self.artifacts.load_and_verify(sealed.payload["manifestDigest"], request)
        champion = self.baselines.lookup(request.scope, request.baseline_key)
        if champion is None:
            champion = self.runtime.run_side_or_resume(request, "champion")
            self.artifacts.seal_side(champion, request)
            self.baselines.store_from_execution(request.scope, request, champion)
        candidate = self.runtime.run_side_or_resume(request, "candidate")
        self.artifacts.seal_side(candidate, request)
        raw_pair = RawPairArtifact.build_and_verify(request, champion, candidate)
        manifest = self.artifacts.seal_pair(raw_pair)
        self.store.commit_raw_pair(
            request.scope, request.gate.value, request.execution_id, manifest,
            (candidate.usage_receipt_event_digest, champion.usage_receipt_event_digest),
            f"{request.execution_id}:raw-pair",
        )
        return raw_pair
```

`run_side_or_resume` writes a deterministic per-side result path before launch, appends a side intent with the exact grant digest, reconciles the P05 grant after completion or failure, atomically seals the process/usage/raw-result manifest, then appends the side-completed event. If a crash occurs after launch but before sealing, recovery uses the process tracker and reserved grant; it never issues a second grant or repeats an already reconciled call.

`ProgressiveGateRunner` resolves the exact prior gate event, constructs the full pairing identity from protected runtime plans, obtains G2 membership from the persisted selection receipt or the complete sorted G3 suite, calls `run_or_resume`, derives checks from raw artifacts, and commits one `gate.receipt`. It rejects zero cases, missing protected families, incomplete pairs, unknown loaded release, sandbox status other than `enforced`, and any unknown usage field.

- [ ] **Step 4: Run phase, cache, pairing, grant, and recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_progressive_gates.py tests/selfloop/test_g2_and_baseline_cache.py tests/selfloop/test_budget.py tests/selfloop/test_runtime_isolation.py`

Expected: all tests pass; every injected restart returns the original terminal receipt, sealed raw artifacts are reused, and no side runs more than once.

- [ ] **Step 5: Commit resumable paired G2-G3**

```bash
git add scripts/selfloop_supervisor/gates/progressive.py scripts/selfloop_supervisor/gates/recovery.py tests/selfloop/test_progressive_gates.py
git commit -m "feat(selfloop): journal and resume paired development gates"
```

### Task 5: Persist ledger-verified G0-G3 readiness without a C3 claim

**Files:**
- Create: `scripts/selfloop_supervisor/gates/development_conformance.py`
- Modify: `scripts/validate_v2.py`
- Test: `tests/selfloop/test_development_conformance.py`

**Interfaces:**
- Consumes: `GateLedger`, current pinned supervisor/policy/spec events, and exact `GateScope`.
- Produces: `DevelopmentGateReceipt` and `DevelopmentConformanceService.issue(scope, idempotency_key) -> DevelopmentGateReceipt` for Plan 10.
- `issue` accepts no receipt sequence or digest strings. It queries the canonical ledger for the unique current G0-G3 chain and appends `development.g0_g3.ready` with the campaign-scoped P05 signature.

- [ ] **Step 1: Write failing ledger-chain, stale-proof, and no-overclaim tests**

```python
def test_readiness_is_built_from_unique_ledger_chain(development_campaign):
    receipt = development_campaign.conformance.issue(
        development_campaign.scope, "experiment-a:development-ready"
    )
    assert receipt.status == "g0_g3_ready"
    assert receipt.conformance == "C2"
    assert receipt.gate_receipt_digests == development_campaign.persisted_gate_digests

def test_readiness_rejects_receipt_from_other_campaign(development_campaign):
    development_campaign.replace_g3_with_other_campaign_event()
    with pytest.raises(ProofScopeMismatch, match="campaign"):
        development_campaign.conformance.issue(
            development_campaign.scope, "experiment-a:development-ready"
        )

def test_readiness_rejects_changed_policy_evaluator_or_candidate(development_campaign):
    development_campaign.advance_evaluator_without_recomputing_baseline()
    with pytest.raises(StaleGateEvidence, match="evaluator"):
        development_campaign.conformance.issue(
            development_campaign.scope, "experiment-a:development-ready"
        )
```

- [ ] **Step 2: Run the test and verify the conformance service is absent**

Run: `python3 -m pytest -q tests/selfloop/test_development_conformance.py`

Expected: collection fails because `selfloop_supervisor.gates.development_conformance` does not exist.

- [ ] **Step 3: Implement canonical chain resolution and persistence**

```python
class DevelopmentConformanceService:
    def issue(self, scope, idempotency_key):
        self.ledger.verify()
        gates = self.store.resolve_unique_gate_chain(scope, ("G0", "G1", "G2", "G3"))
        if [row.status for row in gates] != ["passed", "passed", "passed", "passed"]:
            raise IncompleteGateChain("ordered passed G0-G3 required")
        verify_linked_previous_digests(gates)
        verify_common_scope_and_pairing_base(scope, gates)
        policy = self.store.resolve_current_policy_pin(scope)
        evaluator = self.store.resolve_current_evaluator(scope)
        baseline_audit = self.baselines.audit(
            scope, gates[-1].pairing_identity.base_digest(),
            f"{idempotency_key}:baseline-audit",
        )
        payload = {
            "schema": "selfloop.development-gates.v1", "status": "g0_g3_ready",
            "conformance": "C2", "lastCompletedGate": "G3",
            "generationId": scope.generation_id, "experimentId": scope.experiment_id,
            "candidateReleaseId": scope.candidate_release_id,
            "championReleaseId": scope.champion_release_id,
            "candidateDiffHash": scope.candidate_diff_hash,
            "policyBundleDigest": policy.payload["policyBundleDigest"],
            "evaluatorDigest": evaluator.payload["evaluatorDigest"],
            "supervisorDigest": scope.supervisor_digest,
            "specDigest": SPEC_DIGEST,
            "gateReceiptDigests": [row.receipt_digest for row in gates],
            "gateReceiptEventDigests": [row.event_digest for row in gates],
            "baselineAuditEventDigest": baseline_audit.digest,
            "claimBoundary": "Sealed G4 and C3 remain unproven.",
        }
        event = self.ledger.append(
            scope.root_id, scope.campaign_id, "development.g0_g3.ready",
            payload, idempotency_key,
        )
        return DevelopmentGateReceipt.from_event(event)
```

Modify `scripts/validate_v2.py --check-eval` to import the service and schema-check a temporary ledger-backed readiness fixture. The validator must not advertise C3 and must fail if the fixture swaps a campaign, candidate, policy, evaluator, or gate digest.

- [ ] **Step 4: Run the complete Plan 9 proof gate**

Run:

```bash
python3 -m pytest -q \
  tests/selfloop/test_gate_store.py \
  tests/selfloop/test_g0_g1.py \
  tests/selfloop/test_g2_and_baseline_cache.py \
  tests/selfloop/test_progressive_gates.py \
  tests/selfloop/test_development_conformance.py
python3 scripts/validate_v2.py --check-eval
git diff --check
```

Expected: all tests pass; validator exits `0`; diff check is silent; the persisted readiness event reports C2/G3 and resolves four same-campaign gate receipts plus the baseline audit.

- [ ] **Step 5: Commit ledger-backed development readiness**

```bash
git add scripts/selfloop_supervisor/gates/development_conformance.py scripts/validate_v2.py tests/selfloop/test_development_conformance.py
git commit -m "feat(selfloop): persist verified development gate readiness"
```

## Plan 9 Completion Gate

- [ ] G0/G1 evidence is built only by protected runners from exact P08 ledger events and exact reopened P02 candidate/champion release receipts; callers cannot substitute paths, attestations, provenance maps, checks, or booleans.
- [ ] Every gate and baseline mutation uses P05's campaign-scoped five-argument `Ledger.append`.
- [ ] Every effectful P09 service is bound to a live controller mutation session and consumes a phase-scoped capability; unbound and closed-session mutations fail.
- [ ] Gate receipts hash the full scope, pairing identity (including both source-attestation and release-bundle receipt digests), checks, artifacts, previous receipt, and policy/supervisor identities.
- [ ] G2 membership and baseline keys are deterministic, complete, ledger-indexed, and artifact-verified.
- [ ] G2/G3 resume verifies commit, release, budget, prior gate, and artifacts, then reuses sealed raw results without duplicate calls.
- [ ] `development.g0_g3.ready` is persisted from the unique current ledger chain and remains C2; Plan 10 alone may prove C3.
- [ ] Execute the roadmap's **Shared protected-runtime rollover execution task** with `SOURCE_STAGE=P08`, `TARGET_STAGE=P09`, and the exact committed P09 SHA; verify its authorization/pending/activation/rescue/fresh-loader receipt chain before the runtime-facing Plan 9 command is accepted.
