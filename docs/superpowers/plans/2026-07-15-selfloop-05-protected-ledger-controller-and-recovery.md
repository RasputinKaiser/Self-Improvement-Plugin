# Protected Ledger, Controller, and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the protected C2 controller foundation: a root-scoped SQLite event ledger, externally anchored head, deterministic projections, policy enforcement, idempotent transitions, locking, and crash recovery.

**Architecture:** Authoritative code lives in `scripts/selfloop_supervisor/`; each supervisor release is copied into a new digest-named immutable bundle below `${SIPS_HOME}/selfloop/supervisor/bundles/`, and an operator-authorized ledger pointer selects the one active bundle. Runtime dispatch always loads that activated bundle, never a candidate worktree or mutable source tree, while prior bundles remain available for rescue. One protected SQLite database owns events, materialized state, pointers, grants, locks, and intended actions; a separately atomically written anchored-head file detects truncation or rehashing. Candidate-evolvable code in `scripts/selfloop_strategy/` may communicate only through schema-validated JSON subprocess requests and cannot write supervisor state.

**Tech Stack:** Python 3.10+, standard-library `sqlite3`, `hashlib`, `json`, `fcntl`, `pathlib`, `subprocess`, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- Preserve `homebase.selfloop.v1` as compatibility-only; this plan does not advertise C2 experiment conformance.
- Canonical state is `${SIPS_HOME:-~/.codex/sips}/selfloop/supervisor/state.sqlite3`; the protected external anchor is `ledger-head.json` beside it.
- Every mutation requires explicit `rootId`, explicit `campaignId`, a unique idempotency key, `BEGIN IMMEDIATE`, and an append-only event. Root, campaign, idempotency key, type, and canonical payload are all covered by the event digest.
- `ControllerRequest.parse_v2()` is the single CLI/MCP parser. It dispatches by a shared `ControllerAction` enum to exact action-specific payload types; it rejects missing and unknown fields. Read-only `status` rejects an idempotency key, while every mutating action requires one.
- A low-level mutator may run only with a controller-issued `MutationCapability` derived from the current lock-owning `MutationSession`. Supervisor stage/activate, budget grant/reconcile/reserve/release, and P08 worktree create/commit/remove all bind their phase idempotency keys to that session; public helpers never mint capabilities.
- P04 `bootstrap.sqlite3` and P01 JSON state are C1 inputs, not parallel C2 authorities. Import the attested seed and pointers once into the canonical ledger, record their source digests, then treat the C1 stores as read-only compatibility projections.
- Corruption is never treated as an absent campaign. Anchor mismatch, sequence gaps, or digest mismatch fail closed.
- Only the marker-delimited `state.yaml` runtime block is supervisor-generated and non-authoritative; all bytes outside it are preserved exactly.
- Release identity normalizes the runtime block, while the actual rendered block SHA-256 is recorded separately as `stateProjectionDigest`.
- `local-auto-v1` permits only registered local SIPS install operations and denies push, publish, message, purchase, and remote deployment.
- Research subprocesses require a tested OS isolation provider that grants read access only to the active release and write access only to the candidate worktree while denying supervisor, anchor, sealed, credential, and sibling-worktree paths; no provider means fail closed.
- Tests use temporary `SIPS_HOME` and never touch the live plugin, cache, config, or supervisor store.
- The canonical P02 protected-bundle handle is `SupervisorBundleReceipt.bundle_digest`; its path is re-resolved as `${SIPS_HOME}/selfloop/supervisor/bundles/<bundle_digest>` and rehashed before use. Rollover staging consumes a verified P02 `ReleaseBundleReceipt` byte handle with its path-independent `receipt_digest`, never a `ReleaseIdentity` or caller path alone.

---

### Task 1: Create the canonical SQLite ledger and anchored head

**Files:**
- Create: `scripts/selfloop_supervisor/ledger.py`
- Modify: `scripts/selfloop_supervisor/bootstrap_store.py`
- Modify: `scripts/selfloop_supervisor/bootstrap.py`
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Modify: `scripts/selfloop_supervisor/paths.py`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_ledger.py`

**Interfaces:**
- Consumes: P01 `RootBinding.root_id`/`SelfloopPaths`, P04 `BootstrapStore`, and its attested seed/pointers.
- Produces: `Ledger.open(sips_home: Path, bootstrap_store: BootstrapStore | None = None)`, `Ledger.append(root_id: str, campaign_id: str, event_type: str, payload: Mapping[str, Any], idempotency_key: str) -> EventRecord`, `Ledger.receipt_for_idempotency_key(root_id: str, campaign_id: str, idempotency_key: str) -> EventRecord | None`, `Ledger.record_intent(root_id: str, campaign_id: str, operation: str, payload: Mapping[str, Any], idempotency_key: str) -> IntentRecord`, `Ledger.commit_receipt(root_id: str, campaign_id: str, intent_id: str, event_type: str, payload: Mapping[str, Any], idempotency_key: str) -> EventRecord`, `Ledger.verify() -> LedgerHead`, `Ledger.rebuild(root_id: str) -> dict[str, Any]`, `LegacyBootstrapImporter.import_and_seal(store: BootstrapStore, ledger: Ledger) -> BootstrapMigrationReceipt`, and canonical `LedgerBootstrapStore.commit_seed(record: BootstrapRecord) -> BootstrapRecord` for all post-migration bootstraps. Later gate/install plans build typed repositories over the three generic journal methods rather than inventing incompatible ledger signatures.

- [ ] **Step 1: Write the failing sequence, replay, and tamper tests**

```python
def test_append_is_idempotent_and_anchor_detects_truncation(tmp_path):
    ledger = Ledger.open(tmp_path)
    first = ledger.append("root-1", "campaign-1", "campaign.started", {"focus": "eval"}, "start-1")
    replay = ledger.append("root-1", "campaign-1", "campaign.started", {"focus": "eval"}, "start-1")
    assert replay == first
    assert ledger.verify().sequence == 1
    with ledger.connection:
        ledger.connection.execute("DELETE FROM events WHERE sequence = 1")
    with pytest.raises(LedgerCorruption, match="anchored head does not match"):
        ledger.verify()

def test_attested_c1_seed_is_imported_once(tmp_path, committed_bootstrap_store):
    ledger = Ledger.open(tmp_path, bootstrap_store=committed_bootstrap_store)
    assert ledger.root_pointers("root-1").stable_release_id == "release-seed"
    imported = ledger.last_event("root-1", "bootstrap.imported")
    expected = LegacyBootstrapImporter.inspect_root(committed_bootstrap_store, "root-1")
    assert imported.payload["legacyRootDigest"] == expected.root_digest
    assert imported.payload["seedReceiptDigest"] == expected.seed_receipt_digest
    assert ledger.count("bootstrap.imported") == 1
    assert Ledger.open(tmp_path, bootstrap_store=committed_bootstrap_store).count("bootstrap.imported") == 1

def test_conflicting_bootstrap_after_import_fails_closed(tmp_path, committed_bootstrap_store, bootstrap_tamper):
    Ledger.open(tmp_path, bootstrap_store=committed_bootstrap_store)
    bootstrap_tamper.replace_seed_release(committed_bootstrap_store, "root-1", "release-conflict")
    with pytest.raises(LedgerCorruption, match="bootstrap source digest changed"):
        Ledger.open(tmp_path, bootstrap_store=committed_bootstrap_store)

def test_two_legacy_roots_import_independently_then_store_is_sealed(
    tmp_path, two_root_bootstrap_store,
):
    ledger = Ledger.open(tmp_path, bootstrap_store=two_root_bootstrap_store)
    assert ledger.root_pointers("root-1").stable_release_id == "release-seed-1"
    assert ledger.root_pointers("root-2").stable_release_id == "release-seed-2"
    assert ledger.count("bootstrap.imported") == 2
    assert two_root_bootstrap_store.is_sealed()

def test_new_root_bootstrap_after_migration_writes_canonical_ledger(tmp_path, bootstrap_record_3):
    ledger = Ledger.open(tmp_path)
    canonical = LedgerBootstrapStore(ledger)
    canonical.commit_seed(bootstrap_record_3)
    assert ledger.root_pointers("root-3").stable_release_id == bootstrap_record_3.release_id
    assert ledger.count("bootstrap.established") == 1

def test_reused_idempotency_key_with_changed_event_is_rejected(tmp_path):
    ledger = Ledger.open(tmp_path)
    ledger.append("root-1", "campaign-1", "campaign.started", {"focus": "a"}, "same-key")
    with pytest.raises(IdempotencyConflict):
        ledger.append("root-1", "campaign-1", "campaign.started", {"focus": "b"}, "same-key")

def test_intent_and_terminal_receipt_are_campaign_scoped_and_replayable(tmp_path):
    ledger = Ledger.open(tmp_path)
    intent = ledger.record_intent(
        "root-1", "campaign-1", "paired-evaluation", {"jobId": "job-1"}, "intent-1",
    )
    terminal = ledger.commit_receipt(
        "root-1", "campaign-1", intent.intent_id, "evaluation.completed",
        {"artifactDigest": "sha256:raw-1"}, "terminal-1",
    )
    assert ledger.receipt_for_idempotency_key("root-1", "campaign-1", "terminal-1") == terminal
    assert ledger.receipt_for_idempotency_key("root-1", "campaign-2", "terminal-1") is None
```

- [ ] **Step 2: Run the test and confirm the missing-module failure**

Run: `python3 -m pytest -q tests/selfloop/test_ledger.py`

Expected: collection fails with `ModuleNotFoundError: No module named 'selfloop_supervisor.ledger'`.

- [ ] **Step 3: Implement schema creation, digest chaining, one-time bootstrap import, idempotency, and atomic anchor writes**

```python
def event_digest(previous, sequence, root_id, campaign_id, event_type, payload_json, idempotency_key):
    body = canonical_json({
        "previous": previous, "sequence": sequence, "rootId": root_id,
        "campaignId": campaign_id, "eventType": event_type,
        "payload": json.loads(payload_json), "idempotencyKey": idempotency_key,
    })
    return hashlib.sha256(body).hexdigest()

def append(self, root_id, campaign_id, event_type, payload, idempotency_key):
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    self.connection.execute("BEGIN IMMEDIATE")
    prior = self._event_for_key(root_id, idempotency_key)
    if prior is not None:
        if prior.campaign_id != campaign_id or prior.event_type != event_type or prior.payload_json != payload_json:
            self.connection.rollback()
            raise IdempotencyConflict(idempotency_key)
        self.connection.rollback()
        return prior
    head = self._database_head()
    sequence = head.sequence + 1
    digest = event_digest(head.digest, sequence, root_id, campaign_id, event_type, payload_json, idempotency_key)
    self.connection.execute(
        "INSERT INTO events(sequence, root_id, campaign_id, event_type, payload_json, previous_digest, digest, idempotency_key) VALUES(?,?,?,?,?,?,?,?)",
        (sequence, root_id, campaign_id, event_type, payload_json, head.digest, digest, idempotency_key),
    )
    self.connection.execute("INSERT OR REPLACE INTO pending_anchor(id, sequence, digest) VALUES(1,?,?)", (sequence, digest))
    self.connection.commit()
    self._write_anchor_atomic(LedgerHead(sequence=sequence, digest=digest))
    self.connection.execute("DELETE FROM pending_anchor WHERE id=1")
    self.connection.commit()
    return self._event_by_sequence(sequence)
```

When a legacy P04 store exists, enumerate every attested root in one consistent read transaction. For each root, hash only its seed attestation plus pointer row, verify release/slot/supervisor/policy/receipt identities, and import a missing canonical root plus `bootstrap.imported` atomically. Existing imported roots must match their recorded per-root digest. After all rows import, seal the legacy database read-only and append one `bootstrap.migration.sealed` event containing the final whole-store audit digest. The seal prevents a later legitimate-looking row from appearing outside authority. Reconfigure P04 `BootstrapManager` to use `LedgerBootstrapStore` whenever the canonical ledger exists, so new roots append `bootstrap.established` and pointers directly to the ledger. Legacy JSON helpers become read-only projections rebuilt from canonical state.

- [ ] **Step 4: Prove normal replay, conflicting-key rejection, per-root bootstrap migration, sequence gaps, root/campaign/idempotency/payload tampering, tail truncation, and recoverable pending-anchor cases**

Run: `python3 -m pytest -q tests/selfloop/test_ledger.py`

Expected: all ledger and migration cases pass and pytest exits `0`.

- [ ] **Step 5: Commit the ledger boundary**

```bash
git add scripts/selfloop_supervisor/ledger.py scripts/selfloop_supervisor/bootstrap_store.py scripts/selfloop_supervisor/bootstrap.py scripts/selfloop_supervisor/contracts.py scripts/selfloop_supervisor/paths.py tests/selfloop/conftest.py tests/selfloop/test_ledger.py
git commit -m "feat(selfloop): add protected anchored event ledger"
```

### Task 2: Materialize root state and enforce one mutating lock

**Files:**
- Create: `scripts/selfloop_supervisor/materialized_state.py`
- Create: `scripts/selfloop_supervisor/locking.py`
- Test: `tests/selfloop/test_controller_state.py`

**Interfaces:**
- Consumes: `Ledger.append(root_id, campaign_id, event_type, payload, idempotency_key) -> EventRecord` and P01 `RootStateStore` migration input.
- Produces: `StateStore.load(root_id: str) -> CampaignState`, `StateStore.apply(event: EventRecord) -> CampaignState`, `StateStore.stable_champion(root_id: str) -> ChampionPointer`, and `RootLock.acquire(root_id: str, owner_id: str, lease_seconds: int) -> LockReceipt`. `stable_champion` is derived only from verified canonical pointer events and returns release ID, slot ID, commit SHA, and manifest digest.

- [ ] **Step 1: Write failing tests for root isolation, legal transitions, and lock exclusion**

```python
def test_roots_are_isolated_and_second_writer_is_rejected(store, locks):
    store.apply(event("root-a", "campaign.started", campaignId="campaign-a"))
    assert store.load("root-a").campaign_id == "campaign-a"
    assert store.load("root-b").status == "idle"
    locks.acquire("root-a", "worker-1", 30)
    with pytest.raises(ControllerBusy, match="root-a"):
        locks.acquire("root-a", "worker-2", 30)
```

- [ ] **Step 2: Run and observe the red state**

Run: `python3 -m pytest -q tests/selfloop/test_controller_state.py`

Expected: collection fails because `materialized_state` and `locking` do not exist.

- [ ] **Step 3: Implement explicit transition tables and SQLite-backed leases**

```python
ALLOWED = {
    "idle": {"preparing", "complete"},
    "preparing": {"running", "paused", "failed", "aborted"},
    "running": {"evaluating", "paused", "failed", "aborted"},
    "evaluating": {"running", "promotable", "paused", "failed", "aborted"},
    "promotable": {"probation", "running", "aborted"},
    "probation": {"running", "complete", "failed"},
    "paused": {"preparing", "running", "evaluating", "aborted"},
}

def require_transition(before: str, after: str) -> None:
    if after not in ALLOWED.get(before, set()):
        raise InvalidTransition(f"{before} -> {after}")
```

- [ ] **Step 4: Run focused state and lock tests**

Run: `python3 -m pytest -q tests/selfloop/test_controller_state.py`

Expected: `8 passed`.

- [ ] **Step 5: Commit state materialization and locking**

```bash
git add scripts/selfloop_supervisor/materialized_state.py scripts/selfloop_supervisor/locking.py tests/selfloop/test_controller_state.py
git commit -m "feat(selfloop): materialize root state with writer locks"
```

### Task 3: Enforce immutable supervisor runtime and JSON strategy boundary

**Files:**
- Modify: `scripts/selfloop_supervisor/supervisor_bundle.py`
- Modify: `scripts/selfloop_supervisor/restricted_process.py`
- Create: `scripts/selfloop_strategy/worker.py`
- Create: `scripts/selfloop_supervisor/strategy_rpc.py`
- Test: `tests/selfloop/test_strategy_boundary.py`

**Interfaces:**
- Consumes: P02 `SupervisorBundleBuilder.build(release_bundle) -> SupervisorBundleReceipt`.
- Consumes: P03 `RestrictedProcessLauncher.run(command, cwd, readable_roots, writable_roots, denied_roots, environment, limits, input_text=None) -> ProcessReceipt` and `ProcessLimits`.
- Produces: a backward-compatible `RestrictedProcessLauncher.run(command: Sequence[str], cwd: Path, readable_roots: Sequence[Path], writable_roots: Sequence[Path], denied_roots: Sequence[Path], environment: Mapping[str, str], limits: ProcessLimits, input_text: str | None = None) -> ProcessReceipt`, `StrategyOperationPolicy.authorize(operation: str, runtime_root: Path, artifact_inputs: Sequence[Path]) -> StrategyCapability`, `StrategyClient(bundle: SupervisorBundleReceipt, launcher: RestrictedProcessLauncher, timeout_seconds: int)`, `StrategyClient.call_with_receipt(operation: str, runtime_root: Path, request: Mapping[str, Any], artifact_inputs: Sequence[Path] = ()) -> StrategyCallReceipt`, and the convenience `StrategyClient.call(operation: str, runtime_root: Path, request: Mapping[str, Any], artifact_inputs: Sequence[Path] = ()) -> Mapping[str, Any]` returning only `StrategyCallReceipt.payload`.
- `StrategyCallReceipt` carries `status`, optional validated `payload`, `process_receipt: ProcessReceipt`, and structured `error`; derived accessors expose exit/timeout, elapsed time, observed tool calls, input/output byte counts, sandbox policy digest, and artifact digest. `call_with_receipt` never raises before returning this receipt, even on process/schema failure. The caller must reconcile its grant and then call `receipt.require_success()`. It never trusts a strategy-reported token count as authoritative usage.
- `StrategyCapability` is selected by the pinned operation policy, never caller paths. Read-only operations (`compile-evidence`, `build-idea-prompt`, `finalize-idea-pack`, `propose-lineages`, `select-card`) can read only the immutable strategy runtime plus supervisor-validated content-addressed artifact inputs and write only a fresh disposable scratch directory; they cannot write the release/runtime root. P08's builder broker owns the separate candidate-worktree write capability.
- JSON request requires `schema`, `rootId`, `campaignId`, `generationId`, `operation`, and `grant`; responses reject unknown fields and never carry paths to sealed or supervisor state.

- [ ] **Step 1: Write failing pinning, schema, environment, and write-denial tests**

```python
def test_strategy_runs_out_of_process_without_supervisor_paths(tmp_path, fake_strategy, restricted_launcher):
    client = StrategyClient(fake_strategy.bundle, launcher=restricted_launcher, timeout_seconds=5)
    response = client.call("select-card", fake_strategy.candidate, {
        "schema": "selfloop.strategy-request.v1",
        "rootId": "root-1", "campaignId": "campaign-1", "generationId": "generation-1",
        "operation": "select-card", "grant": {"grantId": "grant-1", "reservedTokens": 1000},
    })
    assert response["schema"] == "selfloop.strategy-response.v1"
    assert "SIPS_HOME" not in response["observedEnv"]
    assert "supervisorPath" not in response
    assert response["anchorRead"] == "denied"
```

- [ ] **Step 2: Run and confirm the boundary is absent**

Run: `python3 -m pytest -q tests/selfloop/test_strategy_boundary.py`

Expected: collection fails with missing `strategy_rpc`.

- [ ] **Step 3: Implement digest-named read-only bundles and strict subprocess JSON**

```python
completed = self.launcher.run(
    command=(sys.executable, "-m", "selfloop_strategy.worker"),
    cwd=runtime_root,
    readable_roots=(runtime_root, *capability.readable_artifacts),
    writable_roots=(capability.scratch_root,),
    denied_roots=(self.bundle.path.parent, self.ledger_path.parent, *self.sealed_roots),
    environment={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(runtime_root / "scripts"),
                 "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(capability.scratch_root)},
    limits=capability.process_limits,
    input_text=json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n",
)
error = None
response = None
if completed.exit_code == 0:
    try:
        response = json.loads(completed.stdout)
        validate_strategy_response(response)
    except (ValueError, StrategySchemaError) as exc:
        error = StrategyError.from_exception(exc)
else:
    error = StrategyError("process_failed", completed.stderr.strip())
return StrategyCallReceipt.from_process(completed, payload=response, error=error)
```

Resolve `capability = operation_policy.authorize(...)` before launch. Validate every artifact input against its content digest and operation-specific allowlist; reject raw paths in strategy JSON. Create scratch with mode `0700`, seal its artifacts after the call, and delete it on terminal reconciliation. Add tests proving selection/evidence cannot modify the runtime root, an unlisted artifact is unreadable, and a listed content-addressed artifact is readable.

- [ ] **Step 4: Run boundary tests**

Run: `python3 -m pytest -q tests/selfloop/test_strategy_boundary.py`

Expected: `7 passed`.

- [ ] **Step 5: Commit the protected runtime boundary**

```bash
git add scripts/selfloop_supervisor/supervisor_bundle.py scripts/selfloop_supervisor/restricted_process.py scripts/selfloop_strategy/worker.py scripts/selfloop_supervisor/strategy_rpc.py tests/selfloop/test_strategy_boundary.py
git commit -m "feat(selfloop): isolate strategy behind pinned supervisor RPC"
```

### Task 4: Add policy, controller actions, and deterministic recovery

**Files:**
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Create: `scripts/selfloop_supervisor/controller_requests.py`
- Modify: `scripts/selfloop_supervisor/bootstrap.py`
- Modify: `scripts/selfloop_supervisor/snapshot.py`
- Modify: `scripts/selfloop_supervisor/supervisor_bundle.py`
- Create: `scripts/selfloop_supervisor/budget.py`
- Create: `scripts/selfloop_supervisor/policy.py`
- Create: `scripts/selfloop_supervisor/process_registry.py`
- Create: `scripts/selfloop_supervisor/process_trampoline.py`
- Create: `scripts/selfloop_supervisor/kernel.py`
- Create: `scripts/selfloop_supervisor/recovery.py`
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Test: `tests/selfloop/test_controller_requests.py`
- Test: `tests/selfloop/test_budget_boundary.py`
- Test: `tests/selfloop/test_recovery.py`
- Test: `tests/selfloop/test_mutation_routing.py`

**Interfaces:**
- Keep P00's broad dataclass private to `V1RequestAdapter`; do not extend it. Produce shared `ControllerAction(str, Enum)` with `BOOTSTRAP`, `SNAPSHOT`, `RESTORE`, `AUTHORIZE_SUPERVISOR_UPGRADE`, `PREPARE_SUPERVISOR_UPGRADE`, `ACTIVATE_SUPERVISOR`, `START`, `ADVANCE`, `STATUS`, `PAUSE`, `RESUME`, `ABORT`, `STOP`, `COMPLETE`, `CLEAR`, `RECORD`, and `ROLLBACK`, plus `ControllerRequest.parse_v2(arguments: Mapping[str, Any]) -> ControllerRequest`.
- `ControllerRequest.payload` is the closed union `BootstrapPayload | SnapshotPayload | RestorePayload | AuthorizeSupervisorUpgradePayload | PrepareSupervisorUpgradePayload | ActivateSupervisorPayload | StartPayload | AdvancePayload | StatusPayload | PausePayload | ResumePayload | AbortPayload | StopPayload | CompletePayload | ClearPayload | RecordPayload | RollbackPayload`. The exact action fields are: `bootstrap={source_commit, config}`, `snapshot={label?}`, `restore={snapshot_id}`, `authorize-supervisor-upgrade={source_commit, release_id, source_attestation_digest}`, `prepare-supervisor-upgrade={authorization_receipt_digest, expected_prior_digest}`, `activate-supervisor={pending_upgrade_id, expected_prior_digest}`, `start={focus, budget_profile}`, `advance={}`, `status={}`, `pause={}`, `resume={}`, `abort={}`, `stop={}`, `complete={}`, `clear={}`, `record={experiment_id, terminal_experiment_event_digest}`, and `rollback={promotion_id?}`. Braces denote the complete allowed set; `?` marks the only optional fields. `budget_profile` is `standard|deep`; rollback without an ID resolves the unique current eligible trial and journals the resolved promotion ID/reason before effect.
- Each action payload is a separate frozen dataclass with those required/optional fields and an exact parser. `STATUS` has `idempotency_key is None` and rejects one; every other action requires a nonempty key. `authorize-supervisor-upgrade` is CLI/direct-TTY only, re-executes inside the active pinned bundle, verifies the controller-injected TTY dependency, and persists a `SupervisorUpgradeAuthorizationReceipt`; MCP and non-TTY callers are denied. `prepare-supervisor-upgrade` accepts only that receipt digest and persists `PendingSupervisorUpgrade`. `activate-supervisor` accepts only a pending ID; inside `handle`, a session/capability-gated resolver loads its canonical event or verifies/imports the P04 row. V2 `record` derives outcome/summary from the protected final experiment event; free text remains v1 compatibility data only.
- Produces `MutationSession(root_id, campaign_id, intent_id, request_idempotency_key, lock_owner, authorization_digest, nonce)` and `MutationSession.issue(operation: MutationOperation, resource_id: str, phase: str) -> MutationCapability`. A capability carries the session digest, exact operation/resource, deterministic phase key, single-use nonce, and `idempotency_key = f"{request_idempotency_key}:{phase}"`; only `SelfloopController.handle` can construct a session.
- Produces: `SelfloopController.handle(request: ControllerRequest) -> ControllerResponse`, `Policy.authorize(action: ControllerAction, policy_id: str) -> AuthorizationReceipt`, `BudgetMeter.authorize(request: UsageRequest, capability: MutationCapability) -> BudgetGrant`, `BudgetMeter.reconcile(grant_id: str, usage: UsageReceipt, capability: MutationCapability) -> BudgetReceipt`, `ProcessRegistry.launch(scope: ObjectScope, intent_id: str, spec: ProcessLaunchSpec, capability: MutationCapability) -> RegisteredProcessReceipt`, `reconcile_launch(process_id: str, capability: MutationCapability) -> RegisteredProcessReceipt`, `await_terminal(process_id: str, capability: MutationCapability) -> TerminalProcessReceipt`, `terminate(process_id: str, capability: MutationCapability) -> ProcessTerminationReceipt`, `archive(process_id: str, capability: MutationCapability) -> ProcessArchiveReceipt`, and `RecoveryManager.resume(root_id: str) -> RecoveryReceipt`. Raw `Popen` registration is private and recovery-only; every persisted bind, terminal, termination, or archive transition consumes the exact current-session capability.
- `ProcessRegistry.launch` allocates process/output/handshake IDs and persists `process.launch.intended` before spawn. A protected trampoline creates a new process group and atomically writes PID, PGID, executable digest, and OS start token to the predeclared handshake before `exec`; the registry then persists `process.started`. A crash between spawn and binding is recovered from that handshake. PID reuse is rejected by start-token mismatch, and restart reconciles intended, live, exited, and orphaned rows before resuming.
- `handle` is the only adapter-facing mutation entry after the canonical ledger exists. CLI and MCP both call `ControllerRequest.parse_v2`; they never build requests with action-specific optional fields. Low-level P02/P04 helpers, budget methods, runtime staging, and later P08 worktree methods require the exact session capability. Read-only status verifies the ledger without taking the root mutation lock.
- `BudgetGrant` carries `grant_id`, `root_id`, `campaign_id`, `category`, `purpose`, `reserved_tokens`, `tool_call_cap`, and `expires_at`; it is ledger-backed and single-use. `authorize` appends `budget.granted`; `reconcile` always appends a terminal `budget.reconciled` receipt, including failed or unknown-usage calls, before returning or raising.
- `start`, open-ended `resume`, and bare `advance` remain C1/foundation-only until Plan 08 can produce a terminal experiment receipt. V2 `stop`, `abort`, and `clear` share the evidence-preserving abort path; P00 v1 bytes and its legacy `stop -> clear` translation remain frozen behind `V1RequestAdapter`.

- [ ] **Step 1: Write failing typed-request, capability, process-registry, replay, and abort tests**

```python
def test_v2_requests_are_action_discriminated_and_status_has_no_idempotency():
    status = ControllerRequest.parse_v2({"action": "status", "root": "/repo"})
    assert status.action is ControllerAction.STATUS
    assert isinstance(status.payload, StatusPayload)
    assert status.idempotency_key is None
    with pytest.raises(RequestSchemaError, match="idempotency_key is not allowed for status"):
        ControllerRequest.parse_v2({"action": "status", "root": "/repo", "idempotency_key": "x"})
    with pytest.raises(RequestSchemaError, match="unknown field: summary"):
        ControllerRequest.parse_v2({
            "action": "advance", "root": "/repo", "idempotency_key": "a-1", "summary": "free text",
        })
    for action in ("stop", "clear"):
        parsed = ControllerRequest.parse_v2({"action": action, "root": "/repo", "idempotency_key": f"{action}-1"})
        assert parsed.action.value == action

def test_mutating_request_requires_key_and_capability_is_session_scoped(controller, snapshot_manager):
    with pytest.raises(RequestSchemaError, match="idempotency_key is required"):
        ControllerRequest.parse_v2({"action": "restore", "root": "/repo", "snapshot_id": "snapshot-1"})
    session = controller.session_for_test("restore-1")
    capability = session.issue(MutationOperation.SNAPSHOT_RESTORE, "snapshot-1", "restore")
    snapshot_manager.restore("snapshot-1", capability=capability)
    with pytest.raises(MutationDenied, match="operation or session mismatch"):
        snapshot_manager.restore(
            "snapshot-2", capability=session.issue(MutationOperation.BUDGET_GRANT, "snapshot-2", "wrong"),
        )

def test_process_registry_journals_before_spawn_and_rejects_pid_reuse(registry_factory, child_spec):
    first = registry_factory()
    row = first.launch(scope(), "intent-1", child_spec, process_capability("launch-child"))
    assert first.ledger.event_sequence("process.launch.intended") < first.ledger.event_sequence("process.started")
    reopened = registry_factory()
    assert reopened.get(row.process_id).start_token == row.start_token
    child_spec.replace_start_token(row.pid, "different-boot-or-process")
    assert reopened.reconcile_launch(
        row.process_id, process_capability("reconcile-child", operation="PROCESS_RECONCILE"),
    ).status == "pid-reused"

def test_crash_after_spawn_before_bind_recovers_handshake_before_unlock(registry_factory, child_spec):
    first = registry_factory(crash_after="spawn-before-bind")
    with pytest.raises(SimulatedCrash):
        first.launch(scope(), "intent-crash", child_spec, process_capability("launch-crash"))
    process_id = first.ledger.last_event("root-1", "process.launch.intended").payload["processId"]
    reopened = registry_factory()
    bound = reopened.reconcile_launch(
        process_id, process_capability("bind-crash", operation="PROCESS_RECONCILE"),
    )
    assert bound.pid and bound.process_group and bound.start_token
    assert reopened.lock_for("root-1").held is True
    reopened.terminate(
        process_id, process_capability("terminate-crash", operation="PROCESS_TERMINATE"),
    )
    reopened.await_terminal(
        process_id, process_capability("terminal-crash", operation="PROCESS_RECONCILE"),
    )
    assert reopened.release_root_lock("root-1").status == "released"

@pytest.mark.parametrize("action", ["push", "publish", "message", "purchase", "remote-deploy"])
def test_local_auto_policy_denies_external_actions(policy, action):
    with pytest.raises(AuthorizationDenied, match=action):
        policy.authorize(action, "local-auto-v1")

def test_unknown_usage_is_denied_before_provider_call(meter, fake_provider):
    with pytest.raises(BudgetDenied, match="conservative enforceable bound required"):
        meter.authorize(UsageRequest(
            root_id="root-1", campaign_id="campaign-1", category="proposal",
            purpose="idea-pack", estimated_tokens=None, output_cap=None, tool_call_cap=None,
        ), budget_capability("grant:idea-pack"))
    assert fake_provider.calls == []

def test_failed_granted_call_persists_full_charge_before_raise(meter):
    grant = meter.authorize(UsageRequest(
        root_id="root-1", campaign_id="campaign-1", category="proposal",
        purpose="idea-pack", estimated_tokens=700, output_cap=300, tool_call_cap=0,
    ), budget_capability("grant:idea-pack"))
    receipt = meter.reconcile(
        grant.grant_id, UsageReceipt(status="failed", actual_tokens=None, tool_calls=0),
        budget_capability("reconcile:idea-pack"),
    )
    assert receipt.charged_tokens == grant.reserved_tokens
    assert meter.ledger.last_event("root-1", "budget.reconciled").payload["receiptId"] == receipt.receipt_id

def test_legacy_bootstrap_and_restore_adapters_route_through_controller(
    canonical_home, legacy_cli, recording_controller,
):
    legacy_cli.bootstrap(root="/repo", idempotency_key="bootstrap-1")
    legacy_cli.restore(root="/repo", snapshot_id="snapshot-1", idempotency_key="restore-1")
    assert [request.action for request in recording_controller.requests] == ["bootstrap", "restore"]
    assert all(request.idempotency_key for request in recording_controller.requests)

def test_low_level_restore_rejects_missing_controller_capability(snapshot_manager):
    with pytest.raises(MutationDenied, match="controller capability required"):
        snapshot_manager.restore("snapshot-1", capability=None)

def test_abort_releases_lock_last_and_replays_each_phase_once(controller, long_running_child):
    controller.start_for_test(long_running_child)
    first = controller.handle(v2_request("abort", "abort-1"))
    replay = controller.handle(v2_request("abort", "abort-1"))
    assert replay.receipt == first.receipt
    assert controller.ledger.ordered_types("abort-1") == [
        "abort.intent", "process.terminated", "abort.evidence.archived",
        "campaign.aborted", "worktree.removed", "root.lock.released",
    ]
```

- [ ] **Step 2: Run and verify recovery and budget enforcement are red**

Run: `python3 -m pytest -q tests/selfloop/test_controller_requests.py tests/selfloop/test_budget_boundary.py tests/selfloop/test_recovery.py tests/selfloop/test_mutation_routing.py`

Expected: collection fails with missing `controller_requests`, `budget`, `process_registry`, and `recovery`; mutation-routing assertions also fail because legacy helpers still mutate directly.

- [ ] **Step 3: Implement typed parsing, session-bound phases, durable child tracking, terminal failure, and unlock-last abort**

```python
PAYLOAD_BY_ACTION = {
    ControllerAction.BOOTSTRAP: BootstrapPayload,
    ControllerAction.SNAPSHOT: SnapshotPayload,
    ControllerAction.RESTORE: RestorePayload,
    ControllerAction.AUTHORIZE_SUPERVISOR_UPGRADE: AuthorizeSupervisorUpgradePayload,
    ControllerAction.PREPARE_SUPERVISOR_UPGRADE: PrepareSupervisorUpgradePayload,
    ControllerAction.ACTIVATE_SUPERVISOR: ActivateSupervisorPayload,
    ControllerAction.START: StartPayload,
    ControllerAction.ADVANCE: AdvancePayload,
    ControllerAction.STATUS: StatusPayload,
    ControllerAction.PAUSE: PausePayload,
    ControllerAction.RESUME: ResumePayload,
    ControllerAction.ABORT: AbortPayload,
    ControllerAction.STOP: StopPayload,
    ControllerAction.COMPLETE: CompletePayload,
    ControllerAction.CLEAR: ClearPayload,
    ControllerAction.RECORD: RecordPayload,
    ControllerAction.ROLLBACK: RollbackPayload,
}

@classmethod
def parse_v2(cls, arguments):
    action = ControllerAction(require_string(arguments, "action"))
    payload = PAYLOAD_BY_ACTION[action].parse_exact(arguments, common={"action", "root", "idempotency_key"})
    key = optional_string(arguments, "idempotency_key")
    if action is ControllerAction.STATUS and key is not None:
        raise RequestSchemaError("idempotency_key is not allowed for status")
    if action is not ControllerAction.STATUS and not key:
        raise RequestSchemaError("idempotency_key is required for mutating action")
    return cls(action=action, root=require_path(arguments, "root"), payload=payload, idempotency_key=key)

def execute_mutation(self, request, operation, resource_id, effect):
    scope = self.state.require_scope(request.root)
    authorization = self.policy.authorize(request.action, scope.policy_id)
    lock = self.locks.acquire(scope.root_id, owner_id=request.idempotency_key, lease_seconds=30)
    intent = self.ledger.record_intent(
        scope.root_id, scope.campaign_id, operation.value,
        request.payload.to_dict(), request.idempotency_key,
    )
    session = MutationSession.from_intent(intent, lock, authorization)
    try:
        result = self.recovery.run_phase(
            session, phase=operation.value,
            effect=lambda: effect(session.issue(operation, resource_id, operation.value)),
        )
        return self.ledger.commit_receipt(
            scope.root_id, scope.campaign_id, intent.intent_id, "intent.completed",
            result.to_dict(), f"{request.idempotency_key}:terminal",
        )
    except BaseException as error:
        self.recovery.commit_terminal_failure(session, error, f"{request.idempotency_key}:failed")
        raise
```

Every payload dataclass defines `ALLOWED_FIELDS` and `REQUIRED_FIELDS`; `parse_exact` rejects fields belonging to another action. CLI, MCP, the legacy adapter, tests, and recovery all call this parser. `V1RequestAdapter` translates the frozen P00 surface without allowing v1 fields into v2 parsing.

Implement the initial protected meter beside recovery. For model/subagent/memory/proposal/evaluation/judge calls, `authorize` computes `reserved_tokens = estimated_tokens + output_cap`, requires a positive conservative bound within the current campaign hard cap, persists `budget.granted`, and returns a short-lived grant before execution. Deterministic local tools may reserve zero tokens only with enforceable wall-time and positive tool caps. `reconcile` consumes a distinct session capability, charges authoritative actual usage or the full reservation, and persists `budget.reconciled` even for failure, timeout, unknown usage, or later `require_success()` failure. Plan 07 extends this exact meter.

Create a `registered_processes` table keyed by protected `process_id`. `launch` first allocates stdout/stderr/handshake handles and appends `process.launch.intended`, then spawns only `process_trampoline.py` with those predeclared handles. The trampoline creates the process group and atomically writes PID, PGID, executable digest, and platform start token before `exec`. `launch` validates the handshake and appends `process.started`; if the controller crashes first, capability-gated `reconcile_launch` performs that binding on restart. `await_terminal`, `terminate`, and `archive` likewise require exact `PROCESS_RECONCILE`, `PROCESS_TERMINATE`, and `ARTIFACT_PERSIST` capabilities and append their durable receipts before returning. `_register_existing_process` is private to this recovery path. Never infer ownership from PID alone. Keep the root lock until every intended launch has a bound terminal reconciliation.

Recovery first reconciles intended and registered process rows. Generic abort journals and replays `mark-aborting -> bind any spawn handshakes -> terminate registered process groups -> archive logs/receipts -> append terminal aborted or incomplete receipt -> reconcile processes/grants/reservations -> remove only a disposable recorded worktree -> release root lock`. The root lock release is always the final phase and every phase has its own derived idempotency key. A phase exception appends a typed terminal failed receipt with the last completed phase and preserved artifacts before returning failure; it does not unlock while a launch is unbound or a child is unreconciled.

- [ ] **Step 4: Run recovery and policy tests**

Run: `python3 -m pytest -q tests/selfloop/test_controller_requests.py tests/selfloop/test_budget_boundary.py tests/selfloop/test_recovery.py tests/selfloop/test_mutation_routing.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit controller recovery**

```bash
git add scripts/selfloop_supervisor/contracts.py scripts/selfloop_supervisor/controller_requests.py scripts/selfloop_supervisor/bootstrap.py scripts/selfloop_supervisor/snapshot.py scripts/selfloop_supervisor/supervisor_bundle.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/policy.py scripts/selfloop_supervisor/process_registry.py scripts/selfloop_supervisor/process_trampoline.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_cli.py scripts/harness_homebase_mcp.py tests/selfloop/test_controller_requests.py tests/selfloop/test_budget_boundary.py tests/selfloop/test_recovery.py tests/selfloop/test_mutation_routing.py
git commit -m "feat(selfloop): add policy-bound controller recovery"
```

### Task 5: Project canonical state without rewriting repository truth

**Files:**
- Modify: `scripts/selfloop_supervisor/projection.py`
- Modify: `scripts/selfloop_supervisor/release.py`
- Modify: `scripts/selfloop_cli.py`
- Test: `tests/selfloop/test_state_projection.py`

**Interfaces:**
- Extends P01 `ProjectionWriter.write(repo_root, state) -> Path` and `normalize_projection_for_release(data: bytes) -> tuple[bytes, str | None]` to render C2 champion, experiment, gate, receipt, and blocker fields.
- Produces: `ProjectionService.refresh(root_id: str, repo_root: Path, state: CampaignState, idempotency_key: str) -> ProjectionReceipt`; the receipt and ledger event carry wire field `stateProjectionDigest`.
- Markers remain exactly `# >>> SIPS SELFLOOP GENERATED v1 >>>` and `# <<< SIPS SELFLOOP GENERATED v1 <<<`.

- [ ] **Step 1: Write a failing byte-preservation and digest-separation test**

```python
def test_projection_preserves_non_runtime_bytes_and_release_normalizes_block(tmp_path, projection_service):
    path = tmp_path / "state.yaml"
    prefix = b"version: 1\nnotes:\n  - keep me\n"
    old = b"# >>> SIPS SELFLOOP GENERATED v1 >>>\nstatus: old\n# <<< SIPS SELFLOOP GENERATED v1 <<<\n"
    suffix = b"owner: RasputinKaiser\n"
    path.write_bytes(prefix + old + suffix)
    receipt = projection_service.refresh("root-1", tmp_path, campaign_state(status="running", last_completed_gate="G1"), "projection-1")
    assert path.read_bytes().startswith(prefix)
    assert path.read_bytes().endswith(suffix)
    normalized, actual_digest = normalize_projection_for_release(path.read_bytes())
    assert b"status: running" not in normalized
    assert actual_digest == hashlib.sha256(extract_projection_block(path.read_bytes())).hexdigest()
    assert receipt.state_projection_digest == actual_digest
    assert projection_service.ledger.last_event("root-1").payload["stateProjectionDigest"] == actual_digest
```

- [ ] **Step 2: Run and observe the projection failure**

Run: `python3 -m pytest -q tests/selfloop/test_state_projection.py`

Expected: tests fail because the P01 projection module lacks `ProjectionService` and C2 ledger-backed fields.

- [ ] **Step 3: Implement marker-only replacement and normalized release bytes**

```python
NORMALIZED_BLOCK = (
    PROJECTION_START.encode() + b"\n" +
    b"projection: normalized-live-state\n" +
    PROJECTION_END.encode() + b"\n"
)

def normalize_projection_for_release(data: bytes) -> tuple[bytes, str | None]:
    parts = split_projection(data)
    digest = hashlib.sha256(parts.block).hexdigest() if parts.block is not None else None
    return parts.prefix + NORMALIZED_BLOCK + parts.suffix, digest
```

- [ ] **Step 4: Prove projection parity and run adjacent ledger/recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_state_projection.py tests/selfloop/test_ledger.py tests/selfloop/test_recovery.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit projection support**

```bash
git add scripts/selfloop_supervisor/projection.py scripts/selfloop_supervisor/release.py scripts/selfloop_cli.py tests/selfloop/test_state_projection.py
git commit -m "feat(selfloop): derive marker-scoped runtime projection"
```

### Task 6: Roll the protected supervisor bundle without mutable-source fallback

**Files:**
- Create: `scripts/selfloop_supervisor/runtime_registry.py`
- Create: `scripts/selfloop_supervisor/trusted_upgrade.py`
- Modify: `scripts/selfloop_supervisor/supervisor_bundle.py`
- Modify: `scripts/selfloop_supervisor/bootstrap_store.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Test: `tests/selfloop/test_supervisor_rollover.py`

**Interfaces:**
- Consumes P02 `ReleaseBuilder`, `ReleaseBundleStore.open_verified(release_id, source_attestation_digest) -> ReleaseBundleReceipt`, `SupervisorBundleBuilder.build(release_bundle) -> SupervisorBundleReceipt`, P04's exact `SupervisorUpgradeAuthorizationReceipt` and `PendingSupervisorUpgrade`, and P05 supervisor-upgrade request/session.
- P05 implements only the receiving side of the P04 bridge: `TrustedUpgradeVerifier.verify_pending(pending: PendingSupervisorUpgrade, legacy_store: BootstrapStore) -> VerifiedPendingSupervisorUpgrade` and private `_import_pending(verified, capability: MutationCapability) -> EventRecord`. It verifies the pending row and bound authorization were persisted by the exact active P04 runtime and bind root, source commit/release/manifest/source-attestation/release-bundle receipt digests, candidate supervisor bundle/manifest digests, expected P04 digest, spec/policy digests, and one-use nonce. P05 source cannot self-authorize, rebuild, or restage its first activation.
- Produces `SupervisorRuntimeRegistry.stage(release_bundle: ReleaseBundleReceipt, capability: MutationCapability) -> SupervisorBundleReceipt`, `activate(staged_bundle_digest: str, expected_prior_digest: str, capability: MutationCapability) -> SupervisorActivationReceipt`, `resolve_bundle(bundle_digest: str) -> SupervisorBundleReceipt`, and `load_active(root_id: str) -> SupervisorBundleReceipt`.
- Produces `SupervisorUpgradeService.authorize(session, payload, tty) -> SupervisorUpgradeAuthorizationReceipt`, `prepare(session, payload) -> PendingSupervisorUpgrade`, and `resolve_pending(session, pending_upgrade_id) -> EventRecord`. Authorization binds release ID, source-attestation, manifest, path-independent release-bundle receipt, source commit, and current active digest after direct TTY confirmation. Preparation resolves the authorization event, opens exact release bytes, stages them, and persists the pending receipt. Resolution first checks the canonical ledger; if absent only for the first bridge, it loads/verifies the P04 row and calls capability-gated `_import_pending`. `activate-supervisor` calls this resolver inside `handle`; adapters cannot import or pass event payloads.
- `SupervisorBundleReceipt.bundle_digest` is the sole protected-runtime digest. `resolve_bundle` derives the real path below the configured `SIPS_HOME`, rejects symlinks/path escapes/caller paths, rehashes the manifest and every byte, and returns a receipt whose `path` is that resolved directory.
- The P05 dispatcher resolves only the canonical activated digest. There is no `PYTHONPATH` or source-tree fallback after activation; the prior P04 digest remains immutable and addressable as the rescue runtime. A failed host-load proof atomically restores that prior digest and appends a terminal failed activation receipt.

- [ ] **Step 1: Write failing old-trust, byte-handle, capability, path-resolution, replay, and rollback tests**

```python
def test_p04_authorizes_first_p05_rollover_and_keeps_rescue(controller, p04_runtime, p05_release_bundle):
    authorization = p04_runtime.authorize_upgrade(
        root_id="root-1", target=p05_release_bundle,
        expected_prior_digest=p04_runtime.bundle.bundle_digest,
    )
    pending = p04_runtime.prepare_supervisor_upgrade(authorization=authorization)
    request = activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=p04_runtime.bundle.bundle_digest,
        idempotency_key="activate-p05",
    )
    receipt = controller.handle(request).receipt
    assert receipt.prior_bundle_digest == p04_runtime.bundle.bundle_digest
    assert receipt.active_bundle_digest == controller.runtime.load_active("root-1").bundle_digest
    assert controller.runtime.resolve_bundle(receipt.active_bundle_digest).path == receipt.resolved_bundle_path
    assert controller.runtime.resolve_bundle(receipt.prior_bundle_digest).bundle_digest == p04_runtime.bundle.bundle_digest
    assert controller.handle(request).receipt == receipt

def test_release_identity_raw_path_and_self_signed_upgrade_are_rejected(runtime_registry, p05_release_bundle):
    with pytest.raises(TypeError, match="ReleaseBundleReceipt required"):
        runtime_registry.stage(p05_release_bundle.release_identity, stage_capability())
    with pytest.raises(TypeError, match="ReleaseBundleReceipt required"):
        runtime_registry.stage(p05_release_bundle.path, stage_capability())
    with pytest.raises(TrustedUpgradeDenied, match="verified PendingSupervisorUpgrade required"):
        p05_controller().handle(activate_request(
            pending_upgrade_id=self_signed_pending_upgrade(p05_release_bundle).pending_upgrade_id,
            expected_prior_digest="sha256:p04", idempotency_key="self-signed-pending",
        ))

def test_stage_and_activate_reject_missing_or_cross_session_capability(runtime_registry, p05_release_bundle):
    with pytest.raises(MutationDenied, match="controller capability required"):
        runtime_registry.stage(p05_release_bundle, capability=None)
    staged = runtime_registry.stage(p05_release_bundle, stage_capability(session="session-a"))
    with pytest.raises(MutationDenied, match="session mismatch"):
        runtime_registry.activate(
            staged.bundle_digest, "sha256:p04", activate_capability(session="session-b"),
        )

def test_dispatcher_resolves_real_bundle_path_and_never_falls_back(runtime_registry, active_bundle, source_tree):
    source_tree.joinpath("scripts/selfloop_supervisor/kernel.py").write_text("raise RuntimeError('mutable')\n")
    loaded = runtime_registry.dispatch("root-1", status_request())
    assert loaded.bundle_digest == active_bundle.bundle_digest
    assert loaded.path == runtime_registry.bundles_root / active_bundle.bundle_digest

def test_failed_host_proof_rolls_back_and_persists_terminal_failure(controller, p04_runtime, p05_release_bundle):
    controller.host_probe.fail_with("loaded digest differs")
    response = controller.handle(p04_runtime.activate_request(p05_release_bundle, "activate-fail"))
    assert response.status == "failed"
    assert controller.runtime.load_active("root-1").bundle_digest == p04_runtime.bundle.bundle_digest
    assert controller.ledger.last_event("root-1", "supervisor.activation.failed").payload["hostProofStatus"] == "failed"
```

- [ ] **Step 2: Run and observe the missing registry**

Run: `python3 -m pytest -q tests/selfloop/test_supervisor_rollover.py`

Expected: collection fails with `ModuleNotFoundError: No module named 'selfloop_supervisor.runtime_registry'`.

- [ ] **Step 3: Implement the P04-trusted bridge, verified byte staging, and ledger-authoritative activation**

The bridge first verifies the sealed P04 bootstrap row, resolves `${SIPS_HOME}/selfloop/supervisor/bundles/<p04-digest>`, rehashes it, and resolves the exact `PendingSupervisorUpgrade` plus its bound `SupervisorUpgradeAuthorizationReceipt`. Verify their schemas, request/idempotency digests, binding state, root, active P04 digest, source commit, release ID, manifest/source-attestation/path-independent release-bundle receipt digests, candidate supervisor bundle/manifest digests, and nonce. Resolve and rehash the already staged candidate supervisor bundle from its digest; P05 must not rebuild or restage it. Import the pending receipt and legacy row digest as `supervisor.upgrade.pending-imported` in the canonical ledger.

Inside one lock-owning `MutationSession`, journal `authorize-upgrade`, `resolve-release`, `stage-supervisor`, `prepare-upgrade`, `resolve-pending`, `activate-pointer`, and `host-proof` before their effects. For P05-and-later upgrades, the active pinned controller handles the TTY-only authorization action and persists `SupervisorUpgradeAuthorizationReceipt`. `prepare-supervisor-upgrade` accepts only that receipt digest plus expected prior digest, calls `ReleaseBundleStore.open_verified(authorization.release_id, authorization.source_attestation_digest)`, verifies `release_bundle.receipt_digest`, and passes the exact byte handle to `stage` with `SUPERVISOR_STAGE`. It resolves/rehashes `bundles/<bundle_digest>` and persists `PendingSupervisorUpgrade`. `activate-supervisor` supplies only the pending ID; `resolve_pending` loads a canonical pending event or verifies/imports the P04 row using `SUPERVISOR_PENDING_IMPORT`, then activation consumes `SUPERVISOR_ACTIVATE`. In one canonical transaction it compares the prior digest, records prior rescue/target digests, consumes the pending/authorization nonce, and appends `supervisor.activated`; recovery rebuilds the loader projection from that event.

Run a protected loader/startup probe against the resolved target bytes. If it cannot prove the exact target digest/path, execute a journaled compensation transaction restoring the P04 digest, append `supervisor.activation.failed` with raw host proof, and keep P05 non-authoritative. On success, append `supervisor.host-load.proved`. Every process start re-resolves and rehashes the active bundle. Crashes replay phase receipts and cannot consume the P04 authorization twice.

- [ ] **Step 4: Run rollover and adjacent recovery/routing tests**

Run: `python3 -m pytest -q tests/selfloop/test_supervisor_rollover.py tests/selfloop/test_recovery.py tests/selfloop/test_mutation_routing.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit the rollover implementation**

```bash
git add scripts/selfloop_supervisor/runtime_registry.py scripts/selfloop_supervisor/trusted_upgrade.py scripts/selfloop_supervisor/supervisor_bundle.py scripts/selfloop_supervisor/bootstrap_store.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py tests/selfloop/test_supervisor_rollover.py
git commit -m "feat(selfloop): activate immutable supervisor releases"
```

## Plan Verification

- [ ] Run `python3 -m pytest -q tests/selfloop/test_ledger.py tests/selfloop/test_controller_state.py tests/selfloop/test_strategy_boundary.py tests/selfloop/test_controller_requests.py tests/selfloop/test_budget_boundary.py tests/selfloop/test_recovery.py tests/selfloop/test_mutation_routing.py tests/selfloop/test_state_projection.py tests/selfloop/test_supervisor_rollover.py`; expected: all pass.
- [ ] In the disposable P04-to-P05 fixture, invoke `activate-supervisor` twice with the same P04 authorization digest and idempotency key; expected: one `supervisor.activated` event, the same receipt twice, a resolved/rehash-verified P05 bundle path, a current host-load proof, and the P04 bundle still verified as rescue. Injecting a host digest mismatch must leave P04 active and append one `supervisor.activation.failed` receipt.
- [ ] Run `python3 scripts/selfloop_cli.py status --root . --json`; expected: schema `homebase.selfloop.v2`, conformance `C1`, verified ledger/anchor status, and no adaptive-experiment claim.
- [ ] Run `python3 scripts/validate_v2.py --check-eval && git diff --check`; expected: both exit `0`, and `git diff --check` emits no output.
- [ ] Confirm tests created no files below the real `${SIPS_HOME:-~/.codex/sips}`.
