# Selfloop Root-Scoped State and Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace C0 singleton selfloop clobbering with supervisor-assigned root identities, per-root materialized state, and a marker-delimited non-authoritative `state.yaml` projection while retaining C0 behavior.

**Architecture:** Extend `scripts/selfloop_supervisor/` with Git-root identity, path, state-store, and projection modules. Canonical JSON remains under `${SIPS_HOME:-~/.codex/sips}/selfloop/roots/<root-id>/`; `state.yaml` is generated from that state but is never read as authority. The generated block is byte-isolated so P02 can normalize only live projection bytes during release hashing.

**Tech Stack:** Python 3.10+, standard-library `json`, `hashlib`, `subprocess`, `uuid`, `pathlib`, atomic `os.replace`, pytest 8+.

## Global Constraints

- Normative contract is `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`; this plan retains advertised conformance at C0.
- “Every campaign, generation, card, attempt, candidate, evaluation run, promotion, and probation MUST have a stable unique identifier.”
- “`rootId` is an opaque supervisor-assigned identity whose registry binds a Git common directory, remote identity, and current canonical path.”
- “A path move requires a verified rebind; a clone receives a new `rootId` unless it is explicitly registered as a campaign fork.”
- “A `root` argument MUST scope state; it MUST NOT merely be echoed while mutating a global singleton.”
- “Mutable operational state MUST live outside the candidate repository under the resolved SIPS home, currently `${SIPS_HOME:-~/.codex/sips}`.”
- “The repository's `state.yaml` is a human-readable truth projection.” It is not the lock or transactional source of truth.
- “Before C2 it MUST state the actual compatibility stage rather than inventing those fields.”
- “Corrupt state MUST be reported as corruption. It MUST NOT be treated as equivalent to no campaign.”
- Preserve every byte of `state.yaml` outside the supervisor markers; normalize only the generated block for release identity and record its actual digest separately.

---

## File Map

- Create `scripts/selfloop_supervisor/identity.py`: Git identity inspection and root registry.
- Create `scripts/selfloop_supervisor/paths.py`: canonical SIPS selfloop paths.
- Create `scripts/selfloop_supervisor/state.py`: schema-v2 materialized state and revision-checked storage.
- Modify `scripts/selfloop_supervisor/projection.py`: extend the P00 marker writer with root fields, splitting, and release normalization.
- Modify `scripts/selfloop_supervisor/compat_controller.py`: resolve and mutate the requested root.
- Modify `tests/selfloop/test_c0_controller.py`: construct the controller from a root registry and SIPS home.
- Modify `scripts/selfloop_cli.py`: use `--root`, defaulting to the current Git root.
- Modify `scripts/harness_homebase_mcp.py`: pass the validated MCP `root` through unchanged.
- Create `references/selfloop/schemas/state-v2.example.json`.
- Create `tests/selfloop/test_root_identity.py`, `test_root_state.py`, and `test_state_projection.py`.
- Create `tests/selfloop/conftest.py`: temporary Git-root and binding fixtures shared by P01-P04.
- Modify `tests/selfloop/test_c0_adapters.py` and `tests/test_homebase_mcp.py`.

### Task 1: Register stable root identities and canonical paths

**Files:**
- Create: `scripts/selfloop_supervisor/identity.py`
- Create: `scripts/selfloop_supervisor/paths.py`
- Create: `tests/selfloop/conftest.py`
- Test: `tests/selfloop/test_root_identity.py`

**Interfaces:**
- Consumes: a canonical Git checkout path and `${SIPS_HOME}`.
- Produces: `GitIdentity`, `RootBinding`, `inspect_git_identity(root)`, `RootRegistry.register(root, fork_of=None)`, `RootRegistry.rebind(root_id, new_root)`, and `SelfloopPaths.for_root(home, root_id)`.

- [ ] **Step 1: Write identity tests using two temporary Git repositories and an explicit clone**

```python
def test_registry_reuses_one_checkout_but_not_a_clone(tmp_path, git_repo_factory):
    source = git_repo_factory(tmp_path / "source")
    clone = git_repo_factory(tmp_path / "clone", remote=source)
    registry = RootRegistry(tmp_path / "sips")
    first = registry.register(source)
    assert registry.register(source).root_id == first.root_id
    assert registry.register(clone).root_id != first.root_id

def test_rebind_requires_matching_remote_and_repository_key(tmp_path, git_repo_factory):
    source = git_repo_factory(tmp_path / "source")
    moved = tmp_path / "moved"
    binding = RootRegistry(tmp_path / "sips").register(source)
    source.rename(moved)
    rebound = RootRegistry(tmp_path / "sips").rebind(binding.root_id, moved)
    assert rebound.canonical_path == str(moved.resolve())
```

- [ ] **Step 2: Run the identity tests and observe the missing module**

Run: `python3 -m pytest -q tests/selfloop/test_root_identity.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'selfloop_supervisor.identity'`.

- [ ] **Step 3: Implement the exact identity records and path API**

```python
@dataclass(frozen=True)
class GitIdentity:
    common_dir: str
    remote: str
    repository_key: str

@dataclass(frozen=True)
class RootBinding:
    root_id: str
    common_dir: str
    remote: str
    repository_key: str
    canonical_path: str
    fork_of: str | None

@dataclass(frozen=True)
class SelfloopPaths:
    home: Path
    root_id: str
    @classmethod
    def for_root(cls, home: Path, root_id: str) -> "SelfloopPaths":
        return cls(home=home.expanduser().resolve(), root_id=root_id)
    @property
    def root_dir(self) -> Path: return self.home / "selfloop" / "roots" / self.root_id
    @property
    def state_file(self) -> Path: return self.root_dir / "state.json"
```

Compute `repository_key` as SHA-256 of the normalized remote plus the first root commit. `register()` reuses only an identical Git common directory; a differing common directory always receives `root-<uuid4 hex>`. `rebind()` requires the stored remote and repository key to match and records the explicit path change. Write the registry atomically at `selfloop/supervisor/root-registry.json`. In `tests/selfloop/conftest.py`, define `git_repo_factory(path, remote=None)` to initialize Git, configure local author `Ralto <ralto@example.invalid>`, commit `README.md`, and optionally clone from `remote`; define `binding` and `two_bindings` from that factory.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_root_identity.py`

Expected: both tests pass.

```bash
git add scripts/selfloop_supervisor/identity.py scripts/selfloop_supervisor/paths.py tests/selfloop/conftest.py tests/selfloop/test_root_identity.py
git commit -m "feat(selfloop): add root identity registry"
```

### Task 2: Store schema-v2 state independently for each root

**Files:**
- Create: `scripts/selfloop_supervisor/state.py`
- Create: `references/selfloop/schemas/state-v2.example.json`
- Modify: `scripts/selfloop_supervisor/compat_controller.py`
- Modify: `tests/selfloop/test_c0_controller.py`
- Test: `tests/selfloop/test_root_state.py`

**Interfaces:**
- Consumes: `RootBinding`, `SelfloopPaths`, and the P00 `ControllerRequest`.
- Produces: `new_c0_state(root_id, campaign_id, focus) -> dict`, `RootStateStore.load() -> dict | None`, and `RootStateStore.save(state, expected_revision) -> dict`.

- [ ] **Step 1: Write isolation, revision, and corruption tests**

```python
def test_two_roots_cannot_clobber_each_other(tmp_path, two_bindings):
    left = RootStateStore(SelfloopPaths.for_root(tmp_path, two_bindings[0].root_id))
    right = RootStateStore(SelfloopPaths.for_root(tmp_path, two_bindings[1].root_id))
    left.save(new_c0_state(two_bindings[0].root_id, "campaign-left", "left"), expected_revision=0)
    right.save(new_c0_state(two_bindings[1].root_id, "campaign-right", "right"), expected_revision=0)
    assert left.load()["focus"] == "left"
    assert right.load()["focus"] == "right"

def test_corruption_and_stale_revision_fail_closed(tmp_path, binding):
    store = RootStateStore(SelfloopPaths.for_root(tmp_path, binding.root_id))
    store.paths.state_file.parent.mkdir(parents=True)
    store.paths.state_file.write_text("{broken", encoding="utf-8")
    with pytest.raises(StateCorruptionError): store.load()
```

- [ ] **Step 2: Run tests and observe the missing state API**

Run: `python3 -m pytest -q tests/selfloop/test_root_state.py`

Expected: FAIL during collection because `RootStateStore` is undefined.

- [ ] **Step 3: Implement state creation and compare-and-swap writes**

`new_c0_state()` must emit `schema: selfloop.state.v2`, `revision: 0`, the root and campaign IDs, `status: running`, focus, `budgetProfile: standard`, null champion/generation/experiment fields, empty usage, zero exploration counters, null blocker, `conformanceStage: C0`, and a `compatibilityState` containing the P00 v1 fields. `save()` checks `expected_revision`, writes revision `expected_revision + 1` through a sibling temporary file plus `os.replace`, and rejects malformed JSON, schema mismatch, or root mismatch with `StateCorruptionError`.

Refactor the constructor to `CompatibilityController(home: Path, registry: RootRegistry, now: Callable[[], datetime])`, resolve the request root through `RootRegistry`, store C0 transitions in `RootStateStore`, and return only `compatibilityState` through v1 adapters. Update the P00 unit test to create a temporary Git root and registry. Import an existing selfloop-mode `goal_state.json` once when no root state exists; record `legacyImportedFrom` and never delete the source during migration.

- [ ] **Step 4: Run focused tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_root_state.py tests/selfloop/test_c0_controller.py`

Expected: all tests pass with no cross-root writes.

```bash
git add scripts/selfloop_supervisor/state.py references/selfloop/schemas/state-v2.example.json scripts/selfloop_supervisor/compat_controller.py tests/selfloop/test_c0_controller.py tests/selfloop/test_root_state.py
git commit -m "feat(selfloop): persist root-scoped state"
```

### Task 3: Generate a non-authoritative marker block in `state.yaml`

**Files:**
- Modify: `scripts/selfloop_supervisor/projection.py`
- Test: `tests/selfloop/test_state_projection.py`

**Interfaces:**
- Produces: `ProjectionWriter.write(repo_root, state) -> Path`, `split_projection(data: bytes) -> ProjectionParts`, and `normalize_projection_for_release(data: bytes) -> tuple[bytes, str | None]`.

- [ ] **Step 1: Write byte-preservation and normalization tests**

```python
def test_projection_preserves_all_operator_bytes(tmp_path):
    path = tmp_path / "state.yaml"
    path.write_bytes(b"version: 1\nnotes:\n  - keep me\n")
    ProjectionWriter().write(tmp_path, {"schema": "selfloop.state.v2", "rootId": "root-a", "campaignId": "campaign-a", "status": "running", "conformanceStage": "C0", "blocker": None})
    text = path.read_text(encoding="utf-8")
    assert text.startswith("version: 1\nnotes:\n  - keep me\n")
    assert text.count(PROJECTION_START) == 1
    assert "stableChampionReleaseId" not in text

def test_release_normalization_ignores_live_block_changes():
    first = f"project: SIPS\n{PROJECTION_START}\nrevision: 1\n{PROJECTION_END}\n".encode()
    second = f"project: SIPS\n{PROJECTION_START}\nrevision: 9\n{PROJECTION_END}\n".encode()
    assert normalize_projection_for_release(first)[0] == normalize_projection_for_release(second)[0]
    assert normalize_projection_for_release(first)[1] != normalize_projection_for_release(second)[1]
```

- [ ] **Step 2: Run tests and observe the missing projection module**

Run: `python3 -m pytest -q tests/selfloop/test_state_projection.py`

Expected: tests fail because P00 `projection.py` lacks `ProjectionWriter`, `ProjectionParts`, `split_projection`, and release normalization.

- [ ] **Step 3: Implement the exact marker contract**

Use `# >>> SIPS SELFLOOP GENERATED v1 >>>` and `# <<< SIPS SELFLOOP GENERATED v1 <<<`. Render only spec version, C0 stage, root ID, campaign ID, status, revision, blocker, and `authority: supervisor-projection-only`; omit champion and gate fields before C2. Replace an existing complete block or append one after a single newline. Reject duplicate or unterminated markers. `normalize_projection_for_release()` replaces only the block body with `projection: normalized-live-state`, returns the normalized bytes, and separately returns the SHA-256 of the actual complete generated block.

Define `ProjectionParts` as a frozen dataclass with `prefix: bytes`, `block: bytes | None`, and `suffix: bytes`; `split_projection()` is the only parser used by both the writer and release normalizer.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest -q tests/selfloop/test_state_projection.py`

Expected: both tests pass.

```bash
git add scripts/selfloop_supervisor/projection.py tests/selfloop/test_state_projection.py
git commit -m "feat(selfloop): add truthful state projection"
```

### Task 4: Carry root scope through every adapter

**Files:**
- Modify: `scripts/selfloop_cli.py`
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `tests/selfloop/test_c0_adapters.py`
- Modify: `tests/test_homebase_mcp.py`
- Modify: `scripts/validate_v2.py`

**Interfaces:**
- Consumes: `RootRegistry`, `RootStateStore`, and `ProjectionWriter`.
- Produces: CLI `--root <path>` and MCP root arguments that select the actual state namespace.

- [ ] **Step 1: Add a two-root adapter regression**

Start focus `alpha` through MCP root A and focus `beta` through CLI `--root B`; assert each status returns only its own campaign ID and focus, and each repository's generated block names its own root ID.

- [ ] **Step 2: Implement adapter propagation and validation**

Default CLI root to `git rev-parse --show-toplevel`; reject a non-Git root with exit 2. Pass MCP's already validated `workspace_root()` result to `run_action`. After every successful mutation, write the marker projection; status remains read-only. Add validator checks for one marker pair and prohibit any controller read from `state.yaml`.

- [ ] **Step 3: Run the C0-plus-root gate**

Run: `python3 -m pytest -q tests/selfloop tests/test_homebase_mcp.py && python3 scripts/run_tests.py goal_state --verbose && python3 scripts/validate_v2.py && git diff --check`

Expected: all commands exit 0; two-root tests prove isolation; advertised conformance remains C0.

- [ ] **Step 4: Commit root-scoped adapter support**

```bash
git add scripts/selfloop_cli.py scripts/harness_homebase_mcp.py tests/selfloop/test_c0_adapters.py tests/test_homebase_mcp.py scripts/validate_v2.py
git commit -m "feat(selfloop): scope adapters by registered root"
```
