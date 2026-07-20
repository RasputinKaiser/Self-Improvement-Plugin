# Selfloop Atomic Trial Install and Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the one ledger-authorized G4 winner, install it into an immutable local slot with replayable phase evidence, prove the loaded trial identity, and recover the complete stable runtime/configuration tuple after every injected fault.

**Architecture:** `PromotionResolver` accepts only a root, promotion ID, and idempotency key, then folds the anchored P05 ledger to recover the exact P09 `GateScope`/`PairingIdentity` chain, P10 G4 terminal decision and single `campaign.policy.pinned` bundle, release bundle, current stable tuple, registered local boundaries, and pinned supervisor. A typed phase journal records an intended action before every filesystem/process/host effect, seals the effect's raw output at a deterministic artifact path, and commits a hash-linked receipt afterward so restart reuses completed evidence. Activation and rollback each change the authoritative release/slot/configuration/runtime tuple in one canonical pointer transaction; rollback prepares and verifies inactive restore generations before that transaction.

**Tech Stack:** Python 3.10+, standard-library dataclasses/hashlib/json/os/pathlib/shutil/sqlite3, P02 releases/snapshots, P03 restricted launcher, P05 anchored ledger, pytest 8+.

## Global Constraints

- Contract: `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- `scripts/selfloop_supervisor/**`, promotion resolution, active pointers, snapshots, rescue build, policies, journals, and receipts execute from pinned `${SIPS_HOME}/selfloop/supervisor/bundles/<digest>/` outside candidate worktrees.
- After source tests pass, the active P10 controller must TTY-authorize, prepare, and activate the exact P11 release through the roadmap's protected rollover checkpoint. The install/rollback adapter and fault-matrix acceptance run only after a fresh loader proves the P11 promotion modules; source-tree imports do not activate trial authority.
- The public install request is exactly `PromotionRequest(root_id, promotion_id, idempotency_key)`. Candidate/stable IDs, paths, digests, policies, boundaries, gate receipts, and pointer values are never caller fields.
- Installation authority is one verified `promotion.authorized.v1` ledger event produced only after a P10 `g4.terminal` `trial_promote` decision and a current persisted P10 C3 conformance receipt for that exact G4/policy/supervisor/release. It binds the exact ordered G0-G3 `GateReceipt` event/receipt digests, each full P09 `PairingIdentity` digest and their verified common base digest, the separate P10 G4 terminal event/`G4RunReceipt` digest, common `GateScope`, P02 `ReleaseIdentity`, manifest, source-attestation digest, and canonical path-independent `ReleaseBundleReceipt.receipt_digest`, the P10 `campaign.policy.pinned` event and bundle digest (including G4/probation policy digests), C3 receipt digest, permission manifest, supervisor, authorized change class, and champion evaluated at G4.
- Resolution fails closed when the ledger/anchor is invalid, any gate or artifact is missing, the G4 champion is not the current canonical stable champion, the bundle bytes disagree with the registered manifest, or the promotion was already superseded/terminated.
- `local-auto-v1` permits only registered local snapshot, slot, configuration-generation, activation-projection, task-local probe, canary, and rollback effects. Push, publish, message, purchase, remote deployment, and paths outside `SelfloopPaths` are denied.
- Slot IDs include the install-payload digest. Existing destinations are immutable: matching content is verified/reused and mismatching content is neither deleted nor overwritten.
- Every external side effect has a unique persisted phase intent before it starts and a persisted phase receipt after success. Raw stdout, stderr, manifests, probe JSON, verifier output, and canary output are content-addressed; resume verifies and reuses them instead of replaying completed work.
- `PromotionResolver` and receipt resolution are read-only. Every authorization append, snapshot/slot/configuration write, activation, rollback, pointer/projection mutation, host probe, canary, and trial-control commit runs inside the P05 controller's live `MutationSession` and consumes a distinct operation/resource/phase `MutationCapability`. Tasks 1-5 define internal services; Task 6 makes the typed controller action their sole mutation entry and proves direct/unbound calls fail.
- The authoritative active tuple is `(release_id, slot_id, config_generation_id, runtime_generation_id)`. Ledger commits and the atomic JSON projection always carry all four values; no partial tuple is representable.
- Before rollback changes authority, P02 snapshot content is materialized into inactive runtime/configuration generations and verified. No active directory or configuration is overwritten in place.
- Tests use real temporary files and P05 SQLite ledgers. Unit host/canary adapters may be deterministic, but all receipts are computed from actual bytes and effects; no live cache, configuration, host, or plugin is mutated.

---

### Task 1: Resolve the exact ledger-authorized G4 winner

**Files:**
- Create: `scripts/selfloop_supervisor/promotion/resolver.py`
- Test: `tests/selfloop/test_promotion_resolver.py`

**Interfaces:**
- Consumes: P02 `ReleaseIdentity`, byte-bearing `ReleaseBundleReceipt`, and `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, P05 `Ledger.verify`/`StateStore.stable_champion`/generic journal methods, P09 `GateScope`/`PairingIdentity`/ordered `GateReceipt` events and `development.g0_g3.ready`, P10 `G4RunReceipt`/`g4.terminal`/`CampaignPolicyService`, `SelfloopPaths`, and registered root/release/supervisor records.
- Produces: `PromotionRequest`, `PromotionAuthorizationReceipt`, `ResolvedPromotion`, `PromotionAuthorizationStore.authorize_g4`, and `PromotionResolver.resolve`.
- `PromotionAuthorizationStore.authorize_g4(root_id, g4_terminal_event_digest, idempotency_key, capability)` is protected orchestration, not a public API. It validates and consumes the exact P05 `PROMOTION_AUTHORIZE` capability, resolves the terminal event, derives `promotion_id = "promotion-" + sha256(g4_receipt.receipt_digest)[:24]`, and appends `promotion.authorized.v1` only for `trial_promote`.

- [ ] **Step 1: Write failing minimal-request and cross-proof tests**

```python
def test_public_request_has_no_identity_or_path_injection_fields():
    request = PromotionRequest("root-1", "promotion-7", "install-7")
    assert dataclasses.asdict(request) == {
        "root_id": "root-1", "promotion_id": "promotion-7",
        "idempotency_key": "install-7",
    }
    with pytest.raises(TypeError):
        PromotionRequest("root-1", "promotion-7", "install-7",
                         stable_release_id="release-attacker")

def test_resolver_returns_exact_authorized_release_and_current_stable(canonical_promotion):
    resolved = canonical_promotion.resolver.resolve(canonical_promotion.request)
    assert resolved.candidate_release == canonical_promotion.g4_candidate_release
    assert resolved.g0_g3_receipt_digests == canonical_promotion.ordered_g0_g3_digests
    assert resolved.g4_receipt_digest == canonical_promotion.g4_receipt.receipt_digest
    assert resolved.stable_release.release_id == "release-stable"
    assert resolved.candidate_bundle.path.is_relative_to(
        canonical_promotion.paths.release_bundles
    )
    assert resolved.candidate_bundle.receipt_digest == (
        canonical_promotion.g4_candidate_bundle.receipt_digest
    )

@pytest.mark.parametrize("mutation", (
    "g4_outcome", "gate_order", "gate_scope", "pairing_identity",
    "policy_bundle_digest", "campaign_policy_pin_event",
    "manifest_digest", "commit_sha", "source_attestation_digest",
    "release_bundle_receipt_digest", "bundle_byte", "current_stable",
    "supervisor_digest", "c3_conformance_receipt", "authorization_event_digest",
))
def test_resolver_rejects_any_cross_proof_mismatch(canonical_promotion, mutation):
    canonical_promotion.mutate(mutation)
    with pytest.raises(PromotionResolutionError):
        canonical_promotion.resolver.resolve(canonical_promotion.request)
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_promotion_resolver.py`

Expected: collection fails because `selfloop_supervisor.promotion.resolver` and `promotion.authorized.v1` do not exist.

- [ ] **Step 3: Persist complete G4 authorization and implement the resolver**

Do not add a parallel context or policy event. Resolve P10's `g4.terminal` event and its `G4RunReceipt`, then follow its source event digests to P09 `development.g0_g3.ready`, the ordered G0-G3 receipts, and P10's one `campaign.policy.pinned` event. P10 already hashes the exact candidate/champion manifest identities and policy-pin source into `G4RunReceipt`; the authorization cross-checks those fields against P02 registered bundle bytes and the full P09 `PairingIdentity`.

```python
@dataclass(frozen=True)
class PromotionRequest:
    root_id: str
    promotion_id: str
    idempotency_key: str

@dataclass(frozen=True)
class ResolvedPromotion:
    root_id: str; campaign_id: str; generation_id: str; experiment_id: str
    promotion_id: str; authorization_receipt_digest: str
    g0_g3_receipt_digests: tuple[str, str, str, str]
    g4_receipt_digest: str; g4_terminal_event_digest: str
    gate_scope: GateScope
    g0_g3_pairing_identities: tuple[
        PairingIdentity, PairingIdentity, PairingIdentity, PairingIdentity
    ]
    pairing_base_digest: str
    campaign_policy_pin_event_digest: str; policy_bundle_digest: str
    g4_policy_id: str; g4_policy_digest: str
    probation_policy_id: str; probation_policy_digest: str
    c3_conformance_receipt_digest: str
    change_class: str
    candidate_release: ReleaseIdentity; candidate_manifest: ReleaseManifest
    candidate_bundle: ReleaseBundleReceipt
    stable_release: ReleaseIdentity; stable_slot_id: str
    stable_config_generation_id: str; stable_runtime_generation_id: str
    install_boundary: Path; config_generation_boundary: Path
    runtime_generation_boundary: Path; artifact_boundary: Path
    permission_manifest_digest: str; supervisor_digest: str
    ledger_head_digest: str

class PromotionResolver:
    def resolve(self, request: PromotionRequest) -> ResolvedPromotion:
        head = self.ledger.verify()
        authorization = self.authorizations.require(
            request.root_id, request.promotion_id
        )
        g4 = self.gates.require_g4_terminal(
            request.root_id, authorization.g4_terminal_event_digest
        )
        if g4.decision.outcome != "trial_promote":
            raise PromotionResolutionError("G4 did not authorize trial promotion")
        development, gates = self.gates.require_development_chain(
            request.root_id,
            authorization.development_ready_event_digest,
            authorization.g0_g3_receipt_digests,
        )
        pairing_base = self.gates.require_common_pairing_base(
            gates, development
        )
        self._require_g4_matches_scope_and_pairing_base(
            g4, development.scope, pairing_base
        )
        campaign_policy = self.campaign_policies.resolve(development.scope)
        c3 = self.conformance.require_current_c3(
            g4.scope, g4.receipt_digest,
            campaign_policy.policy_bundle_digest,
        )
        registered = self.releases.require_registered(
            request.root_id, g4.scope.candidate_release_id
        )
        release = self.release_bundles.open_verified(
            registered.release_id, registered.source_attestation_digest,
        )
        require_equal(
            release.receipt_digest,
            registered.release_bundle_receipt_digest,
        )
        stable = self.state.stable_champion(request.root_id)
        if stable.release_id != g4.scope.champion_release_id:
            raise PromotionResolutionError("G4 champion is no longer canonical stable")
        boundaries = self.boundaries.require_registered(request.root_id)
        self._require_authorization_matches(
            authorization, g4, campaign_policy, c3, release, stable,
            boundaries, head
        )
        return ResolvedPromotion.from_verified(
            authorization, gates, g4, release, stable, boundaries, head
        )
```

`PromotionAuthorizationStore.authorize_g4` verifies the anchored ledger, P09 readiness and ordered G0-G3 previous-receipt links, P10 G4 terminal source links, exact common `GateScope`, every full gate-specific `PairingIdentity` and their common `base_digest()`, the single P10 campaign-policy pin, current P10 C3 receipt, registered release ID/source-attestation/receipt-digest tuple and reopened bytes, authorized P08 change class, and current stable champion before appending its authorization. G4 remains a distinct `G4RunReceipt`; it is never coerced into a P09 `GateReceipt`. The event carries values, not executable paths; `PromotionResolver` reconstructs the canonical path only by reopening the protected P02 store and comparing `ReleaseBundleReceipt.receipt_digest`. Replay of the same idempotency key returns the original event; a changed payload is a P05 `IdempotencyConflict`.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_promotion_resolver.py tests/selfloop/test_g4_runner.py tests/selfloop/test_gate_store.py tests/selfloop/test_ledger.py`

Expected: minimal request, stale champion, wrong gate/release/policy, bundle tamper, anchor tamper, and idempotent authorization tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/promotion/resolver.py tests/selfloop/test_promotion_resolver.py
git commit -m "feat(selfloop): resolve ledger-authorized promotions"
```

### Task 2: Enforce local authorization and immutable slot identity

**Files:**
- Create: `scripts/selfloop_supervisor/promotion/slots.py`
- Create: `scripts/selfloop_supervisor/promotion/authorization.py`
- Test: `tests/selfloop/test_trial_slots.py`

**Interfaces:**
- Consumes: `ResolvedPromotion` and its supervisor-derived boundaries; no caller policy/path.
- Produces: pure `slot_id_for`, `InstallSlot`, and capability-gated `PromotionSlotService.create_or_verify_slot(promotion, capability)` plus `authorize_local_action`. No module-level slot mutator remains callable without a P05 session capability.

- [ ] **Step 1: Write failing boundary and immutable-reuse tests**

```python
def test_slot_id_includes_payload_digest_and_cannot_be_overwritten(
    tmp_path, resolved_promotion, slot_service, promotion_capability
):
    first = slot_service.create_or_verify_slot(
        resolved_promotion,
        promotion_capability("slot.materialize", resolved_promotion.promotion_id),
    )
    assert resolved_promotion.candidate_release.install_payload_digest[:16] in first.slot_id
    replay = slot_service.create_or_verify_slot(
        resolved_promotion,
        promotion_capability(
            "slot.materialize", resolved_promotion.promotion_id, replay=True
        ),
    )
    assert replay == first
    corrupt_one_byte(first.root)
    with pytest.raises(SlotIntegrityError, match="existing immutable slot mismatch"):
        slot_service.create_or_verify_slot(
            resolved_promotion,
            promotion_capability("slot.verify", resolved_promotion.promotion_id),
        )

def test_slot_mutation_rejects_missing_or_reused_capability(
    resolved_promotion, slot_service, promotion_capability
):
    with pytest.raises(MutationCapabilityRequired):
        slot_service.create_or_verify_slot(resolved_promotion, capability=None)
    capability = promotion_capability(
        "slot.materialize", resolved_promotion.promotion_id
    )
    slot_service.create_or_verify_slot(resolved_promotion, capability)
    with pytest.raises(MutationDenied, match="already consumed"):
        slot_service.create_or_verify_slot(resolved_promotion, capability)

@pytest.mark.parametrize("action", (
    "push", "publish", "message", "purchase", "remote_deploy",
))
def test_local_auto_denies_external_actions(action, resolved_promotion):
    with pytest.raises(PermissionError):
        authorize_local_action(resolved_promotion, action,
                               resolved_promotion.install_boundary)
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_trial_slots.py`

Expected: FAIL importing `selfloop_supervisor.promotion.slots`.

- [ ] **Step 3: Implement exact identity and boundary authorization**

```python
@dataclass(frozen=True)
class InstallSlot:
    slot_id: str; release_id: str; release_digest: str
    root: Path; manifest_digest: str; receipt_digest: str

def slot_id_for(release: ReleaseIdentity) -> str:
    return f"slot-{release.release_id}-{release.install_payload_digest[:16]}"

class PromotionSlotService:
    def create_or_verify_slot(
        self, promotion: ResolvedPromotion, capability: MutationCapability
    ) -> InstallSlot:
        self.capabilities.require(
            capability, MutationOperation.SLOT_MATERIALIZE,
            resource_id=promotion.promotion_id,
        )
        destination = promotion.install_boundary / slot_id_for(
            promotion.candidate_release
        )
        if destination.exists():
            result = verify_existing_slot(destination, promotion)
        else:
            staging = destination.parent / f".{destination.name}.staging"
            copy_registered_bundle(promotion.candidate_bundle.path, staging)
            verify_staged_slot(staging, promotion.candidate_manifest)
            fsync_tree(staging)
            os.replace(staging, destination)
            fsync_directory(destination.parent)
            remove_group_and_other_write_bits(destination)
            result = verify_existing_slot(destination, promotion)
        self.capabilities.consume(capability, result.receipt_digest)
        return result
```

A stale staging directory is accepted only when its complete manifest, modes, symlink targets, release identity, source-attestation digest, release-bundle receipt digest, and intended phase digest match. Otherwise it is moved to a content-addressed quarantine after a journaled intent; it is never silently deleted. Authorization uses the policy and canonical boundaries already present on `ResolvedPromotion` and records the resolved target in the phase intent. `PromotionResolver` reopens and verifies the exact P02 receipt immediately before the journaled install; `PromotionSlotService` accepts only that protected `ResolvedPromotion` plus the exact live phase capability, copies its resolved receipt path, and verifies every copied byte against the bound manifest before rename. No stored or caller path is byte authority.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_trial_slots.py tests/selfloop/test_promotion_resolver.py`

Expected: immutable reuse, corrupt-existing-slot, stale staging, symlink traversal, boundary traversal, and denied external-action tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/promotion/slots.py scripts/selfloop_supervisor/promotion/authorization.py tests/selfloop/test_trial_slots.py
git commit -m "feat(selfloop): protect immutable promotion slots"
```

### Task 3: Journal every install effect and reuse raw artifacts on restart

**Files:**
- Create: `scripts/selfloop_supervisor/promotion/journal.py`
- Create: `scripts/selfloop_supervisor/promotion/trial_install.py`
- Test: `tests/selfloop/test_promotion_phase_journal.py`
- Test: `tests/selfloop/test_atomic_trial_install.py`

**Interfaces:**
- Consumes: P05 `Ledger.record_intent`/`receipt_for_idempotency_key`/`commit_receipt`, P02 `RecoverySnapshotManager.capture`, `ResolvedPromotion`, `PromotionSlotService`, verifier/canary adapters, protected artifact store, deterministic phase output paths, and a kernel-created live `MutationSession`.
- Produces: `PromotionPhase`, `PhaseReceipt`, session-bound `PromotionPhaseJournal.for_session(session)`/`run`/`resume`, `TrialInstallReceipt`, and internal `TrialInstaller.install(request: PromotionRequest, services: PromotionServices)`. `PromotionServices` can be constructed only by the P05 kernel for the current session; every phase effect and every terminal phase-receipt append gets its own operation/resource/phase capability.
- Required install phases are `promotion.resolve`, `snapshot.capture`, `slot.materialize`, `slot.verify`, `capability.verify`, `canary.rescue`, `canary.startup`, and `install.receipt`.

- [ ] **Step 1: Write the before/after crash and raw-reuse matrix**

```python
INSTALL_EFFECT_PHASES = (
    "snapshot.capture", "slot.materialize", "slot.verify",
    "capability.verify", "canary.rescue", "canary.startup",
)

@pytest.mark.parametrize("phase", INSTALL_EFFECT_PHASES)
@pytest.mark.parametrize("edge", ("before_effect", "after_effect_before_receipt"))
def test_restart_reuses_completed_install_effect_and_raw_artifact(
    promotion_fixture, phase, edge
):
    promotion_fixture.crash_at(phase, edge)
    with pytest.raises(SimulatedCrash):
        promotion_fixture.installer.install(
            promotion_fixture.request, promotion_fixture.session_services()
        )
    calls = promotion_fixture.effect_calls(phase)
    raw_digest = promotion_fixture.raw_digest_if_present(phase)
    restarted = promotion_fixture.restart()
    receipt = restarted.installer.install(
        restarted.request, restarted.recovery_session_services()
    )
    assert receipt.status == "installed_verified"
    assert promotion_fixture.effect_calls(phase) == calls + (0 if edge == "after_effect_before_receipt" else 1)
    if raw_digest is not None:
        assert promotion_fixture.phase_receipt(phase).raw_artifact_digest == raw_digest

def test_changed_request_payload_conflicts_with_existing_phase_intent(promotion_fixture):
    services = promotion_fixture.session_services()
    promotion_fixture.installer.install(promotion_fixture.request, services)
    with pytest.raises(IdempotencyConflict):
        promotion_fixture.installer.install(
            replace(promotion_fixture.request, promotion_id="promotion-other"),
            services,
        )
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_promotion_phase_journal.py tests/selfloop/test_atomic_trial_install.py`

Expected: collection fails because `promotion.journal` and `TrialInstaller` do not exist.

- [ ] **Step 3: Implement intended-action, deterministic raw output, and receipt commits**

```python
@dataclass(frozen=True)
class PhaseReceipt:
    schema: str; root_id: str; campaign_id: str; promotion_id: str
    phase: str; intent_id: str; input_digest: str
    raw_artifact_digest: str; raw_artifact_relative_path: str
    observed_state_digest: str; status: str
    receipt_digest: str; event_sequence: int; event_digest: str

class PromotionPhaseJournal:
    def run(
        self, promotion, phase, operation, resource_id,
        input_payload, effect, probe,
    ):
        key = f"{promotion.promotion_id}:{phase}"
        if saved := self.phase_receipts.get(promotion.root_id, key):
            return self._verify_saved(saved, input_payload)
        intent = self.ledger.record_intent(
            promotion.root_id, promotion.campaign_id, phase,
            self._intent_payload(promotion, input_payload), key,
        )
        raw_path = self.artifacts.intended_path(intent.intent_id, "raw.json")
        if raw_path.exists():
            raw = self.artifacts.verify_and_read(raw_path, intent.payload_digest)
        elif observed := probe(intent):
            self.recovery.reconcile_completed_effect(intent, observed)
            raw = self.artifacts.seal_at_intended_path(
                raw_path,
                observed,
                capability=self.session.issue(
                    MutationOperation.ARTIFACT_PERSIST,
                    intent.intent_id,
                    f"{phase}.raw",
                ),
            )
        else:
            effect_capability = self.session.issue(operation, resource_id, phase)
            observed = effect(intent, effect_capability)
            raw = self.artifacts.seal_at_intended_path(
                raw_path,
                observed,
                capability=self.session.issue(
                    MutationOperation.ARTIFACT_PERSIST,
                    intent.intent_id,
                    f"{phase}.raw",
                ),
            )
        receipt = PhaseReceipt.from_raw(intent, raw, probe(intent))
        receipt_capability = self.session.issue(
            MutationOperation.PHASE_RECEIPT_COMMIT,
            intent.intent_id,
            f"{phase}.receipt",
        )
        committed = self.phase_receipts.commit(
            intent, receipt, receipt_capability
        )
        return committed
```

The one phase intent names every path/process argument and the deterministic raw-output destination before any write or launch. Each effect must either be intrinsically content-addressed or provide a `probe` that proves its completed target from bytes. Canary and host-probe subprocesses write their raw JSON/stdout/stderr bundle to the intended path before reporting success, so a crash after process exit never causes a rerun. `PhaseReceipt.receipt_digest` hashes the canonical payload without the storage envelope; `event_sequence` and `event_digest` bind that payload to the verified P05 chain.

```python
class TrialInstaller:
    def install(
        self, request: PromotionRequest, services: PromotionServices
    ) -> TrialInstallReceipt:
        promotion = self.resolver.resolve(request)
        snapshot = services.phases.run(
            promotion, "snapshot.capture", MutationOperation.SNAPSHOT_CAPTURE,
            promotion.promotion_id, promotion.stable_tuple_payload(),
            effect=lambda intent, capability: services.snapshotter.capture(
                promotion.snapshot_context(), promotion.snapshot_boundaries(),
                capability=capability,
            ).to_raw(),
            probe=services.snapshotter.probe_capture,
        )
        slot = services.phases.run(
            promotion, "slot.materialize", MutationOperation.SLOT_MATERIALIZE,
            promotion.promotion_id, promotion.candidate_identity_payload(),
            effect=lambda intent, capability: services.slots.create_or_verify_slot(
                promotion, capability
            ).to_raw(),
            probe=lambda intent: probe_slot(promotion),
        )
        verified = self._run_verification_and_canary_phases(
            promotion, slot, services
        )
        return services.install_receipts.commit_install(
            promotion, snapshot, slot, verified,
            capability=services.issue(
                MutationOperation.INSTALL_RECEIPT,
                promotion.promotion_id,
                "install.receipt",
            ),
        )
```

`TrialInstallReceipt` carries the authorization digest, ordered G0-G4 digests, snapshot, stable four-field tuple, candidate release/slot/config/runtime generation identities, every phase receipt digest, and the ledger head it extends. It is built from stored phase receipts, never from caller-supplied status. Each low-level effect callee consumes its own phase capability; `ArtifactStore.seal_at_intended_path`, `PhaseReceiptStore.commit`, and `commit_install` likewise consume distinct capabilities. `reconcile_completed_effect` may finish only the capability intent already persisted for that exact phase; it cannot mint authority or replay the effect.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_promotion_phase_journal.py tests/selfloop/test_atomic_trial_install.py tests/selfloop/test_trial_slots.py`

Expected: every before/after crash resumes at the first incomplete phase; completed effects and raw artifacts are not replayed; stable authority remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/promotion/journal.py scripts/selfloop_supervisor/promotion/trial_install.py tests/selfloop/test_promotion_phase_journal.py tests/selfloop/test_atomic_trial_install.py
git commit -m "feat(selfloop): journal every trial install effect"
```

### Task 4: Activate and roll back one complete canonical tuple

**Files:**
- Modify: `scripts/selfloop_supervisor/snapshot.py`
- Create: `scripts/selfloop_supervisor/promotion/activation.py`
- Create: `scripts/selfloop_supervisor/promotion/rollback.py`
- Test: `tests/selfloop/test_activation_and_rollback.py`
- Test: `tests/selfloop/test_promotion_fault_matrix.py`

**Interfaces:**
- Consumes: verified `TrialInstallReceipt`, a session-bound phase journal, P05 canonical state/pointer transaction, atomic projection, task-local host probe, P02 snapshot, verifier, rescue canary, and kernel-created `PromotionServices`.
- Produces: `ActiveTuple`, `PreparedRollback`, `ActivationReceipt`, `RollbackReceipt`, capability-gated `RecoverySnapshotManager.prepare_restore`, and internal `activate_trial(request, services)`, `rollback_trial(request, trigger_event_digest, services)`, and `recover_promotion(request, recovery_services)` entry points. No transition helper accepts a caller-minted or orchestration-wide capability.
- Activation phases are `activation.prepare`, `activation.pointer_transaction`, `activation.projection`, `activation.host_probe`, and `activation.receipt`. Rollback phases are `rollback.runtime_prepare`, `rollback.config_prepare`, `rollback.verify`, `rollback.pointer_transaction`, `rollback.projection`, `rollback.host_probe`, `rollback.rescue_canary`, and `rollback.receipt`.

- [ ] **Step 1: Write full-tuple, inactive-restore, and exhaustive fault tests**

```python
def test_rollback_prepares_inactive_generations_before_pointer_transaction(
    active_trial
):
    active_trial.crash_at("rollback.pointer_transaction", "before_effect")
    with pytest.raises(SimulatedCrash):
        active_trial.rollback("integrity-failure")
    prepared = active_trial.rollback_store.prepared("promotion-7")
    assert prepared.runtime_verified and prepared.config_verified
    assert prepared.runtime_root != active_trial.current_runtime_root()
    assert prepared.config_root != active_trial.current_config_root()
    assert active_trial.canonical_tuple() == active_trial.trial_tuple

def test_rollback_switches_release_slot_config_and_runtime_together(active_trial):
    receipt = active_trial.rollback("integrity-failure")
    assert receipt.active_tuple == active_trial.stable_tuple
    assert active_trial.canonical_tuple() == active_trial.stable_tuple
    assert active_trial.projected_tuple() == active_trial.stable_tuple
    assert active_trial.trial_evidence_exists()

ALL_TRANSITION_PHASES = INSTALL_EFFECT_PHASES + (
    "install.receipt",
    "activation.prepare", "activation.pointer_transaction",
    "activation.projection", "activation.host_probe", "activation.receipt",
    "rollback.runtime_prepare", "rollback.config_prepare", "rollback.verify",
    "rollback.pointer_transaction", "rollback.projection",
    "rollback.host_probe", "rollback.rescue_canary", "rollback.receipt",
)

@pytest.mark.parametrize("phase", ALL_TRANSITION_PHASES)
@pytest.mark.parametrize("edge", ("before_effect", "after_effect_before_receipt"))
def test_fault_matrix_never_exposes_a_mixed_tuple_and_reuses_effect(
    promotion_fault_fixture, phase, edge
):
    promotion_fault_fixture.crash_at(phase, edge)
    with pytest.raises(SimulatedCrash):
        promotion_fault_fixture.run()
    promotion_fault_fixture.assert_every_visible_tuple_is_whole()
    calls = promotion_fault_fixture.effect_calls(phase)
    terminal = promotion_fault_fixture.restart().recover_promotion("promotion-7")
    promotion_fault_fixture.assert_every_visible_tuple_is_whole()
    assert promotion_fault_fixture.effect_calls(phase) == calls + (
        0 if edge == "after_effect_before_receipt" else 1
    )
    assert terminal.status in {"trial_active", "rolled_back"}
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_activation_and_rollback.py tests/selfloop/test_promotion_fault_matrix.py`

Expected: FAIL because direct P02 restore mutates active boundaries and no four-field pointer transaction exists.

- [ ] **Step 3: Prepare restores off-path, then commit one pointer transaction**

```python
@dataclass(frozen=True)
class ActiveTuple:
    release_id: str; slot_id: str
    config_generation_id: str; runtime_generation_id: str

@dataclass(frozen=True)
class PreparedRollback:
    promotion_id: str; stable_tuple: ActiveTuple; snapshot_id: str
    runtime_root: Path; config_root: Path
    runtime_manifest_digest: str; config_manifest_digest: str
    runtime_verified: bool; config_verified: bool; receipt_digest: str

def rollback_trial(
    request: PromotionRequest, trigger_event_digest: str, services
) -> RollbackReceipt:
    promotion = services.resolver.resolve(request)
    runtime = services.run_effect(
        promotion, "rollback.runtime_prepare",
        MutationOperation.ROLLBACK_RUNTIME_PREPARE,
        effect=lambda capability: services.restore_preparer.prepare_runtime(
            promotion, capability
        ),
    )
    config = services.run_effect(
        promotion, "rollback.config_prepare",
        MutationOperation.ROLLBACK_CONFIG_PREPARE,
        effect=lambda capability: services.restore_preparer.prepare_config(
            promotion, capability
        ),
    )
    prepared = services.run_effect(
        promotion, "rollback.verify", MutationOperation.ROLLBACK_VERIFY,
        effect=lambda capability: services.restore_preparer.verify_prepared(
            promotion, runtime, config, capability
        ),
    )
    if not prepared.runtime_verified or not prepared.config_verified:
        raise RollbackFailure("inactive restore verification failed")
    switched = services.run_effect(
        promotion, "rollback.pointer_transaction",
        MutationOperation.ROLLBACK_POINTER_TRANSACTION,
        effect=lambda capability: services.pointer_store.commit_rollback_transaction(
            root_id=promotion.root_id,
            promotion_id=promotion.promotion_id,
            expected_active_tuple=promotion.trial_tuple,
            active_tuple=prepared.stable_tuple,
            trial_tuple=None,
            preserve_trial_evidence=True,
            trigger_event_digest=trigger_event_digest,
            prepared_restore_receipt_digest=prepared.receipt_digest,
            capability=capability,
        ),
    )
    services.run_effect(
        promotion, "rollback.projection", MutationOperation.POINTER_PROJECTION,
        effect=lambda capability: services.pointer_projection.rebuild_atomic(
            promotion.root_id, switched, capability
        ),
    )
    loaded = services.run_effect(
        promotion, "rollback.host_probe", MutationOperation.HOST_PROBE,
        effect=lambda capability: services.host_probe.run_task_local(
            switched.active_tuple, capability
        ),
    )
    services.host_probe.require_exact_tuple(loaded, switched.active_tuple)
    rescue = services.run_effect(
        promotion, "rollback.rescue_canary", MutationOperation.RESCUE_CANARY,
        effect=lambda capability: services.canary.run_rescue(
            switched.active_tuple, capability
        ),
    )
    return services.run_effect(
        promotion, "rollback.receipt", MutationOperation.ROLLBACK_RECEIPT,
        effect=lambda capability: services.rollback_receipts.commit(
            promotion, prepared, switched, loaded, rescue, capability
        ),
    )
```

Add capability-gated `RecoverySnapshotManager.prepare_restore(snapshot_id, boundaries, destination_root, capability)`. It verifies the immutable snapshot first, materializes each boundary under deterministic inactive generation directories, fsyncs them, verifies the complete manifest there, consumes the exact preparation capability with its receipt, and returns without replacing a live path. Runtime preparation reuses the retained stable slot when it verifies exactly; if it is missing, it reconstructs that exact inactive stable slot from the snapshot before the pointer transaction. A mismatching immutable stable slot fails closed and leaves rescue authority intact.

`commit_activation_transaction` and `commit_rollback_transaction` are single `BEGIN IMMEDIATE` transitions in the P05 typed pointer repository. Each checks an expected prior tuple, validates its exact pointer-transaction capability, and writes stable, trial, active release, active slot, active config generation, active runtime generation, phase, and proof digests together. `active-pointer.json` projects the four-field tuple plus ledger head through temp-file, fsync, and `os.replace` under a distinct projection capability. A projection may lag after a crash, but neither canonical nor projected state can contain a mixed tuple; `recover_promotion` verifies the anchor, reuses phase artifacts, and reconciles the projection before any new host probe. Activation uses the same `services.run_effect` pattern for each listed activation phase, so install, activation, rollback drill, and exact reactivation never share a capability nonce.

Wrong task-local runtime proof immediately invokes the same prepared rollback path. The test matrix covers both edges around every snapshot/slot/canary/process write, both pointer transactions, both projection renames, both host probes, rescue, and terminal receipts.

- [ ] **Step 4: Verify green**

Run: `python3 -m pytest -q tests/selfloop/test_activation_and_rollback.py tests/selfloop/test_promotion_fault_matrix.py tests/selfloop/test_atomic_trial_install.py`

Expected: every phase/edge recovers; all visible tuples are complete stable or complete trial tuples; completed effects run once; rollback preserves rejected-trial evidence.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/snapshot.py scripts/selfloop_supervisor/promotion/activation.py scripts/selfloop_supervisor/promotion/rollback.py tests/selfloop/test_activation_and_rollback.py tests/selfloop/test_promotion_fault_matrix.py
git commit -m "feat(selfloop): atomically activate and restore full runtime tuples"
```

### Task 5: Persist and verify the trial-control handoff

**Files:**
- Create: `scripts/selfloop_supervisor/promotion/trial_control_receipt.py`
- Modify: `scripts/validate_v2.py`
- Test: `tests/selfloop/test_trial_control_receipt.py`

**Interfaces:**
- Consumes: verified authorization/install/activation phase events, an actual rollback drill, subsequent exact reactivation, current canonical trial tuple, P05 anchor, and the current persisted P10 C3 receipt/pinned campaign policy/spec/supervisor digests.
- Produces: `TrialControlReceipt`, capability-gated `TrialControlStore.commit_ready(root_id, promotion_id, idempotency_key, capability)`, and read-only `resolve(root_id, promotion_id, expected_digest)`/`resolve_current(root_id, promotion_id)`.
- Plan 12 must call `resolve`/`resolve_current`. Passing a deserialized receipt object or a list of digest-looking strings is insufficient.

- [ ] **Step 1: Write persisted-handoff and no-overclaim tests**

```python
def test_trial_control_is_persisted_after_real_rollback_and_reactivation(
    promotion_with_rollback_drill
):
    receipt = promotion_with_rollback_drill.store.commit_ready(
        "root-1", "promotion-7", "trial-control-7",
        promotion_with_rollback_drill.capability("trial_control.ready"),
    )
    assert receipt.status == "trial_control_ready"
    assert receipt.conformance == "C3"
    assert receipt.c3_conformance_receipt_digest == (
        promotion_with_rollback_drill.current_c3.receipt_digest
    )
    assert receipt.rollback_drill_receipt_digest
    assert receipt.current_activation_receipt_digest
    assert promotion_with_rollback_drill.store.resolve(
        "root-1", "promotion-7", receipt.receipt_digest
    ) == receipt

def test_trial_control_rejects_digest_shaped_but_unbacked_proof(
    promotion_with_rollback_drill
):
    promotion_with_rollback_drill.replace_activation_digest(
        "sha256:" + "0" * 64
    )
    with pytest.raises(TrialControlError, match="persisted phase receipt"):
        promotion_with_rollback_drill.store.commit_ready(
            "root-1", "promotion-7", "trial-control-7",
            promotion_with_rollback_drill.capability("trial_control.ready"),
        )

def test_trial_control_is_not_current_after_pointer_or_policy_change(
    ready_trial_control
):
    ready_trial_control.mutate_canonical_pointer()
    with pytest.raises(TrialControlError, match="no longer current"):
        ready_trial_control.store.resolve_current("root-1", "promotion-7")

def test_crash_after_trial_control_event_reuses_one_terminal_receipt(
    promotion_with_rollback_drill
):
    promotion_with_rollback_drill.crash_after("trial_control.ready")
    with pytest.raises(SimulatedCrash):
        promotion_with_rollback_drill.store.commit_ready(
            "root-1", "promotion-7", "trial-control-7",
            promotion_with_rollback_drill.capability("trial_control.ready"),
        )
    receipt = promotion_with_rollback_drill.restart().store.commit_ready(
        "root-1", "promotion-7", "trial-control-7",
        promotion_with_rollback_drill.recovery_capability("trial_control.ready"),
    )
    assert receipt.status == "trial_control_ready"
    assert promotion_with_rollback_drill.ledger.count(
        "trial_control.ready"
    ) == 1
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_trial_control_receipt.py`

Expected: collection fails because no persisted `TrialControlStore` exists.

- [ ] **Step 3: Build the receipt only from verified ledger history**

```python
@dataclass(frozen=True)
class TrialControlReceipt:
    schema: str; root_id: str; campaign_id: str; generation_id: str
    experiment_id: str; promotion_id: str; status: str; conformance: str
    authorization_receipt_digest: str
    ordered_g0_g3_receipt_digests: tuple[str, str, str, str]
    g4_receipt_digest: str; g4_terminal_event_digest: str
    install_receipt_digest: str; first_activation_receipt_digest: str
    rollback_drill_receipt_digest: str
    current_activation_receipt_digest: str
    stable_tuple: ActiveTuple; active_trial_tuple: ActiveTuple
    campaign_policy_pin_event_digest: str; policy_bundle_digest: str
    g4_policy_id: str; g4_policy_digest: str
    probation_policy_id: str; probation_policy_digest: str
    c3_conformance_receipt_digest: str
    permission_manifest_digest: str; supervisor_digest: str; spec_digest: str
    phase_receipt_digests: tuple[str, ...]; created_at: str
    ledger_sequence: int; ledger_head_digest: str
    claim_boundary: str; receipt_digest: str

class TrialControlStore:
    def commit_ready(
        self, root_id, promotion_id, idempotency_key, capability
    ):
        self.capabilities.require(
            capability, MutationOperation.TRIAL_CONTROL_COMMIT,
            resource_id=promotion_id,
        )
        self.ledger.verify()
        proof = self.fold_verified_promotion(root_id, promotion_id)
        proof.require_authorized_g4_and_complete_phase_chain()
        c3 = proof.require_current_p10_c3_receipt()
        proof.require_actual_rollback_drill_then_exact_reactivation()
        proof.require_current_trial_tuple()
        receipt = TrialControlReceipt.from_fold(
            proof, c3_conformance=c3,
            claim_boundary="G5 probation and C4 remain unproven.",
        )
        return self.commit_receipt(receipt, idempotency_key, capability)
```

The rollback drill is the real P11 path: activate the authorized trial, roll back to the verified stable tuple, prove stable task-local loading/rescue, then reactivate the same verified trial and prove its exact tuple. `commit_ready` refuses an isolated simulation receipt, a drill that leaves canonical state stable, or a missing/stale P10 C3 receipt. Its conformance field is copied from and hash-linked to that current receipt; trial-control never creates C3. The persisted `trial_control.ready` event is the only Plan 11-to-Plan 12 handoff.

Extend `validate_v2.py` with `--verify-trial-control --sips-home PATH --root-id ID --promotion-id ID`. That mode opens and verifies the P05 ledger/anchor and calls `TrialControlStore.resolve_current`; a source-file existence check may report implementation presence but may not report readiness.

- [ ] **Step 4: Run the Plan 11 gate**

Run:

```bash
python3 -m pytest -q \
  tests/selfloop/test_promotion_resolver.py \
  tests/selfloop/test_trial_slots.py \
  tests/selfloop/test_promotion_phase_journal.py \
  tests/selfloop/test_atomic_trial_install.py \
  tests/selfloop/test_activation_and_rollback.py \
  tests/selfloop/test_promotion_fault_matrix.py \
  tests/selfloop/test_trial_control_receipt.py
python3 scripts/validate_v2.py --check-eval
git diff --check
```

Expected: all selected tests pass; the validator exits `0` without claiming live trial readiness; diff check is silent. The receipt is persisted at C3 and Plan 12 can resolve it by digest.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/promotion/trial_control_receipt.py scripts/validate_v2.py tests/selfloop/test_trial_control_receipt.py
git commit -m "feat(selfloop): persist verified trial control handoff"
```

### Task 6: Wire install and rollback through the one controller capability boundary

**Files:**
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Modify: `scripts/selfloop_supervisor/controller_requests.py`
- Modify: `scripts/selfloop_supervisor/conformance.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/promotion/trial_install.py`
- Modify: `scripts/selfloop_supervisor/promotion/rollback.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `commands/selfloop.md`
- Modify: `skills/sips-selfloop/SKILL.md`
- Test: `tests/selfloop/test_adapter_trial_control.py`
- Modify: `tests/test_homebase_mcp.py`

**Interfaces:**
- Extends P05's closed request contract with `ControllerAction.INSTALL_TRIAL`, exact frozen `InstallTrialPayload(promotion_id: str)`, and one new `PAYLOAD_BY_ACTION` entry; it adds no loose optional request field. Existing `ControllerAction.ROLLBACK` continues to use P05's exact `RollbackPayload`. Adapters accept flat wire fields `action`, `root`, `promotion_id`, and `idempotency_key`, and `ControllerRequest.parse_v2` normalizes `promotion_id` into the action-specific payload before dispatch.
- Produces: `SelfloopController.install_trial`/`rollback_trial`, private `PromotionServices.for_session(session)`, and capability-gated low-level promotion mutators. `PromotionResolver.resolve` remains read-only. `PromotionServices` owns the live session and issues one distinct capability immediately before each named low-level effect; neither controller handler passes one orchestration-wide capability.
- `install-trial` resolves authorization, runs journaled install/activation/rollback-drill/reactivation, and persists `trial_control.ready`. `rollback` records the protected `operator_requested` trigger and invokes the same P11 rollback path.

- [ ] **Step 1: Write failing controller-capability and adapter-parity tests**

```python
def test_cli_and_mcp_build_the_same_minimal_install_request(
    repo_root, authorized_promotion
):
    cli = run_cli(
        "install-trial", "--root", str(repo_root),
        "--promotion-id", authorized_promotion.promotion_id,
        "--idempotency-key", "install-adapter-7", "--json",
    )
    mcp = call_mcp("homebase_selfloop", {
        "version": "v2", "action": "install-trial",
        "root": str(repo_root),
        "promotion_id": authorized_promotion.promotion_id,
        "idempotency_key": "install-adapter-7",
    })
    assert normalized_controller_payload(cli) == normalized_controller_payload(mcp)
    assert set(mcp["request"]) == {
        "action", "root", "promotion_id", "idempotency_key",
    }
    parsed = ControllerRequest.parse_v2(mcp["request"])
    assert parsed.action is ControllerAction.INSTALL_TRIAL
    assert isinstance(parsed.payload, InstallTrialPayload)
    assert parsed.payload.promotion_id == authorized_promotion.promotion_id

@pytest.mark.parametrize("field", (
    "candidate_release_id", "candidate_path", "stable_release_id",
    "stable_slot_id", "g4_receipt_digest", "policy_digest",
    "install_boundary", "config_boundary",
))
def test_mcp_rejects_caller_identity_path_and_policy_fields(
    repo_root, authorized_promotion, field
):
    request = {
        "version": "v2", "action": "install-trial",
        "root": str(repo_root),
        "promotion_id": authorized_promotion.promotion_id,
        "idempotency_key": "reject-extra-7", field: "attacker-value",
    }
    response = call_mcp("homebase_selfloop", request)
    assert response["status"] == "failed"
    assert response["error"] == "unexpected_promotion_field"

def test_direct_install_and_rollback_require_controller_capability(
    promotion_services, promotion_request
):
    with pytest.raises(MutationCapabilityRequired):
        promotion_services.installer.install(promotion_request, services=None)
    with pytest.raises(MutationCapabilityRequired):
        promotion_services.rollback.rollback(
            promotion_request, trigger_event_digest=promotion_services.trigger,
            services=None,
        )

def test_controller_install_and_rollback_are_journaled_and_remain_c3(
    controller_fixture, repo_root, authorized_promotion
):
    installed = controller_fixture.handle(ControllerRequest.parse_v2({
        "action": "install-trial", "root": str(repo_root),
        "promotion_id": authorized_promotion.promotion_id,
        "idempotency_key": "controller-install-7",
    }))
    assert installed.payload["trial_control_receipt_digest"]
    assert installed.payload["conformance"] == "C3"
    assert installed.payload["conformance_receipt_digest"] == (
        controller_fixture.current_c3.receipt_digest
    )
    rolled_back = controller_fixture.handle(ControllerRequest.parse_v2({
        "action": "rollback", "root": str(repo_root),
        "idempotency_key": "controller-rollback-7",
    }))
    assert rolled_back.payload["rollback_receipt_digest"]
    assert rolled_back.payload["resolved_promotion_id"] == (
        authorized_promotion.promotion_id
    )
    assert rolled_back.payload["conformance"] == "C3"
    assert controller_fixture.ledger.has_intent("trial.install")
    assert controller_fixture.ledger.has_intent("trial.rollback")
    phase_caps = installed.payload["phase_capability_receipts"]
    assert len({item["nonce"] for item in phase_caps}) == len(phase_caps)
    assert len({item["phase"] for item in phase_caps}) == len(phase_caps)
    assert controller_fixture.capabilities.reuse_attempts == 0

def test_controller_rejects_install_or_rollback_when_p10_c3_is_stale(
    controller_fixture, repo_root, authorized_promotion
):
    controller_fixture.invalidate_c3_policy()
    for action in ("install-trial", "rollback"):
        arguments = {
            "action": action, "root": str(repo_root),
            "idempotency_key": f"stale-{action}",
        }
        if action == "install-trial":
            arguments["promotion_id"] = authorized_promotion.promotion_id
        response = controller_fixture.handle(ControllerRequest.parse_v2(arguments))
        assert response.payload["status"] == "failed"
        assert response.payload["error"] == "current_c3_receipt_required"
```

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest -q tests/selfloop/test_adapter_trial_control.py tests/test_homebase_mcp.py`

Expected: adapter tests fail because `install-trial` is absent, `rollback` is still unavailable-until-C4, and promotion mutators do not require P05 `MutationCapability`.

- [ ] **Step 3: Make `SelfloopController.handle` the only mutation entry**

```python
def _handle_install_trial(self, request: ControllerRequest):
    identity = self.roots.resolve(request.root)
    if not isinstance(request.payload, InstallTrialPayload):
        raise RequestSchemaError("install-trial payload required")
    minimal = PromotionRequest(
        root_id=identity.root_id,
        promotion_id=request.payload.promotion_id,
        idempotency_key=require_text(request.idempotency_key, "idempotency_key"),
    )
    with self.root_lock.acquire(identity.root_id, self.owner_id) as lock:
        promotion = self.promotion_resolver.resolve(minimal)
        c3 = self.conformance.require_current_c3_for_promotion(promotion)
        authorization = self.policy.authorize(
            request.action, promotion.permission_manifest_digest
        )
        intent = self.journal_promotion_intent(
            identity, minimal, operation="trial.install", lock=lock
        )
        session = self.sessions.from_intent(
            intent, lock=lock, authorization=authorization
        )
        services = self.promotion_services.for_session(session)
        receipt = self.trial_orchestrator.install_activate_drill_and_reactivate(
            minimal, services
        )
        return self.commit_controller_receipt(
            intent, receipt,
            conformance=c3.conformance,
            conformance_receipt_digest=c3.receipt_digest,
            claim_boundary="G5 probation and C4 remain unproven.",
            capability=services.issue(
                MutationOperation.CONTROLLER_RECEIPT,
                promotion.promotion_id,
                "trial.install.controller_receipt",
            ),
        )

def _handle_rollback_trial(self, request: ControllerRequest):
    identity = self.roots.resolve(request.root)
    if not isinstance(request.payload, RollbackPayload):
        raise RequestSchemaError("rollback payload required")
    with self.root_lock.acquire(identity.root_id, self.owner_id) as lock:
        resolved_id = request.payload.promotion_id
        resolution_reason = "explicit_request"
        if resolved_id is None:
            current = self.state.require_unique_eligible_trial(identity.root_id)
            resolved_id = current.promotion_id
            resolution_reason = "unique_current_eligible_trial"
        minimal = PromotionRequest(
            identity.root_id,
            require_text(resolved_id, "resolved promotion_id"),
            require_text(request.idempotency_key, "idempotency_key"),
        )
        promotion = self.promotion_resolver.resolve(minimal)
        c3 = self.conformance.require_current_c3_for_promotion(promotion)
        authorization = self.policy.authorize(
            request.action, promotion.permission_manifest_digest
        )
        intent = self.journal_promotion_intent(
            identity, minimal, operation="trial.rollback", lock=lock,
            resolved_promotion_id=resolved_id,
            resolution_reason=resolution_reason,
        )
        session = self.sessions.from_intent(
            intent, lock=lock, authorization=authorization
        )
        services = self.promotion_services.for_session(session)
        trigger = services.triggers.append_operator_requested(
            identity, minimal,
            capability=services.issue(
                MutationOperation.ROLLBACK_TRIGGER,
                promotion.promotion_id,
                "rollback.operator_requested",
            ),
        )
        receipt = self.rollback_service.rollback(
            minimal, trigger.event_digest, services
        )
        return self.commit_controller_receipt(
            intent, receipt, conformance=c3.conformance,
            conformance_receipt_digest=c3.receipt_digest,
            claim_boundary="G5 probation and C4 remain unproven.",
            resolved_promotion_id=resolved_id,
            resolution_reason=resolution_reason,
            capability=services.issue(
                MutationOperation.CONTROLLER_RECEIPT,
                promotion.promotion_id,
                "trial.rollback.controller_receipt",
            ),
        )
```

Harden `TrialInstaller`, activation, snapshot preparation, pointer commits, projection writes, host probes, canaries, trigger/phase/trial-control receipts, and rollback so each mutating method requires a live P05 `MutationCapability` whose root, campaign, intent, operation, resource, phase, and nonce match. `PromotionServices.for_session` is private to the kernel and is created only inside `SelfloopController.handle` after root binding, policy, lock, resolver, and journal checks. It issues a fresh capability immediately before each low-level effect and never exposes an orchestration-wide capability. Each callee consumes its capability with its own terminal receipt. Recovery re-enters the recorded intent through the controller, creates a recovery session bound to that intent, and issues only the first incomplete phase's capability; completed phase capabilities cannot be replayed.

Add exact CLI forms:

```bash
python3 scripts/selfloop_cli.py install-trial --root PATH --promotion-id ID --idempotency-key KEY --json
python3 scripts/selfloop_cli.py rollback --root PATH [--promotion-id ID] --idempotency-key KEY --json
```

The MCP v2 schema exposes the same four semantic install fields; rollback accepts the same shape with `promotion_id` optional. It rejects unknown promotion fields before controller dispatch. An omitted rollback ID is resolved only under the root lock from the unique current eligible trial, and both the ID and resolution reason are persisted before any rollback effect. Preserve frozen v1 bytes. `commands/selfloop.md` and `skills/sips-selfloop/SKILL.md` delegate to the CLI/controller and do not describe direct mutation. `status` reports the persisted current conformance registry. Install/rollback responses copy C3 and its digest only from the currently verified P10 receipt; a stale/missing receipt fails before mutation, and trial-control alone never manufactures a stage.

- [ ] **Step 4: Verify adapter parity and adjacent recovery**

Run: `python3 -m pytest -q tests/selfloop/test_adapter_trial_control.py tests/selfloop/test_promotion_fault_matrix.py tests/selfloop/test_trial_control_receipt.py tests/test_homebase_mcp.py`

Expected: CLI/MCP parity, extra-field rejection, optional rollback normalization, frozen v1 compatibility, direct/unbound-mutator denial, unique per-effect capability issuance with zero reuse, current-C3 gating/digest propagation, stale-C3 rejection before mutation, controller journaling, idempotent replay, and recovery tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/selfloop_supervisor/contracts.py scripts/selfloop_supervisor/controller_requests.py scripts/selfloop_supervisor/conformance.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/promotion/trial_install.py scripts/selfloop_supervisor/promotion/rollback.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py commands/selfloop.md skills/sips-selfloop/SKILL.md tests/selfloop/test_adapter_trial_control.py tests/test_homebase_mcp.py
git commit -m "feat(selfloop): route trial control through controller"
```

## Plan 11 Completion Gate

- [ ] The public promotion request contains only root ID, promotion ID, and idempotency key; `PromotionResolver` derives every authority/identity/path from a verified ledger.
- [ ] The authorization binds one current G4 `trial_promote` winner to exact `GateScope`, every full P09 `PairingIdentity` plus common base, separate P10 `G4RunReceipt`, commit, manifest, bundle, single P10 campaign-policy pin/bundle, supervisor, permission manifest, and ordered G0-G4 proof chain.
- [ ] Every install/activation/rollback external effect has an intent, raw content-addressed artifact, receipt, and crash-reuse test on both sides of the effect.
- [ ] Existing content-addressed slots are never overwritten.
- [ ] Activation requires exact task-local proof of the whole trial tuple.
- [ ] Rollback prepares verified inactive runtime/configuration generations, changes the whole canonical tuple once, preserves trial evidence, and survives the complete fault matrix without mixed state.
- [ ] `trial_control.ready` is ledger-persisted, current-state verified, consumable by Plan 12, and remains C3 until persisted G5/C4 proof exists.
- [ ] CLI, MCP, command, and skill adapters pass only root/promotion/idempotency through `SelfloopController`; direct mutators require a scoped controller capability, and responses expose C3 only by verifying/carrying the current P10 C3 receipt digest.
- [ ] P11 adds `InstallTrialPayload` to P05's exact discriminated union without a loose request field; typed install and rollback are the only mutation routes and every effect consumes a live phase capability.
- [ ] Execute the roadmap's **Shared protected-runtime rollover execution task** with `SOURCE_STAGE=P10`, `TARGET_STAGE=P11`, and the exact committed P11 SHA; verify its authorization/pending/activation/rescue/fresh-loader receipt chain before any runtime-facing trial-control proof is accepted.
