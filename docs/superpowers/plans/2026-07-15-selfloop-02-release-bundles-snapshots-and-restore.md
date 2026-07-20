# Selfloop Release Bundles, Snapshots, and Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build complete immutable release bundles and verified whole-boundary recovery snapshots, with projection-only `state.yaml` changes excluded from candidate identity but recorded separately.

**Architecture:** Release construction lives in the protected supervisor and reads a committed Git tree under a versioned boundary policy. It normalizes only P01's generated `state.yaml` block, records that block's digest outside the release identity payload, rejects every other tracked or untracked source byte, and records any narrowly allowlisted generated build artifacts in the source attestation. The builder writes the exact committed bytes into a protected staged archive and returns only its opaque handle; materialization never accepts a caller byte-source path. Bundles, pinned supervisor copies, source attestations, and recovery snapshots live under `SIPS_HOME`, never inside candidate-writable roots.

**Tech Stack:** Python 3.10+, standard-library `hashlib`, `json`, `os`, `shutil`, `stat`, `subprocess`, `tarfile`, `tempfile`, pytest 8+.

## Global Constraints

- Normative contract is `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`; advertised conformance remains C0 until P04 completes.
- “Git commits and release bundles are the normal rollback mechanism.”
- “Promotion moves an immutable release bundle” containing code, configuration, dependency, capability, memory, evaluator, install, activation, migration, and rollback identity.
- “Changed-path policy MUST cover the entire release, not just `scripts/`.”
- “Generated or installed plugin files MUST be derived from and hash-linked to the release bundle.”
- “The snapshot identity MUST include each recursive relative path, file type, mode, file content hash or symlink target, and manifest version.”
- “Restore MUST verify the manifest before mutation, remove files not present in the restored bundle within the declared install boundary, verify the restored digest, and run the rescue smoke check.”
- A source commit, installed cache, configuration, and live host are separate proof layers.
- Only `# >>> SIPS SELFLOOP GENERATED v1 >>>` through `# <<< SIPS SELFLOOP GENERATED v1 <<<` is normalized in `state.yaml`; all other bytes remain release evidence.
- Normalized cleanliness enumerates tracked changes, untracked files, and ignored files. Only non-symlink, non-executable generated artifacts matching the exact versioned build-artifact allowlist may be excluded; an untracked or ignored source/configuration path always fails closed.
- `ReleaseBundleReceipt` is the canonical byte-bearing release handle. `ReleaseIdentity` alone never authorizes staging, evaluation, bootstrap, or supervisor rollover, and arbitrary caller-provided bundle paths are not accepted.
- A release ID names immutable committed bytes while a source attestation names the exact normalized-clean observation that authorized one build. `ReleaseBundleStore.open_verified` therefore requires both identities; it never silently selects one of several attestations for the same release.
- `ReleaseBundleReceipt.receipt_digest` is the path-independent proof reference. It is always recomputed from canonical non-path fields before use; moving the protected store cannot change it, and possession of the digest alone does not authorize bytes.
- `SupervisorBundleReceipt.bundle_digest` is the one canonical protected-runtime digest field; later plans must not rename it to `digest` or reconstruct it from a path name.
- Snapshot/restore adapters accept only boundary IDs from `recovery-boundaries-v1.json` and rescue-command IDs from `rescue-commands-v1.json`. Protected code derives absolute paths, argv, environment, and `SnapshotContext` from canonical scope; caller-supplied paths, commands, or context JSON are invalid.
- Existing `snapshot_harness.py` filename-plus-content identity remains covered and unchanged for C0 callers.

---

## File Map

- Create `scripts/selfloop_supervisor/release.py`: release entries, identity, clean-tree proof, and bundle builder.
- Create `scripts/selfloop_supervisor/supervisor_bundle.py`: pinned protected-runtime bundle builder.
- Create `scripts/selfloop_supervisor/snapshot.py`: recursive capture, verification, restore, and receipts.
- Create `references/selfloop/policies/release-boundary-v1.json`.
- Create `references/selfloop/policies/recovery-boundaries-v1.json` and `rescue-commands-v1.json`: registered local boundary templates and pinned rescue argv.
- Create `references/selfloop/policies/runtime-lock-v1.json`: exact stdlib-only selfloop runtime dependency identity and Python floor.
- Create `references/selfloop/schemas/release-manifest-v1.example.json`, `release-source-attestation-v1.example.json`, `release-bundle-receipt-v1.example.json`, and `snapshot-manifest-v1.example.json`.
- Modify `scripts/selfloop_cli.py`: add `bundle`, `snapshot`, and `restore` supervisor commands.
- Modify `scripts/validate_v2.py`: validate boundary, schemas, and protected paths.
- Create `tests/selfloop/test_release_bundle.py`, `test_supervisor_bundle.py`, and `test_recovery_snapshot.py`.
- Modify `tests/selfloop/conftest.py`: release, bundle, and snapshot fixtures.
- Modify `tests/selfloop/test_state_projection.py`; retain existing snapshot tests in `scripts/run_tests.py`.

### Task 1: Compute complete release identity without live-projection drift

**Files:**
- Create: `scripts/selfloop_supervisor/release.py`
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Create: `references/selfloop/policies/release-boundary-v1.json`
- Create: `references/selfloop/policies/runtime-lock-v1.json`
- Create: `references/selfloop/schemas/release-manifest-v1.example.json`
- Create: `references/selfloop/schemas/release-source-attestation-v1.example.json`
- Modify: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_release_bundle.py`

**Interfaces:**
- Consumes: `normalize_projection_for_release(data) -> tuple[bytes, str | None]` from P01 and a clean committed Git SHA.
- Produces: `ReleaseEntry`, `ReleaseManifest.identity_payload()`, `ReleaseSourceAttestation`, `ReleaseBuildReceipt`, `ReleaseBuilder.assert_normalized_clean(root, sha) -> ReleaseSourceAttestation`, and `ReleaseBuilder.build(root_id, root, sha, metadata) -> ReleaseBuildReceipt`.

- [ ] **Step 1: Write release-identity tests**

```python
def test_live_projection_changes_only_projection_digest(clean_sips_repo, sips_home):
    builder = ReleaseBuilder(sips_home)
    first = builder.build("root-a", clean_sips_repo, "HEAD", RELEASE_METADATA)
    rewrite_generated_projection(clean_sips_repo / "state.yaml", revision=9)
    builder.assert_normalized_clean(clean_sips_repo, "HEAD")
    second = builder.build("root-a", clean_sips_repo, "HEAD", RELEASE_METADATA)
    assert second.release_id == first.release_id
    assert second.source_tree_digest == first.source_tree_digest
    assert second.projection_digest != first.projection_digest

def test_operator_authored_state_change_is_dirty(clean_sips_repo, sips_home):
    with (clean_sips_repo / "state.yaml").open("a", encoding="utf-8") as handle:
        handle.write("operator_note: changed\n")
    with pytest.raises(DirtyReleaseError):
        ReleaseBuilder(sips_home).assert_normalized_clean(clean_sips_repo, "HEAD")

def test_untracked_or_ignored_release_source_is_dirty(clean_sips_repo, sips_home):
    (clean_sips_repo / ".gitignore").write_text("scripts/uncommitted.py\n", encoding="utf-8")
    git(clean_sips_repo, "add", ".gitignore")
    git(clean_sips_repo, "commit", "-m", "ignore fixture")
    (clean_sips_repo / "scripts").mkdir(exist_ok=True)
    (clean_sips_repo / "scripts/uncommitted.py").write_text("UNCOMMITTED = True\n", encoding="utf-8")
    with pytest.raises(DirtyReleaseError, match="uncommitted release path"):
        ReleaseBuilder(sips_home).assert_normalized_clean(clean_sips_repo, "HEAD")

def test_allowlisted_generated_artifact_is_excluded_but_attested(clean_sips_repo, sips_home):
    cache = clean_sips_repo / ".pytest_cache/v/cache"
    cache.mkdir(parents=True)
    cache.joinpath("nodeids").write_text("[]\n", encoding="utf-8")
    attestation = ReleaseBuilder(sips_home).assert_normalized_clean(clean_sips_repo, "HEAD")
    assert attestation.excluded_build_artifacts == (".pytest_cache/v/cache/nodeids",)
    assert attestation.excluded_build_artifacts_digest
```

- [ ] **Step 2: Run tests and observe the missing release module**

Run: `python3 -m pytest -q tests/selfloop/test_release_bundle.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'selfloop_supervisor.release'`.

- [ ] **Step 3: Implement the manifest and normalized clean-tree proof**

```python
from collections.abc import Sequence

@dataclass(frozen=True)
class ReleaseEntry:
    path: str
    kind: str
    mode: int
    digest: str | None
    symlink_target: str | None

@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    root_id: str
    commit_sha: str
    source_tree_digest: str
    configuration_digest: str
    dependency_lock_digest: str
    runtime_identity: dict
    capability_manifest_digest: str
    permission_manifest_digest: str
    memory_compatibility: dict
    evaluator_compatibility: dict
    install_payload_digest: str
    activation_contract_version: str
    migration_metadata: dict
    rollback_metadata: dict
    entries: Sequence[ReleaseEntry]

@dataclass(frozen=True)
class ReleaseBuildReceipt:
    manifest: ReleaseManifest
    projection_digest: str | None
    normalized_clean: bool
    source_attestation: ReleaseSourceAttestation
    staged_archive_id: str
    staged_archive_digest: str
    @property
    def release_id(self) -> str: return self.manifest.release_id
    @property
    def source_tree_digest(self) -> str: return self.manifest.source_tree_digest
    @property
    def manifest_digest(self) -> str: return sha256_canonical_manifest(self.manifest)
    @property
    def source_attestation_digest(self) -> str: return self.source_attestation.digest
    def to_release_identity(self) -> ReleaseIdentity:
        return ReleaseIdentity(
            release_id=self.manifest.release_id, commit_sha=self.manifest.commit_sha,
            source_tree_digest=self.manifest.source_tree_digest,
            manifest_digest=self.manifest_digest,
            install_payload_digest=self.manifest.install_payload_digest,
        )
```

Define `ReleaseSourceAttestation` with `root_id`, `commit_sha`, `normalized_tree_digest`, `boundary_policy_digest`, sorted `excluded_build_artifacts`, `excluded_build_artifacts_digest`, `projection_digest`, and canonical `digest`. Define the shared frozen `ReleaseIdentity` in `contracts.py` with exactly the five fields returned above; later plans consume `ReleaseBuildReceipt.to_release_identity()` rather than inventing a parallel release shape.

Build entries from every tracked path in `git archive <sha>`, preserving relative path, regular-file or symlink kind, executable mode, content hash or link target. Replace only the committed generated block in archived `state.yaml` with P01's fixed sentinel before hashing or staging; the live block digest remains outside the immutable identity and the projector regenerates it after activation. Hash a canonical JSON identity payload that excludes `release_id`; set `release_id` to `release-` plus its first 24 hex characters. During `build()`, write those exact normalized bytes beneath `${SIPS_HOME}/selfloop/release-staging/<staged-archive-id>`, verify them against the manifest, remove group/other write bits, and return only `staged_archive_id` plus its canonical digest on `ReleaseBuildReceipt`; neither an adapter nor `materialize()` accepts an archive path. Keep the live projection digest and source attestation only on `ReleaseBuildReceipt`, never in the immutable release identity payload.

`assert_normalized_clean()` runs `git status --porcelain=v2 -z --untracked-files=all --ignored=matching`, compares every tracked byte to the selected commit after applying P01 normalization only to `state.yaml`, and classifies every untracked or ignored path. When Git reports an ignored directory entry, walk it recursively without following symlinks so every contained file is classified rather than trusting the directory name. `release-boundary-v1.json` contains an exact `allowedUntrackedBuildPatterns` list initially limited to `.pytest_cache/**`, `**/__pycache__/**`, `**/*.pyc`, `.coverage`, `htmlcov/**`, `build/**`, and `dist/**`. A match is excludable only when it is a regular non-executable file beneath the matched generated directory; a symlink, executable, path escape, nested Git repository, or source/configuration suffix outside those generated forms fails. Every excluded relative path and content digest enters the source attestation, while none enters the release bundle. An ignored `scripts/*.py`, command, skill, hook, manifest, policy, fixture, test, documentation, or configuration file fails even if `.gitignore` matches it.

The boundary policy must explicitly classify `.codex-plugin`, `.agents`, `.mcp.json`, `commands`, `skills`, `agents`, `hooks`, `assets`, `scripts`, `tests`, `fixtures`, `.github`, documentation, `references/selfloop`, `pyproject.toml`, `runtime-lock-v1.json`, and `state.yaml`; an unclassified tracked path fails release construction. `runtime-lock-v1.json` declares Python `>=3.10`, implementation `CPython`, and an empty third-party runtime dependency list; test-tool versions remain part of the environment digest. Extend `tests/selfloop/conftest.py` with `RELEASE_METADATA`, `clean_sips_repo`, `rewrite_generated_projection`, `release_fixture`, and `snapshot_fixture`; each builds real temporary files and Git commits rather than mocking hashes.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_release_bundle.py tests/selfloop/test_state_projection.py`

Expected: projection-only drift and explicitly attested generated artifacts pass; every tracked, untracked, or ignored source/configuration byte fails.

```bash
git add scripts/selfloop_supervisor/release.py scripts/selfloop_supervisor/contracts.py references/selfloop/policies/release-boundary-v1.json references/selfloop/policies/runtime-lock-v1.json references/selfloop/schemas/release-manifest-v1.example.json references/selfloop/schemas/release-source-attestation-v1.example.json tests/selfloop/conftest.py tests/selfloop/test_release_bundle.py
git commit -m "feat(selfloop): build complete release identity"
```

### Task 2: Materialize immutable release and protected supervisor bundles

**Files:**
- Modify: `scripts/selfloop_supervisor/release.py`
- Create: `scripts/selfloop_supervisor/supervisor_bundle.py`
- Create: `references/selfloop/schemas/release-bundle-receipt-v1.example.json`
- Modify: `tests/selfloop/test_release_bundle.py`
- Test: `tests/selfloop/test_supervisor_bundle.py`

**Interfaces:**
- Consumes: the complete `ReleaseBuildReceipt`, including its protected opaque staged-archive identity and exact source attestation.
- Produces: `ReleaseBundleStore.materialize(build: ReleaseBuildReceipt) -> ReleaseBundleReceipt`, `ReleaseBundleStore.open_verified(release_id: str, source_attestation_digest: str) -> ReleaseBundleReceipt`, `ReleaseBundleReceipt.identity_payload() -> Mapping[str, Any]`, path-independent `ReleaseBundleReceipt.receipt_digest`, and `SupervisorBundleBuilder.build(release_bundle: ReleaseBundleReceipt) -> SupervisorBundleReceipt`.
- `ReleaseBundleReceipt` has canonical fields `release_identity`, protected resolved `path`, `manifest_digest`, `source_attestation_digest`, and recomputed `receipt_digest`. Its exact path-independent digest contract is below; require the top-level and nested manifest digests to match. `SupervisorBundleReceipt` has canonical fields `path`, `bundle_digest`, `manifest_digest`, and `source_release_id`.

```python
def identity_payload(self) -> dict[str, object]:
    return {
        "schema": "selfloop.release-bundle-receipt.v1",
        "releaseIdentity": {
            "releaseId": self.release_identity.release_id,
            "commitSha": self.release_identity.commit_sha,
            "sourceTreeDigest": self.release_identity.source_tree_digest,
            "manifestDigest": self.release_identity.manifest_digest,
            "installPayloadDigest": self.release_identity.install_payload_digest,
        },
        "manifestDigest": self.manifest_digest,
        "sourceAttestationDigest": self.source_attestation_digest,
    }

@property
def receipt_digest(self) -> str:
    encoded = json.dumps(
        self.identity_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

- [ ] **Step 1: Write bundle immutability tests**

```python
def test_pinned_supervisor_is_outside_candidate_and_digest_named(tmp_path, release_fixture):
    receipt = SupervisorBundleBuilder(tmp_path / "sips").build(release_fixture.bundle_receipt)
    assert receipt.path.parent.name == "bundles"
    assert receipt.path.name == receipt.bundle_digest
    assert receipt.source_release_id == release_fixture.bundle_receipt.release_identity.release_id
    assert not receipt.path.is_relative_to(release_fixture.repo_root)
    assert receipt.path.joinpath("scripts/selfloop_supervisor/compat_controller.py").is_file()

def test_bundle_store_accepts_no_caller_byte_source_path(release_fixture):
    with pytest.raises(TypeError):
        release_fixture.bundle_store.materialize(
            release_fixture.build_receipt,
            release_fixture.repo_root,
        )

def test_release_bundle_receipt_digest_is_path_independent(release_fixture):
    receipt = release_fixture.bundle_receipt
    assert "path" not in receipt.identity_payload()
    assert receipt.receipt_digest == sha256_canonical_json(receipt.identity_payload())
    reopened = release_fixture.bundle_store.open_verified(
        receipt.release_identity.release_id,
        receipt.source_attestation_digest,
    )
    assert reopened.receipt_digest == receipt.receipt_digest
```

- [ ] **Step 2: Run the test and observe the missing builder**

Run: `python3 -m pytest -q tests/selfloop/test_supervisor_bundle.py`

Expected: FAIL because `SupervisorBundleBuilder` is undefined.

- [ ] **Step 3: Implement content-addressed materialization**

Resolve `build.staged_archive_id` only beneath the protected staging store and require its digest and every entry to match the build receipt. Write release bytes plus `manifest.json` to `${SIPS_HOME}/selfloop/bundles/<release-id>` through a temporary sibling, then rename atomically. Store the exact source attestation separately at `${SIPS_HOME}/selfloop/source-attestations/<source-attestation-digest>.json`; validate it against `release-source-attestation-v1`, then require its root, commit, and normalized-tree identities to match the release manifest and staged bytes. Existing release bytes may be reused only after full verification, while a new attestation for the same release gets its own immutable attestation object. `materialize()` accepts only the complete `ReleaseBuildReceipt`; a detached manifest, staged-archive ID, or path is a type error. `open_verified(release_id, source_attestation_digest)` resolves both IDs beneath their content-addressed stores, rejects path arguments and symlinks, verifies every bundle entry and the exact attestation linkage, recomputes the path-independent receipt digest, and returns the canonical `ReleaseBundleReceipt`. A stored or caller-asserted receipt digest is only an equality assertion against that recomputation.

Build the protected subset at `${SIPS_HOME}/selfloop/supervisor/bundles/<supervisor-digest>` only from a verified `ReleaseBundleReceipt`, taking `scripts/selfloop_supervisor`, `scripts/selfloop_cli.py`, and `references/selfloop` from its immutable path. Write `supervisor-manifest.json`, remove group/other write bits, and return `SupervisorBundleReceipt(path, bundle_digest, manifest_digest, source_release_id)`. Existing matching bundles are verified and reused, never overwritten. A `ReleaseIdentity`, raw directory, or caller-supplied supervisor path is rejected because hashes alone do not supply trusted bytes.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_release_bundle.py tests/selfloop/test_supervisor_bundle.py`

Expected: all bundle tests pass.

```bash
git add scripts/selfloop_supervisor/release.py scripts/selfloop_supervisor/supervisor_bundle.py references/selfloop/schemas/release-bundle-receipt-v1.example.json tests/selfloop/test_release_bundle.py tests/selfloop/test_supervisor_bundle.py
git commit -m "feat(selfloop): pin protected supervisor bundles"
```

### Task 3: Capture and restore recursive recovery snapshots

**Files:**
- Create: `scripts/selfloop_supervisor/snapshot.py`
- Create: `references/selfloop/policies/recovery-boundaries-v1.json`
- Create: `references/selfloop/policies/rescue-commands-v1.json`
- Create: `references/selfloop/schemas/snapshot-manifest-v1.example.json`
- Test: `tests/selfloop/test_recovery_snapshot.py`

**Interfaces:**
- Produces the pre-ledger low-level primitives `SnapshotContext`, `SnapshotBoundary`, `RecoveryBoundaryRegistry.resolve(boundary_ids: Sequence[str], scope: RecoveryScope) -> tuple[SnapshotBoundary, ...]`, `RescueCommandRegistry.resolve(command_id: str, scope: RecoveryScope) -> tuple[str, ...]`, `RecoverySnapshotManager.capture(context, boundaries) -> SnapshotReceipt`, `verify(snapshot_id) -> SnapshotManifest`, and `restore(snapshot_id, boundaries, rescue_command) -> RestoreReceipt`. P05 preserves these internals but requires a controller-issued `MutationCapability` for capture/restore once the canonical ledger exists; CLI/MCP never call a low-level mutator directly after that migration.
- `RecoveryScope` contains protected root, campaign, experiment, release, promotion, SIPS-home, install-slot, and configuration identities. Adapters supply only IDs; protected code constructs `SnapshotContext`, absolute boundaries, rescue argv, and the sanitized environment.

- [ ] **Step 1: Write recursive identity, tamper, and exact-restore tests**

```python
def test_snapshot_identity_covers_mode_content_and_symlink(snapshot_fixture):
    first = snapshot_fixture.capture()
    snapshot_fixture.make_executable("bin/tool")
    assert snapshot_fixture.capture().snapshot_id != first.snapshot_id
    snapshot_fixture.retarget_symlink("current", "slots/b")
    assert snapshot_fixture.capture().snapshot_id != first.snapshot_id

def test_restore_removes_extra_files_and_rejects_tampering(snapshot_fixture):
    receipt = snapshot_fixture.capture()
    snapshot_fixture.install_root.joinpath("extra.txt").write_text("remove", encoding="utf-8")
    restored = snapshot_fixture.manager.restore(
        receipt.snapshot_id,
        snapshot_fixture.boundary_registry.resolve(("registered-install.v1",), snapshot_fixture.scope),
        snapshot_fixture.rescue_registry.resolve("rescue-smoke.v1", snapshot_fixture.scope),
    )
    assert restored.verified is True
    assert not snapshot_fixture.install_root.joinpath("extra.txt").exists()
    snapshot_fixture.tamper_snapshot("manifest.json")
    with pytest.raises(SnapshotIntegrityError):
        snapshot_fixture.manager.verify(receipt.snapshot_id)
```

- [ ] **Step 2: Run tests and observe the missing snapshot module**

Run: `python3 -m pytest -q tests/selfloop/test_recovery_snapshot.py`

Expected: FAIL during collection.

- [ ] **Step 3: Implement capture, preflight verification, staged restore, and rescue**

Require nonempty root, campaign, experiment, release, and promotion IDs in `SnapshotContext`. `recovery-boundaries-v1.json` maps IDs such as `registered-install.v1` and `registered-configuration.v1` to templates rooted only in the registered `SIPS_HOME`, active immutable slot, and protected configuration root; resolution rejects traversal, symlinks, overlap, and any path not derived from `RecoveryScope`. `rescue-commands-v1.json` maps `rescue-smoke.v1` to an exact argv template whose substitutions are limited to protected scope values, and records the policy/command digest in every restore receipt. No API that adapters can call accepts an absolute boundary path, raw argv, environment mapping, or context identity.

Hash canonical entries containing boundary ID, relative path, kind, numeric mode, content digest or symlink target, and manifest version. Restore only after manifest verification; build each boundary in a sibling staging directory, atomically swap it into place, verify the restored digest, run the resolved pinned rescue command with a sanitized environment, and roll the prior boundary back if rescue exits nonzero. Preserve the failed receipt and never rewrite snapshot contents.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_recovery_snapshot.py`

Expected: all recursive, tamper, extra-file, and rescue-failure tests pass.

```bash
git add scripts/selfloop_supervisor/snapshot.py references/selfloop/policies/recovery-boundaries-v1.json references/selfloop/policies/rescue-commands-v1.json references/selfloop/schemas/snapshot-manifest-v1.example.json tests/selfloop/test_recovery_snapshot.py
git commit -m "feat(selfloop): add verified recovery snapshots"
```

### Task 4: Expose read-safe bundle and recovery commands and prove C0 compatibility

**Files:**
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/validate_v2.py`

**Interfaces:**
- Produces: `selfloop_cli.py bundle --root --commit`, `snapshot --root --boundary-id <id>`, and `restore --root --snapshot-id <id> --boundary-id <id> --rescue-command-id <id>`.

- [ ] **Step 1: Add CLI tests for JSON receipts and nonzero integrity failures**

Assert each successful command prints one JSON object containing schema, ID, digest, and protected artifact handle; `bundle` includes the recomputed path-independent `receiptDigest`. An unknown/zero boundary ID, caller path/argv/context option, or tampered restore exits 2 and prints an error object to stderr. Assert help and parsing expose no `--context-json`, raw `--boundary`, or raw `--rescue-command` option.

- [ ] **Step 2: Implement the three subcommands without changing start/control semantics**

Parse repeated boundary IDs, resolve them through `RecoveryBoundaryRegistry`, and reject unknown, duplicate, or resolved-overlapping boundaries. Resolve the rescue command only through `RescueCommandRegistry`. Before P05, derive `RecoveryScope` from the registered root and protected compatibility state and fail when experiment/release/promotion identities are incomplete; after P05, the controller derives it from the canonical ledger under a `MutationSession`. `bundle` performs no install or activation. No adapter accepts or echoes an absolute install/configuration path, arbitrary command, context JSON, or environment fragment.

- [ ] **Step 3: Run the plan gate**

Run: `python3 -m pytest -q tests/selfloop && python3 scripts/run_tests.py smoke_coverage --verbose && python3 scripts/validate_v2.py && git diff --check`

Expected: all commands exit 0; existing content-sensitive snapshot coverage remains green; conformance remains C0.

- [ ] **Step 4: Commit the release/recovery surface**

```bash
git add scripts/selfloop_cli.py scripts/validate_v2.py
git commit -m "feat(selfloop): expose verified bundle recovery commands"
```
