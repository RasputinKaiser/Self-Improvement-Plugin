# Selfloop Seed Champion Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perform the one-time clean seed ceremony, install and activate a pinned protected supervisor outside candidates, attest the seed without claiming improvement, and establish C1 state atomically.

**Architecture:** Define two versioned C1-only foundation policies, `bootstrap_g0.v1` and `bootstrap_critical_g1.v1`; they are bootstrap subsets and are not C3 gate receipts. A protected bootstrap manager reserves supervisor-assigned campaign/generation identities, builds P02 bundles, runs checks from the immutable release root and P03 isolated profile, then commits the attestation and champion pointers in one SQLite transaction. The pinned P04 supervisor also owns a narrow clean-bundle pending-upgrade bridge for the P04-to-P05 transition; it can attest and stage a candidate supervisor bundle but cannot activate it. JSON state, pointer files, and the marker-delimited `state.yaml` block are regenerated non-authoritative projections.

**Tech Stack:** Python 3.10+, standard-library `sqlite3`, `json`, `hashlib`, `subprocess`, `uuid`, `pathlib`, pytest 8+; P01-P03 supervisor APIs.

## Global Constraints

- Normative contract is `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`; this plan may advertise C1 only after executable tests and a real bootstrap receipt pass.
- “A root without a champion uses one bootstrap ceremony.”
- “An operator selects a clean committed SHA and an explicit local release configuration.”
- “Because no paired predecessor exists, bootstrap establishes a seed; it does not claim an improvement.”
- “The ceremony is permitted once per `rootId`.”
- “Dirty working-tree bytes, an installed cache without a matching source commit, or a release with incomplete provenance cannot be the seed.”
- P01's generated `state.yaml` block is non-authoritative and normalized for dirtiness; every byte outside that block must match the selected commit.
- After bootstrap, stable champion, active release, active install slot, and generation are REQUIRED; trial champion is null.
- Bootstrap reserves opaque supervisor-assigned `campaignId` and `generationId` values under the request digest before its first external effect. Identical replay returns those identities; the attestation and pointer row commit both so P05 imports rather than synthesizes campaign scope.
- The pinned supervisor executes from `${SIPS_HOME}/selfloop/supervisor/bundles/<digest>`, outside candidate repositories and candidate write permissions.
- Release, seed-slot, evaluation, and supervisor construction consume P02 `ReleaseBundleReceipt`; a detached `ReleaseIdentity` or caller bundle path is not byte authority.
- The P04 upgrade bridge runs only from the currently active pinned P04 bundle under `supervisor-upgrade-bridge.v1`. It independently rechecks normalized cleanliness, resolves a content-addressed release receipt by release and source-attestation digests, verifies a short-lived one-use protected operator-authorization receipt issued by that pinned runtime after direct TTY confirmation, stages a candidate supervisor bundle, and records `PendingSupervisorUpgrade`; it never changes the active pointer or imports code from mutable source.
- `bootstrap_g0.v1` and `bootstrap_critical_g1.v1` MUST NOT be reported as C3 G0 or G1 conformance.
- Source, bundle, installed slot, configuration, host loading, and live task behavior remain separate proof layers.

---

## File Map

- Create `references/selfloop/policies/bootstrap-g0-v1.json`: C1 structural/integrity subset.
- Create `references/selfloop/policies/bootstrap-critical-g1-v1.json`: C1 critical behavior subset.
- Create `references/selfloop/policies/supervisor-upgrade-bridge-v1.json`: P04-only action, target-contract, and authorization-TTL constraints.
- Create `scripts/selfloop_supervisor/bootstrap_checks.py`: policy loader and immutable-root command runner.
- Create `scripts/selfloop_supervisor/bootstrap_store.py`: transactional seed attestation and pointer store.
- Create `scripts/selfloop_supervisor/seed_install.py`: immutable seed-slot materialization and verification.
- Create `scripts/selfloop_supervisor/bootstrap.py`: one-time ceremony orchestrator and recovery.
- Create `scripts/selfloop_supervisor/upgrade_bridge.py`: pinned-runtime clean-bundle verification and pending supervisor-upgrade attestation.
- Modify `scripts/selfloop_supervisor/state.py` and `projection.py`: project committed seed identities.
- Modify `scripts/selfloop_cli.py`: add `bootstrap`, `bootstrap-status`, and pinned-runtime `authorize-supervisor-upgrade`/`prepare-supervisor-upgrade` trampolines.
- Modify `scripts/validate_v2.py`: validate policy IDs, protected bundle, and C1 claim conditions.
- Create `references/selfloop/schemas/bootstrap-receipt-v1.example.json`.
- Create `references/selfloop/schemas/supervisor-upgrade-authorization-v1.example.json`.
- Create `references/selfloop/schemas/pending-supervisor-upgrade-v1.example.json`.
- Create `tests/selfloop/test_bootstrap_checks.py`, `test_bootstrap_store.py`, `test_seed_bootstrap.py`, and `test_supervisor_upgrade_bridge.py`.
- Modify `tests/selfloop/conftest.py`: bootstrap policy, record, and clean/dirty ceremony fixtures.

### Task 1: Define C1-only bootstrap check subsets

**Files:**
- Create: `references/selfloop/policies/bootstrap-g0-v1.json`
- Create: `references/selfloop/policies/bootstrap-critical-g1-v1.json`
- Create: `scripts/selfloop_supervisor/bootstrap_checks.py`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_bootstrap_checks.py`

**Interfaces:**
- Consumes: P02 `ReleaseBundleReceipt`, pinned `SupervisorBundleReceipt`, isolated profile, and explicit release configuration.
- Produces: `BootstrapPolicy`, `BootstrapCheckReceipt`, `load_bootstrap_policy(path, expected_id)`, and `BootstrapCheckRunner.run(policy, context) -> Sequence[BootstrapCheckReceipt]`.

- [ ] **Step 1: Write policy identity, immutable-cwd, and failure tests**

```python
def test_bootstrap_policies_are_not_c3_gate_policies(policy_dir):
    g0 = load_bootstrap_policy(policy_dir / "bootstrap-g0-v1.json", "bootstrap_g0.v1")
    g1 = load_bootstrap_policy(policy_dir / "bootstrap-critical-g1-v1.json", "bootstrap_critical_g1.v1")
    assert g0.conformance_stage == "C1"
    assert g1.conformance_stage == "C1"
    assert g0.receipt_schema == g1.receipt_schema == "selfloop.bootstrap-check.v1"

def test_failed_check_stops_bootstrap_check_set(check_context):
    receipts = BootstrapCheckRunner().run(check_context.policy_with_failure, check_context)
    assert receipts[-1].status == "failed"
    assert all(receipt.claimed_gate is None for receipt in receipts)
```

- [ ] **Step 2: Run tests and observe the missing check runner**

Run: `python3 -m pytest -q tests/selfloop/test_bootstrap_checks.py`

Expected: FAIL during collection.

- [ ] **Step 3: Add the exact versioned policies and runner**

`bootstrap_g0.v1` must run normalized-clean-tree, commit existence, release-manifest completeness, dependency lock, capability/permission manifests, protected-path denial policy, bundle digest, explicit local configuration, and pinned-supervisor digest checks. `bootstrap_critical_g1.v1` must run, from the immutable release root, `python3 -m compileall -q scripts`, `python3 scripts/validate_v2.py`, `python3 scripts/run_tests.py`, and `python3 -m pytest -q`, followed by P03 required critical cases, installed-hash verification, and the versioned rescue/startup canaries. Each receipt records policy digest, check ID, command or deterministic function ID, cwd, environment digest, exit code, stdout/stderr artifact hashes, start/end timestamps, and `claimedGate: null`. Add `policy_dir` and `check_context` fixtures to `tests/selfloop/conftest.py`; the failure context replaces only the compile command with `python3 -c "raise SystemExit(7)"`.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_bootstrap_checks.py`

Expected: policy tests pass and failed commands stop the subset.

```bash
git add references/selfloop/policies/bootstrap-g0-v1.json references/selfloop/policies/bootstrap-critical-g1-v1.json scripts/selfloop_supervisor/bootstrap_checks.py tests/selfloop/conftest.py tests/selfloop/test_bootstrap_checks.py
git commit -m "feat(selfloop): define C1 bootstrap checks"
```

### Task 2: Commit seed attestation and pointers transactionally

**Files:**
- Create: `scripts/selfloop_supervisor/bootstrap_store.py`
- Create: `references/selfloop/schemas/bootstrap-receipt-v1.example.json`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_bootstrap_store.py`

**Interfaces:**
- Produces: `BootstrapScope(campaign_id, generation_id)`, `BootstrapRecord` carrying the path-independent P02 release-bundle receipt digest, `BootstrapStore.reserve_scope(root_id: str, request_digest: str) -> BootstrapScope`, `commit_seed(record)`, `get_seed(root_id)`, `get_pointers(root_id)`, and `rebuild_projections(root_id)`.

- [ ] **Step 1: Write atomicity, one-time, and recovery tests**

```python
def test_seed_and_pointers_commit_together(tmp_path, bootstrap_record):
    store = BootstrapStore(tmp_path / "sips")
    store.commit_seed(bootstrap_record)
    assert store.get_seed(bootstrap_record.root_id).release_id == bootstrap_record.release_id
    pointers = store.get_pointers(bootstrap_record.root_id)
    assert pointers.active_release_id == bootstrap_record.release_id
    assert pointers.campaign_id == bootstrap_record.campaign_id
    assert pointers.generation_id == bootstrap_record.generation_id

def test_scope_is_reserved_once_and_replayed_before_effects(tmp_path):
    store = BootstrapStore(tmp_path / "sips")
    first = store.reserve_scope("root-1", "request-digest-1")
    replay = store.reserve_scope("root-1", "request-digest-1")
    assert replay == first
    assert first.campaign_id.startswith("campaign-")
    assert first.generation_id.startswith("generation-")

def test_second_distinct_seed_is_rejected(tmp_path, bootstrap_record):
    store = BootstrapStore(tmp_path / "sips")
    store.commit_seed(bootstrap_record)
    with pytest.raises(BootstrapAlreadyCompletedError):
        store.commit_seed(replace(bootstrap_record, release_id="release-other"))
```

- [ ] **Step 2: Run tests and observe the missing store**

Run: `python3 -m pytest -q tests/selfloop/test_bootstrap_store.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement one SQLite transaction and projection recovery**

Create `${SIPS_HOME}/selfloop/supervisor/bootstrap.sqlite3` with `bootstrap_scopes(root_id PRIMARY KEY, request_digest UNIQUE, campaign_id UNIQUE, generation_id UNIQUE)`, `bootstrap_attestations(root_id PRIMARY KEY, campaign_id UNIQUE, generation_id UNIQUE, request_digest UNIQUE, receipt_json)`, and `root_pointers(root_id PRIMARY KEY, campaign_id, stable_release_id, trial_release_id, active_release_id, active_slot_id, generation_id, supervisor_bundle_digest)`. `reserve_scope()` uses `BEGIN IMMEDIATE`, allocates `campaign-<uuid4 hex>` and `generation-<uuid4 hex>` once, and returns the committed row before bundle construction, evaluation, install, or another external effect. Identical request replay returns the original scope; a changed digest for that root fails closed.

`commit_seed()` uses one `BEGIN IMMEDIATE`, requires the record's campaign/generation to match the reserved scope, reopens the release/attestation pair and compares its recomputed receipt digest, and inserts the attestation plus pointer row before commit. An identical request digest returns the original receipt, while a different request for the same root fails. `rebuild_projections()` rewrites root `state.json` and `champion-pointers.json` from committed rows and never reads `state.yaml`. Define `bootstrap_record` in `tests/selfloop/conftest.py` with fixed root, request, campaign, release, release-bundle receipt, slot, generation, supervisor-bundle, policy, and receipt values.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_bootstrap_store.py`

Expected: atomicity, idempotent replay, second-seed rejection, and rebuild tests pass.

```bash
git add scripts/selfloop_supervisor/bootstrap_store.py references/selfloop/schemas/bootstrap-receipt-v1.example.json tests/selfloop/conftest.py tests/selfloop/test_bootstrap_store.py
git commit -m "feat(selfloop): transact seed attestation"
```

### Task 3: Orchestrate the clean seed ceremony and pinned supervisor activation

**Files:**
- Create: `scripts/selfloop_supervisor/seed_install.py`
- Create: `scripts/selfloop_supervisor/bootstrap.py`
- Modify: `scripts/selfloop_supervisor/state.py`
- Modify: `scripts/selfloop_supervisor/projection.py`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_seed_bootstrap.py`

**Interfaces:**
- Consumes: `RootRegistry`, `ReleaseBuilder`, `ReleaseBundleStore`, `SupervisorBundleBuilder`, `EvaluationRunner`, `BootstrapCheckRunner`, and `BootstrapStore`.
- Produces the C1/pre-ledger primitives `SeedSlotInstaller.install(release_bundle: ReleaseBundleReceipt) -> SeedSlotReceipt`, `BootstrapRequest`, and `BootstrapManager.bootstrap(request) -> BootstrapReceipt`. The receipt and committed record include the reserved campaign/generation IDs and recomputed path-independent release-bundle receipt digest. P05 imports and seals this store, then wraps bootstrap/slot mutations in a controller-issued `MutationCapability`; after migration, compatibility commands delegate through `SelfloopController.handle` and cannot invoke this primitive directly.

- [ ] **Step 1: Write clean success, dirty rejection, and failed-check tests**

```python
def test_clean_seed_bootstraps_once_without_improvement_claim(bootstrap_fixture):
    receipt = bootstrap_fixture.manager.bootstrap(bootstrap_fixture.request)
    assert receipt.schema == "selfloop.bootstrap-receipt.v1"
    assert receipt.outcome == "seed-established"
    assert receipt.improvement_claimed is False
    assert receipt.campaign_id == bootstrap_fixture.store.get_pointers(receipt.root_id).campaign_id
    assert receipt.generation_id == bootstrap_fixture.store.get_pointers(receipt.root_id).generation_id
    assert receipt.stable_release_id == receipt.active_release_id
    assert receipt.trial_release_id is None
    assert receipt.active_slot_id.startswith("slot-")
    assert receipt.seed_slot_path.parent.name == "slots"
    assert receipt.seed_slot_digest == receipt.install_payload_digest
    assert receipt.release_bundle_receipt_digest == bootstrap_fixture.release_bundle.receipt_digest
    assert receipt.conformance_stage == "C1"

def test_dirty_or_failed_seed_never_activates(bootstrap_fixture):
    bootstrap_fixture.write_operator_byte("README.md")
    with pytest.raises(DirtyReleaseError):
        bootstrap_fixture.manager.bootstrap(bootstrap_fixture.request)
    assert bootstrap_fixture.store.get_pointers(bootstrap_fixture.root_id) is None
```

- [ ] **Step 2: Run tests and observe the missing manager**

Run: `python3 -m pytest -q tests/selfloop/test_seed_bootstrap.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement the ceremony in the fixed order**

Acquire the per-root bootstrap lock; reject an existing distinct seed; compute the canonical request digest and call `BootstrapStore.reserve_scope()` before the first external effect. Verify normalized cleanliness and selected SHA; build/materialize the complete release, reopen its canonical `ReleaseBundleReceipt`, and compare the recomputed path-independent receipt digest; build the pinned supervisor only from that receipt; create an isolated seed profile; run `bootstrap_g0.v1` and the P03 required critical cases. `SeedSlotInstaller` stages the complete receipt at `${SIPS_HOME}/selfloop/slots/.<slot-id>.staging`, verifies every manifest entry and the source-attestation linkage, atomically renames it to immutable `slots/<slot-id>`, removes group/other write bits, and re-verifies the install-payload digest. Existing matching slots are verified and reused; mismatched existing slots fail without overwrite. Run `bootstrap_critical_g1.v1` and rescue/startup canaries from that immutable slot, then commit the reserved campaign/generation IDs, release-bundle receipt digest, attestation, and pointers only when every receipt passes. Use `slot-<first 24 release-digest hex>`; never allocate replacement campaign/generation IDs after scope reservation. Only after the SQLite commit, regenerate JSON projections and the live `state.yaml` marker block. Define `bootstrap_fixture` in `tests/selfloop/conftest.py` from a real clean temporary Git root and the P02/P03 fixture builders; its `write_operator_byte(path)` appends outside the generated marker.

At C1 the generated block names `conformance_stage: C1`, stable/active release IDs, null trial ID, active slot, generation, `last_foundation_check: bootstrap_critical_g1.v1`, `last_completed_gate: null`, receipt path/hash, and blocker. It preserves all non-marker bytes and states `authority: supervisor-projection-only`.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_seed_bootstrap.py tests/selfloop/test_state_projection.py`

Expected: clean fixtures establish one seed; dirty, incomplete, zero-case, failed-hash, and failed-canary fixtures leave no active pointer.

```bash
git add scripts/selfloop_supervisor/seed_install.py scripts/selfloop_supervisor/bootstrap.py scripts/selfloop_supervisor/state.py scripts/selfloop_supervisor/projection.py tests/selfloop/conftest.py tests/selfloop/test_seed_bootstrap.py
git commit -m "feat(selfloop): establish seed champion"
```

### Task 4: Attest a clean pending supervisor upgrade from the pinned P04 runtime

**Files:**
- Create: `scripts/selfloop_supervisor/upgrade_bridge.py`
- Modify: `scripts/selfloop_supervisor/bootstrap_store.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/validate_v2.py`
- Create: `references/selfloop/policies/supervisor-upgrade-bridge-v1.json`
- Create: `references/selfloop/schemas/supervisor-upgrade-authorization-v1.example.json`
- Create: `references/selfloop/schemas/pending-supervisor-upgrade-v1.example.json`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_supervisor_upgrade_bridge.py`

**Interfaces:**
- Consumes: the currently active P04 `SupervisorBundleReceipt`, registered root binding, P02 `ReleaseBuilder.assert_normalized_clean`, `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, `SupervisorBundleBuilder.build`, and the protected P04 bootstrap store.
- Produces: `SupervisorUpgradeAuthorizationReceipt`, `PendingSupervisorUpgrade`, internal `BootstrapStore.record_supervisor_upgrade_authorization(record) -> SupervisorUpgradeAuthorizationReceipt`, `BootstrapStore.record_pending_supervisor_upgrade(record, authorization_receipt_digest) -> PendingSupervisorUpgrade`, `get_pending_supervisor_upgrade(pending_upgrade_id)`, and `PinnedSupervisorUpgradeBridge.prepare(root_id: str, source_commit_sha: str, release_id: str, expected_active_bundle_digest: str, authorization_receipt_digest: str, idempotency_key: str) -> PendingSupervisorUpgrade`.
- `SupervisorUpgradeAuthorizationReceipt` records schema/action, root ID, source commit, release ID, source-attestation digest, release-manifest digest, path-independent release-bundle receipt digest, expected active P04 bundle digest, approved spec digest, bridge-policy ID/digest, a supervisor-generated nonce, issuance/expiry timestamps, immutable `decision: authorized`, and its canonical digest. It records no path, candidate bundle digest, or activation authority.
- `PendingSupervisorUpgrade` records pending ID, root ID, source release/commit/manifest/source-attestation/release-bundle-receipt digests, candidate supervisor bundle/manifest digests, expected active P04 digest, authorization receipt digest, request digest, `status: pending`, and receipt digest. It records no caller path and grants no activation authority.

- [ ] **Step 1: Write pinned-runtime, clean-bundle, idempotency, and no-activation tests**

```python
def test_pinned_p04_bridge_attests_but_does_not_activate(upgrade_fixture):
    pending = upgrade_fixture.active_bridge.prepare(
        root_id=upgrade_fixture.root_id,
        source_commit_sha=upgrade_fixture.source_commit,
        release_id=upgrade_fixture.release_bundle.release_identity.release_id,
        expected_active_bundle_digest=upgrade_fixture.active_bundle.bundle_digest,
        authorization_receipt_digest=upgrade_fixture.authorization.digest,
        idempotency_key="prepare-p05-1",
    )
    assert pending.source_attestation_digest == upgrade_fixture.release_bundle.source_attestation_digest
    assert pending.release_bundle_receipt_digest == upgrade_fixture.release_bundle.receipt_digest
    assert pending.candidate_bundle_digest != pending.expected_active_bundle_digest
    assert upgrade_fixture.store.get_pointers(upgrade_fixture.root_id).supervisor_bundle_digest == pending.expected_active_bundle_digest
    assert upgrade_fixture.active_bridge.prepare(
        root_id=upgrade_fixture.root_id,
        source_commit_sha=upgrade_fixture.source_commit,
        release_id=upgrade_fixture.release_bundle.release_identity.release_id,
        expected_active_bundle_digest=upgrade_fixture.active_bundle.bundle_digest,
        authorization_receipt_digest=upgrade_fixture.authorization.digest,
        idempotency_key="prepare-p05-1",
    ) == pending

def test_mutable_source_or_dirty_bundle_cannot_attest(upgrade_fixture):
    upgrade_fixture.write_uncommitted_source("scripts/selfloop_supervisor/kernel.py")
    with pytest.raises(PendingUpgradeDenied, match="normalized-clean"):
        upgrade_fixture.active_bridge.prepare_from_fixture("prepare-dirty")
    with pytest.raises(PendingUpgradeDenied, match="active pinned runtime required"):
        upgrade_fixture.mutable_source_bridge.prepare_from_fixture("prepare-source")

def test_authorization_is_exact_and_one_use(upgrade_fixture):
    pending = upgrade_fixture.active_bridge.prepare_from_fixture("prepare-p05-1")
    assert pending.authorization_receipt_digest == upgrade_fixture.authorization.digest
    with pytest.raises(PendingUpgradeDenied, match="authorization already bound"):
        upgrade_fixture.active_bridge.prepare_from_fixture("prepare-p05-2")

def test_expired_authorization_cannot_prepare(upgrade_fixture):
    upgrade_fixture.clock.advance(seconds=901)
    with pytest.raises(PendingUpgradeDenied, match="authorization expired"):
        upgrade_fixture.active_bridge.prepare_from_fixture("prepare-expired")
```

- [ ] **Step 2: Run and observe the missing bridge**

Run: `python3 -m pytest -q tests/selfloop/test_supervisor_upgrade_bridge.py`

Expected: collection fails with `ModuleNotFoundError: No module named 'selfloop_supervisor.upgrade_bridge'`.

- [ ] **Step 3: Implement verification and pending-only persistence**

The source-tree `selfloop_cli.py authorize-supervisor-upgrade` and `prepare-supervisor-upgrade` commands are non-authoritative trampolines: each accepts a registered root ID, resolves the active digest from protected bootstrap pointers, verifies that bundle, clears source-tree `PYTHONPATH`, and re-execs the CLI inside that exact bundle. The pinned CLI rejects execution unless `Path(__file__).resolve()` is beneath the verified active bundle. These legacy bridge operations also reject a non-P04 active-bundle schema or an existing P05 ledger; after migration, the corresponding adapter must enter the P05 controller instead of mutating `bootstrap.sqlite3`.

Load `supervisor-upgrade-bridge.v1` only from the executing pinned bundle, verify its digest, require its `sourceStage == P04`, `targetActivationContract == selfloop.controller.v2`, and fixed `authorizationTtlSeconds == 900`, and bind the approved spec digest. `authorize-supervisor-upgrade --root-id --source-commit --release-id --source-attestation-digest` derives the active bundle digest from the protected pointer, resolves and verifies the registered source root, reruns normalized cleanliness, requires the freshly computed attestation digest to equal the requested digest, and opens the exact release/attestation pair. It prints the root ID, commit, release, attestation, release-bundle receipt, manifest, active digest, policy digest, and expiry to `/dev/tty`, requires the operator to type the full source commit, and fails when `/dev/tty` is unavailable; redirected stdin, an environment variable, RPC, MCP, or candidate subprocess cannot satisfy the confirmation. The operator cannot supply or extend the expiry. Only after confirmation does the pinned runtime generate a nonce and insert the canonical authorization receipt into `supervisor_upgrade_authorizations` in `bootstrap.sqlite3`. The source trampoline never constructs, signs, or writes that receipt.

`prepare-supervisor-upgrade --root-id --source-commit --release-id --expected-active-digest --authorization-receipt-digest --idempotency-key` accepts no source-attestation override, candidate bundle path, supervisor path, module path, expiry, or activation flag. Inside the pinned runtime, resolve and verify the registered source root; require `expected_active_bundle_digest` to equal the protected pointer, executing bundle, and authorization receipt; verify the protected authorization is unexpired `supervisor-upgrade.v1` under the exact spec/policy digests for the exact root/commit/release/action; rerun P02 normalized cleanliness; and call `ReleaseBundleStore.open_verified(release_id, authorization.source_attestation_digest)`. Require its recomputed receipt digest, root, commit, manifest, and source-attestation identities to match the authorization, then build the candidate supervisor only from that receipt.

Add `supervisor_upgrade_authorizations(digest PRIMARY KEY, root_id, source_commit_sha, release_id, source_attestation_digest, release_manifest_digest, release_bundle_receipt_digest, expected_active_bundle_digest, spec_digest, bridge_policy_digest, nonce UNIQUE, issued_at, expires_at, binding_state, pending_upgrade_id, receipt_json)` and `pending_supervisor_upgrades(pending_upgrade_id PRIMARY KEY, root_id, authorization_receipt_digest UNIQUE, request_digest UNIQUE, status, receipt_json)` to the protected bootstrap database. Persist the pending row and change the authorization row's `binding_state` from `unbound` to `bound` in one `BEGIN IMMEDIATE`; the immutable authorization receipt remains `decision: authorized`. Return the original pending receipt only for the identical authorization/idempotency/request digest, and reject changed, expired, or second reuse. Do not update `root_pointers`, an active-loader file, canonical release pointers, or host configuration. P05 is the first plan permitted to consume the pending row and activate it under the canonical ledger.

- [ ] **Step 4: Run bridge, bundle, and bootstrap-store tests**

Run: `python3 -m pytest -q tests/selfloop/test_supervisor_upgrade_bridge.py tests/selfloop/test_supervisor_bundle.py tests/selfloop/test_bootstrap_store.py`

Expected: all tests pass; dirty/tampered/source-executed bridges fail; the active P04 digest is unchanged.

- [ ] **Step 5: Commit the pending-upgrade bridge**

```bash
git add scripts/selfloop_supervisor/upgrade_bridge.py scripts/selfloop_supervisor/bootstrap_store.py scripts/selfloop_cli.py scripts/validate_v2.py references/selfloop/policies/supervisor-upgrade-bridge-v1.json references/selfloop/schemas/supervisor-upgrade-authorization-v1.example.json references/selfloop/schemas/pending-supervisor-upgrade-v1.example.json tests/selfloop/conftest.py tests/selfloop/test_supervisor_upgrade_bridge.py
git commit -m "feat(selfloop): attest pending supervisor upgrades"
```

### Task 5: Expose bootstrap safely and gate C1 advertising

**Files:**
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/validate_v2.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `tests/selfloop/test_c0_adapters.py`
- Modify: `tests/test_homebase_mcp.py`

**Interfaces:**
- Produces: pre-ledger `selfloop_cli.py bootstrap --root --commit --config <json>`, read-only `bootstrap-status`, and MCP status visibility without a mutating MCP bootstrap action. Once P05 detects the canonical ledger, this same CLI syntax becomes a thin `ControllerRequest(action="bootstrap")` adapter and `bootstrap-status` reads the canonical projection rather than treating `BootstrapStore` as authority.

- [ ] **Step 1: Add CLI and adapter acceptance tests**

Assert bootstrap requires an explicit commit/config, prints the original receipt with the same supervisor-assigned campaign/generation IDs on identical replay, rejects a second seed, and reports C1 only when the receipt, bundle, pinned supervisor, campaign-bearing pointer row, and projections all agree. MCP `status` may report those proofs but `start` remains C0 agent-executed until P08.

- [ ] **Step 2: Implement commands and C1 validator conditions**

Before P05 migration, `bootstrap-status` reads only `BootstrapStore`; afterward it reads only P05's canonical ledger projection and verifies the recorded per-root import digest. The validator must reject C1 when either bootstrap policy digest differs, the supervisor path is inside the repo, installed hashes differ, the active slot is missing, the seed evaluation ran zero cases, or `last_completed_gate` is non-null. Do not expose push, publish, remote deploy, or cache overwrite behavior.

- [ ] **Step 3: Run the C1 test gate in clean temporary repositories**

Run: `python3 -m pytest -q tests/selfloop tests/test_homebase_mcp.py && python3 scripts/run_tests.py && python3 scripts/validate_v2.py && git diff --check`

Expected: all commands exit 0; the acceptance test for scenario 21 passes; test fixtures advertise C1 only after a campaign-bearing seed receipt; pending-upgrade fixtures leave the active P04 pointer unchanged.

- [ ] **Step 4: Confirm the current checkout is not eligible for a real ceremony while it remains dirty**

Run: `git status --short`

Expected on the current checkout at plan-writing time: nonempty output, so no real bootstrap command is authorized. The clean-repository acceptance fixture above proves the success path; run the real ceremony only after a cohesive release commit and an empty normalized-clean check.

- [ ] **Step 5: Commit the bootstrap surface**

```bash
git add scripts/selfloop_cli.py scripts/validate_v2.py scripts/harness_homebase_mcp.py tests/selfloop/test_c0_adapters.py tests/test_homebase_mcp.py
git commit -m "feat(selfloop): expose verified C1 bootstrap"
```
