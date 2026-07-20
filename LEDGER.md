# SIPS Improvement Ledger

## 2026-07-18 - 0.4.0

- Added a versioned SIPS controller with a strict task DAG, deterministic readiness, fenced leases, multidimensional reservations, structured slice admission, evidence gates, immutable receipts, replay, snapshots, and linked-run recovery.
- Added a physically separate, bounded cyclic Memory Fabric frontier backed by a rebuildable SQLite index; memory contributes context only and never changes task dependencies or readiness.
- Added CLI and Homebase MCP runtime read/write operations with idempotency and expected-revision guards, plus read-only legacy imports and compatibility projections.
- Made lesson capture candidate-first and receipt-bound; active writes now require promotion audits, and writer failure is recorded without claiming activation.
- Preserved the dirty main checkout and developed from its recorded HEAD in an isolated feature worktree. Source tests and legacy baselines pass; installation, fresh-host rediscovery, and controller-authoritative cutover remain separate proof gates.

Deliberately not done: `legacy` remains the default. `dual` and `runtime` execution fail closed until structured legacy results carry runtime lease, fencing, resource, and evidence contracts and clean-integration, parity, rollback, cache, and fresh-host gates pass.

## 2026-07-03 - 0.3.0

- Added nine Codex skills so SIPS Homebase renders as organized first-class skill rows instead of only generic MCP and hook sections.
- Added per-skill Codex display metadata and SVG icons for Control Plane, Proof Scanner, Delegation Router, Memory Fabric, Repo Map, Context Distiller, Execution Repro, Perception Plan, and Tool Factory.
- Updated `validate_v2.py` and `EVAL.md` to treat the skill surface as release-critical, then synced source into the `0.3.0` Codex cache copies.

Score: 99 -> 100. Context delta: +702 SKILL.md body words, +1449 skill-description chars.

Deliberately not done: no screenshot gallery asset yet; the priority in this pass was making the visible skill organization match the Codex Self Improvement reference.

## 2026-07-03 - 0.2.3

- Reorganized the Codex app presentation around Control Plane, Memory Fabric, Verification, Delegation, and Lifecycle Hooks so the home-base reads as a developer control plane instead of a generic productivity utility.
- Moved the Codex/NCode marketplace category to Developer Tools and rewrote starter prompts to expose distinct SIPS surfaces.
- Bumped Codex/NCode plugin versions to 0.2.3 for the presentation pass.

Score: 98 -> 99. Context delta: 0 skill-description chars, 0 SKILL.md body words.

Deliberately not done: no new skills were added because this pass targeted the app-card category and organization shown in Codex, not a new invocation surface.

## 2026-07-03 - 0.2.2

- Added `.agents/plugins/marketplace.json` so the SIPS repo is a supported Codex marketplace root, not only an NCode marketplace/plugin source.
- Bumped Codex/NCode plugin versions to 0.2.2 for the marketplace packaging change.

Score: 96 -> 98. Context delta: 0 skill-description chars, 0 SKILL.md body words.

## 2026-07-03 - 0.2.1

- Updated the Codex plugin interface with a shorter display subtitle plus `composerIcon` and `logo` assets so the local plugin renders with a real SIPS identity in Codex.
- Changed `hooks/hooks.json` command roots from `${CLAUDE_PLUGIN_ROOT}` to `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`, preserving legacy host behavior while making SIPS plugin-root resolution Codex-first.
- Updated `validate_v2.py` to require the portable hook-root syntax and to track the 0.2.1 manifest/marketplace version.

Score: 91 -> 96. Context delta: 0 skill-description chars, 0 SKILL.md body words.

Deliberately not done: no new skills were added because SIPS is currently an MCP/homebase plugin and the pass target was package quality, not a new invocation surface.

## 2026-07-07 - 0.3.1

- Removed the stale `.claude/worktrees/cool-cannon-0f0a3e` worktree (1.4 MB, clean, commits preserved on branch `claude/cool-cannon-0f0a3e`) and added `.claude/` + `.pytest_cache/` to `.gitignore` so untracked junk no longer ships into Codex cache copies; the installed 0.3.0 cache carried a full duplicate plugin snapshot including a second hooks.json.
- sips-memory-fabric: description now triggers on the write side ("record a just-fixed bump"), body gains the capture procedure (`memory_fabric_record` then confirm via `homebase_recall`). Evidence: 2026-07-07 session mining found recurring bumps (skill-path ENOENT, rg exit-1 retries) never captured despite the AGENTS.md standing instruction.
- Version-sync 0.3.1 across plugin.json, ncode marketplace, validate_v2 EXPECTED_VERSION, homebase MCP DEFAULT_PLUGIN_VERSION, EVAL.md, tests; synced source into harness-local cache 0.3.1.

Score: 100 -> 100 (worktree shipping was an unscored latent flaw). Context delta: +39 SKILL.md body words (+5.6%), +62 skill-description chars (+4.3%).

Deliberately not done: ralto-local cache copy of harness-self-improvement left at 0.3.0 — ralto-local is a 14-plugin marketplace and its sync ownership is unresolved (see plugin-improver ledger 0.3.2); resolving that marketplace root is the right fix, not another manual copy.

### 2026-07-07 addendum (0.3.1)
ralto-local deferral closed: a proper marketplace root now exists at ~/plugins/ralto-local (9 plugins via symlinks, .agents manifest) and is registered in config.toml. harness-self-improvement deliberately excluded — harness-local remains its sole owner; the stale ralto cache copy is now unreferenced by any manifest.

## 2026-07-13 — 0.3.1 verification pass (plugin-improve; no changes shipped)
- User asked for "SIPS on ralto-local"; clarified: improve in place, ownership
  stays with harness-local per the 0.3.1 addendum's deliberate exclusion.
- Baseline 100/100 treated as hypothesis and re-verified live (plugin-improve
  0.3.4 rule): validate_v2.py exit 0; pytest 16/16 green — on TOP of the
  uncommitted working tree (22 modified files from the 2026-07-11 audit pass),
  so the drift is verified-good, not rot.
- Outcome: STABLE. No rubric point is gainable; no change clears the
  no-churn bar. Zero diffs, no version bump.
- Remaining capability work lives in SIPS_IMPROVEMENT_PLAN.md (Phase 1: close
  the memory loop) — explicitly capability development for delegated Codex
  sessions, out of scope for a bounded improvement pass.
- Deliberately not done: screenshot gallery asset (presentation nicety,
  mid-flight tree); ralto-local migration (user chose against).

## 2026-07-14 — selfloop cycle 1: self-correction signal precision

- Baseline: `self_correct.py --json` reported 166 scripts as untested and falsely
  included scripts with direct pytest coverage, including
  `retry_lesson_reminder.py`, `sips_paths.py`, `worktree_scope.py`, and
  `eval_grader_parity.py`.
- Change: coverage discovery now reads both the bespoke `run_tests.py` runner
  and `tests/test_*.py`, recognizing explicit script paths and imported modules.
- Measured gain: the list fell to 158; the four proven false positives are gone,
  while a synthetic uncovered helper remains detected.
- Verification: focused pytest 7/7; full harness 91/91; full pytest 21/21;
  validator 134/134; EVAL drift, compileall, and diff hygiene all pass.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/be3a23bd65ac9bd2`.

## 2026-07-14 — selfloop cycle 2: integration-coverage tracing

- Baseline: 154 of the 158 scripts still labeled untested were statically
  reachable from test-covered entrypoints through local imports.
- Change: `self_correct.py` now follows the local Python import graph from
  directly tested scripts and emits the remaining candidates deterministically.
- Measured gain: the signal narrowed from 158 candidates to four:
  `harness_browser_mcp.py`, `memory_fabric_benchmark.py`,
  `memory_fabric_mcp_reload_order.py`, and `memory_fabric_mcp_runtime.py`.
- Verification: a regression fixture proves both transitive coverage and a true
  uncovered control; full harness 91/91, pytest 21/21, validator 134/134, EVAL
  drift, compileall, and diff hygiene all pass.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/a56651bd7e818f06`.

## 2026-07-14 — selfloop cycle 3: MCP runtime reload regressions

- Baseline: `memory_fabric_mcp_runtime.py` and
  `memory_fabric_mcp_reload_order.py` were both outside the test graph despite
  protecting live MCP freshness.
- Change: added focused regressions for pinned reload ordering, exclusion of the
  runtime controller, stale-to-ready receipts, and the explicit current-live
  proof boundary.
- Measured gain: both modules left the untested list; only
  `harness_browser_mcp.py` and `memory_fabric_benchmark.py` remain.
- Verification: focused pytest 3/3; full harness 91/91; full pytest 23/23;
  validator 134/134; EVAL drift, compileall, and diff hygiene all pass.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/c44850b713e5a530`.

## 2026-07-14 — selfloop cycle 4: restore SIPS-owned policy benchmark

- Baseline: `scripts/memory_fabric_benchmark.py --help` crashed because the
  4,272-line `fixtures/benchmarks/policy_benchmark.py` implementation was omitted
  by the Memory Fabric vendoring commit.
- Discovery: restoring the byte-identical archived fixture exposed eight
  release-report failures from hardcoded standalone `codex-memory-fabric`
  identity; the first dynamic-identity pass then exposed cache-copy recursion
  through the intentional `plugins/harness-self-improvement -> ..` wrapper.
- Change: restored the archived fixture byte-for-byte, made install/doctor/cache/
  marketplace/MCP helpers derive the active SIPS identity while retaining the
  standalone fallback, and excluded symlinks from cache copy payloads.
- Measured gain: benchmark moved from a startup `FileNotFoundError`, through
  69/77 behavior passes, to 77/77. The self-correction gap list now contains only
  the legacy `harness_browser_mcp.py` adapter.
- Verification: benchmark 77/77; harness 91/91; pytest 25/25; validator 134/134;
  plugin validator, EVAL drift, compileall, and diff hygiene all pass.
- Durable receipt: `$HOME/.codex/sips/receipts/selfloop/cycle-4-policy-benchmark.json`
  (SHA-256 `897feaec673c71336a87bf29044f136f1b468a5651ead459b2dcd7604ee5f068`).
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/c44850b713e5a530`.

## 2026-07-14 — selfloop cycle 5: restore browser vision dispatch

- Baseline: `self_correct.py --json` reported `harness_browser_mcp.py` as the
  only untested script, and a direct `browser_see` exercise crashed with
  `NameError: name 'subprocess' is not defined` after a successful screenshot.
- Change: imported `subprocess` and added a focused regression for the
  screenshot-to-local-VLM command and MCP response path.
- Measured gain: the regression moved from the reproduced `NameError` to pass,
  and `self_correct.py --json` now reports zero untested scripts.
- Verification: focused pytest 1/1; full harness 91/91; full pytest 26/26;
  Memory Fabric benchmark 77/77; validator 134/134; plugin validator, EVAL
  drift, compileall, and diff hygiene all pass.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/04458779718524d5`.

## 2026-07-14 — selfloop cycle 6: refresh the canonical installed cache

- Baseline: the enabled `harness-local` 0.3.1 cache still ran pre-cycle code:
  `self_correct.py --json` reported 166 gaps, its Memory Fabric benchmark
  crashed with a missing policy fixture, and key source/cache hashes diverged.
- Change: refreshed the same-version canonical install with
  `codex plugin add harness-self-improvement@harness-local`, preserving the
  existing MCP policy block rather than removing and re-adding the plugin.
- Measured gain: the installed benchmark moved from `FileNotFoundError` to
  77/77, installed self-correction moved from 166 gaps to zero, and hashes for
  the self-correction code, browser adapter, fixture, and browser regression now
  match source.
- Verification: installed harness 91/91; installed pytest 26/26; installed
  validator 134/134; installed browser regression 1/1; TOML parses; the
  `sips-homebase` block remains enabled; MCP freshness passes source/cache/
  config/child-process checks.
- Boundary carried forward: host audit reports two missing hook trust rows,
  `homebase_selfloop` is absent from the host enabled-tool allowlist, and this
  already-open task has not rediscovered local SIPS tools.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/81335e1d2d50ad19`.

## 2026-07-14 — selfloop cycle 7: make MCP allowlist freshness truthful

- Baseline: `homebase_mcp_freshness` returned `fresh` although child
  `tools/list` advertised 16 tools and the host allowlist enabled only 15,
  omitting `homebase_selfloop`.
- Change: the checker now parses the exact SIPS plugin MCP block without a new
  runtime dependency, compares an explicit `enabled_tools` allowlist to child
  advertisement, and reports configured and missing tools. The local host
  config now enables and approves `homebase_selfloop`.
- Measured gain: the focused regression moved from the reproduced false-green
  result to pass. Installed freshness now reports 16/16 tools and no omissions;
  `codex mcp get sips-homebase --json` includes `homebase_selfloop`.
- Verification: installed Homebase pytest 8/8; source harness 91/91; source
  pytest 27/27; validator 134/134; plugin validation, compileall,
  self-correction, and diff hygiene pass; source/cache checker and test hashes
  match; host audit passes with 20 trusted hook rows.
- Boundary: this already-open task still exposes no local SIPS MCP tools, so
  task-registry rediscovery remains unproven.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/81335e1d2d50ad19`.

## 2026-07-14 — selfloop cycle 8: remove the obsolete live NCode mirror

- Baseline: the active `PostToolUse` manifest and host trust state still ran
  `sips_presence_mirror.py`; its isolated suite proved that it copied
  `.codex/sips` into `.ncode/sips`, contradicting the current history-only
  `.ncode` policy and the existing state receipt that said the hook was gone.
- Change: removed the active mirror hook and its host trust row, kept the helper
  only as an explicitly documented manual legacy compatibility utility, and
  regenerated `EVAL.md` for the 19-hook lifecycle.
- Measured gain: Codex Desktop app-server `hooks/list` now reports exactly 19
  SIPS hooks, all trusted and enabled, with no mirror entry.
- Verification: installed host audit passes; source/cache hook, EVAL, and README
  hashes match; harness 91/91; pytest 27/27; validator 132/132; plugin
  validation, compileall, self-correction, and diff hygiene pass. The retained
  manual helper suite remains 3/3.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/59024eb8ce616960`.

## 2026-07-14 — selfloop cycle 9: unify proactive coverage drift

- Baseline: the active source and installed `proactive_drift.py` SessionStart
  hooks emitted five untested-script findings while canonical
  `self_correct.py --json` reported zero coverage gaps. The hook used a separate
  filename-and-substring heuristic and looked for tests below the SIPS state
  directory rather than the repository.
- Change: the hook now reuses `self_correct.find_untested_scripts()` and caps
  only the presentation layer. A focused regression covers a pytest-referenced
  entrypoint, its transitive local import, and a genuinely uncovered control.
- Measured gain: the focused regression moved from failure to pass; both source
  and installed SessionStart hook executions moved from five false findings to
  silent output while the uncovered control remains detected.
- Verification: source/cache hashes match; source and installed self-correction
  report zero gaps; source and installed harness 91/91, pytest 28/28, validator
  132/132, and installed host audit pass; source benchmark remains 77/77; plugin
  validation, EVAL drift, compileall, and diff hygiene pass.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/59024eb8ce616960`.

## 2026-07-14 — selfloop cycle 10: retire NCode writes without breaking hot refresh

- Baseline: the live mirror hook was gone, but source and installed packages
  still shipped `sips_presence_mirror.py`, an executable that copied active
  `.codex/sips` presence files into history-only `.ncode/sips`. The architecture,
  CI, legacy suite, README, and plugin-improver inventory preserved the path.
- Change: removed the writer behavior and its active architecture, legacy-suite,
  and CI surfaces. The first literal file deletion exposed a loaded-task
  boundary: this already-open task retained the old hook command and recorded
  repeated exit-2 file-not-found events after the same-version cache refresh.
  The retired path is therefore retained through 0.3.1 as a four-line inert
  tombstone, guarded by a validator marker and a behavior regression that proves
  it is silent and creates no `.ncode` state.
- Measured gain: the focused tombstone regression and 133rd validator check both
  moved red to green. After the corrected cache refresh, 26 stale-dispatch events
  in this loaded task all exited 0; source and installed direct executions are
  silent and perform no I/O.
- Verification: source/cache hashes match for the tombstone, regression,
  validator, EVAL, architecture, README, runner, and CI. Sequential
  source and installed harness 91/91, pytest 29/29, validator 133/133, plugin
  validation, self-correction, and host audit pass; source benchmark remains
  77/77; EVAL drift, compileall, and diff hygiene pass.
- Verification failures kept explicit: the unsupported `codex plugin validate`
  command exited 2; the established `validate_plugin.py` check passed. Running
  source and cache suites concurrently caused a source JSON parse crash and a
  stale-cache EVAL failure; after serializing the suites and refreshing after
  the final EVAL write, both copies passed.
- Boundary: this task still dispatches the cached retired hook path, safely
  absorbed by the tombstone. A fresh task or app restart must prove the path is
  no longer dispatched. Remove the tombstone only with a versioned cache path
  transition, not another same-version 0.3.1 refresh. The dated
  `.plugin-improver/baseline.json` remains a historical 2026-07-13 snapshot and
  is not treated as current inventory proof.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/7fb6a85702bccde0`.

## 2026-07-14 — selfloop cycle 11: restore Codex default prompts

- Baseline: the installed SIPS manifest declared four `defaultPrompt` entries.
  A direct Codex Desktop 0.144.1 app-server startup warned that the maximum is
  three and ignored `interface.defaultPrompt` for SIPS.
- Change: retained the Control Plane, Proof Scanner, and Memory Fabric starter
  prompts, removed the fourth quick-start entry, and added a manifest validator
  guard requiring one to three prompts.
- Measured gain: the new check moved from 133/134 failure at count four to
  134/134 pass at count three. After the same-version cache refresh, app-server
  emitted no SIPS default-prompt warning; source/cache manifest hashes match and
  all 19 SIPS hooks remain enabled and trusted.
- Verification: sequential source and installed harness 91/91 and pytest 29/29;
  source and installed validator 134/134; source benchmark 77/77; plugin
  validation, EVAL drift, compileall, self-correction, host audit, and diff
  hygiene pass.
- Boundary: the probe still emitted two default-prompt warnings for the separate
  plugin-improver plugin and two unscoped skill-icon warnings. This cycle does
  not claim those warnings fixed.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/7c6bef1a9a29fe1e`.

## 2026-07-14 — selfloop cycle 12: require live hook trust proof

- Baseline: `homebase_host_audit` compared the expected SIPS hook keys only
  with `hooks.state` row names in `~/.codex/config.toml`. A synthetic catalog
  where every row matched but the live hook had `trustStatus=modified` still
  returned `passed`.
- Change: `homebase_host_audit.v2` now starts a bounded Codex app-server for the
  audited root, calls `hooks/list`, selects the exact working-directory group,
  and checks exact SIPS plugin identity, key presence, enablement, trust status,
  current hash receipts, duplicates, and catalog diagnostics. Probe failures
  return structured `attention` rather than falling back to a config-only pass.
- Measured gain: the false-green regression moved from failure to pass. The
  canonical source and installed cache both report 19/19 expected live SIPS
  hooks, with zero disabled, untrusted, unhashed, duplicated, or missing hooks
  and zero findings. A modified unrelated Etsy hook is ignored by exact plugin
  filtering.
- Verification: sequential source and installed harness 91/91 and pytest
  32/32; source and installed validator 134/134; source benchmark 77/77; plugin
  validation, EVAL drift, Python 3.9 compile, self-correction, YAML, and diff
  hygiene pass. Source/cache hashes match for the Homebase MCP, regression, and
  README.
- Boundary: the runtime receipt proves a freshly spawned app-server's catalog
  for this root. It does not prove that this already-open task has discarded its
  stale retired-hook dispatcher entry or rediscovered the refreshed MCP tools.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/fe043a90b38e9fdd`.

## 2026-07-14 — selfloop cycle 13: compact host-audit context

- Baseline: the generic MCP renderer interpolated the entire `runtime_hooks`
  dictionary into Markdown. A clean 19-hook audit produced 5,798 characters in
  one line, including every hook key and SHA-256 hash, even though the same
  complete receipt was already present in `structuredContent`.
- Change: the renderer now keeps `runtime_hooks` out of the generic scalar list
  and emits a bounded section with status, observed/expected counts, duplicate,
  disabled, untrusted, and unhashed counts, catalog diagnostics, and probe error
  when present. Findings and the already-open-task claim boundary remain visible.
- Measured gain: source Markdown fell from 5,798 to 660 characters (about 89%)
  and the installed-cache path renders in 697 characters. The source structured
  receipt remains 5,761 characters and retains all 19 keys and current hashes.
- Verification: the focused rendering regression moved red to green; sequential
  source and installed harness 91/91 and pytest 33/33; source and installed
  validator 134/134; source benchmark 77/77; plugin validation, EVAL drift,
  Python 3.9 compile, self-correction, YAML, and diff hygiene pass. Source/cache
  hashes match for the renderer, regression, and README.
- Boundary: this is a context-efficiency improvement only. It does not remove
  structured proof or change the fresh-app-server versus already-open-task
  rediscovery boundary.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/2016c1b46b1da273`.

## 2026-07-14 — selfloop cycle 14: transactional source version bumps

- Baseline: `scripts/bump_version.py` did not exist and a direct invocation
  failed with file-not-found. Release `0.3.1` was synchronized across seven
  machine surfaces: three manifests, two Python constants, and two hardcoded
  MCP assertions, with `EVAL.md` as an eighth generated surface.
- Change: `plugin.json` is now the version source of truth for validation and
  MCP initialization; the cache-path test is synthetic rather than tied to the
  installed release; the unknown-manifest fallback is stable `0.0.0`. The new
  helper therefore edits only `plugin.json`, the NCode marketplace manifest,
  and `pyproject.toml`. It validates a strictly increasing SemVer, preserves
  other bytes and modes, preflights EVAL coherence, writes atomically,
  regenerates EVAL through `validate_v2.py`, runs validator/harness/pytest, and
  restores exact pre-bump manifest and EVAL bytes if any gate fails.
- Failure kept explicit: the first real `0.3.1 -> 0.4.0` run in an isolated repo
  passed validator and 91/91 harness checks, then pytest failed because the new
  dry-run regression itself hardcoded `0.4.0`. The helper rolled every target
  back to `0.3.1`, including EVAL. The test now derives a greater version from
  the current manifest; the second isolated bump passed all gates and left the
  isolated manifests plus generated EVAL at `0.4.0`.
- Verification: source and installed dry runs list exactly three files and write
  nothing; focused regressions cover SemVer rejection, monotonicity, byte-exact
  rollback, and dry-run identity. Sequential source and installed harness 91/91
  and pytest 45/45; source and installed validator 134/134; source benchmark
  77/77; plugin validation, Python 3.9 compile, self-correction, EVAL drift,
  YAML, and diff hygiene pass. Source/cache hashes and executable mode match.
- Boundary: the helper intentionally does not refresh caches, edit config or Git
  state, promote README release notes, commit, push, or publish. `vermin` was not
  available in this shell, so that optional local check was not run.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/fbd592687e4b54f3`.

## 2026-07-14 — selfloop cycle 15: close weekly sweep capture

- Baseline: `weekly_sweep.py` documented a learning-tier Memory Fabric record
  as its sixth step, but the implementation ended after its snapshots and
  summary. A clean scheduled sweep therefore had no durable Memory Fabric
  outcome despite claiming that loop closure in the module documentation.
- Change: the sweep now writes an atomic `sips.weekly_sweep.v1` JSON receipt
  under the active SIPS home and cites that existing artifact when calling the
  local `memory_fabric.py record` path. Clean critical steps produce an
  `active`/high-confidence learning; failed critical steps produce a
  `candidate`/medium-confidence/verify-before-use learning. Receipt or record
  failure makes the sweep exit non-zero. `SIPS_MEMORY_SCOPE` can provide a
  stable source scope for installed/scheduled runs.
- Secondary failure kept explicit: after the weekly regressions were added,
  `self_correct.py --json` reported `validate_v2.py` as untested. The validator
  was already executed by `tests/test_verification_commands.py`; the detector
  ignored quoted paths containing `scripts/` and then accidentally searched
  only the lexicographically last pytest file. A path-qualified, ordering-aware
  regression reproduced the false warning. Coverage discovery now uses each
  quoted Python path's basename and no longer consults a stale last-file buffer.
- Measured gain: an isolated Memory Fabric store receives a real active/high
  learning whose JSON receipt exists; failed capture is a critical sweep
  failure; self-correction returns to zero gaps with `validate_v2.py` correctly
  recognized.
- Verification: focused weekly/self-correction regressions 5/5; sequential
  source and installed harness 91/91 and pytest 49/49; source and installed
  validator 134/134; source benchmark 77/77; plugin validation, Python 3.9
  compile, self-correction, EVAL drift, YAML, and diff hygiene pass. Source/cache
  hashes match for the sweep, detector, tests, README, and plan.
- Boundary: this cycle did not execute the live scheduled sweep because it also
  performs snapshot pruning. Automatic retro-miner ingestion of unresolved
  cross-session retry chains remains future work.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/4f18c7746fde3dad`.

## 2026-07-14 — selfloop cycle 16: retro-miner integration plateau

- Target: validate the remaining plan item that would feed Retro transcript
  retry-chain statistics into the weekly SIPS Memory Fabric record.
- Baseline: both the Retro source script and installed cache are present and
  advertise Codex JSON output through `--codex --stats --json`.
- Evidence: the miner reported `tool_errors: 0`, no retry chains, and no
  unresolved failures for this task's rollout. A bounded direct JSONL parse of
  that same rollout found 12 failing custom/function tool-output records,
  including intentionally red pytest and validator runs from this self-loop.
- Outcome: PLATEAU (first consecutive plateau). Wiring the current miner would
  create false-green Memory Fabric evidence. Repairing the separately owned
  Retro plugin or authoring a duplicate transcript miner is a material scope
  expansion, not a bounded SIPS improvement.
- Change: none to runtime code. The cycle-15 source/cache green baseline remains
  the current implementation proof.

## 2026-07-14 — selfloop cycle 17: cache and historical-memory plateau

- Target: independently audit the remaining cache-hygiene and historical-memory
  rejoin candidates for a safe, bounded SIPS improvement.
- Evidence: the only unreferenced cache candidate is an empty, zero-byte
  `ralto-local/ralto-local` directory. The historical
  `~/.codex/sqlite/memories_1.sqlite` contains seven records across Estate,
  Kickbacks/Hermes, and StorageScope; none has an exact thread/rollout match in
  the live Memory Fabric JSONL store.
- Outcome: PLATEAU (second consecutive plateau). Deleting a zero-byte directory
  is destructive with no measurable benefit. Rejoining the seven cross-project
  records needs per-record semantic deduplication, correct scope selection, and
  external Memory Fabric writes; bulk migration would exceed this repo-local
  cycle's authority and proof boundary.
- Change: none to runtime code. No cache was deleted and no historical record
  was migrated. The cycle-15 source/cache green baseline remains current.
- Stop: cycles 16 and 17 independently reached plateau, satisfying the SIPS
  selfloop stop rule.

## 2026-07-15 — focused selfloop cycle 1: layered local-plugin MCP exposure proof

- Baseline: the supplied ChatGPT screenshots prove that SIPS Homebase is visible
  with one MCP server and ten skills, and that `sips-homebase` is enumerated under
  plugin connections. Host logs prove ChatGPT and its app-server restarted at
  21:47 and this task was created afterward. Config and installed-child proof were
  green at 16/16 tools, but the task's complete 416-tool inventory contained zero
  SIPS/Homebase tools. A skill link injected skill text without attaching the
  deferred local-plugin MCP.
- Change: `homebase_mcp_freshness` now accepts explicit current-task inventory
  evidence, distinguishes omitted/truncated evidence from a complete empty SIPS
  result, recognizes namespaced tool forms, preserves the local `status`, and adds
  `overall_status` plus a bounded `task_exposure` receipt. A locally fresh install
  can now truthfully return `task_tools_missing` instead of false-green freshness.
- App-shot triage: `homebase_perception_plan.v2` emits separate visual,
  host-configuration, child-advertisement, and task-invocation proof layers. The
  `sips-perception-plan` skill now states that UI listing is enumeration proof,
  not current-task callability.
- Repaired dependency: the first JSONL perception-plan verification exposed a
  pre-existing renderer crash (`'list' object has no attribute 'items'`) because
  generic rendering assumed every `checks` value was a dictionary. A regression
  moved red to green and list checks now render normally.
- Verification: four focused regressions moved red to green; sequential source
  and installed harness 91/91, pytest 53/53, validator 134/134; source Memory
  Fabric benchmark 77/77; plugin validation, EVAL drift, self-correction, config
  parsing, and diff hygiene pass. Source/cache hashes match for the MCP, skill,
  and tests. Same-version cache refresh left the config hash unchanged. The
  installed receipt returns local `fresh`, overall `task_tools_missing`, zero
  present tools, and all 16 expected tools missing.
- Boundary: no `tool_search` capability is exposed in this task and no local SIPS
  MCP process was attached, while bundled plugin MCPs did attach. This cycle
  improves detection and fallback accuracy; it does not repair or classify the
  remaining host behavior as a crash. The next discriminating test is explicit
  `plugin://harness-self-improvement@harness-local` activation, not another restart
  or ordinary fresh task.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/610f1cc6d119d210`.

## 2026-07-15 — focused selfloop cycle 2: adversarial task-proof hardening

- Baseline: the first task-exposure classifier accepted any MCP namespace whose
  suffix matched a Homebase tool, described complete inventory advertisement as
  availability, treated generic connection screens as plugin surfaces, and had
  no regression proving that truncated inventories remain non-errors.
- Change: task matching now accepts only exact tool names or normalized
  `sips-homebase` namespaces. The receipt separates task advertisement from
  task-local successful invocation, reports `task_tools_advertised_callability_unproven`
  until invocation exists, rejects conflicting invocation/absence evidence, and
  leaves truncated inventories unproven. App-shot planning triggers only for
  plugin/MCP targets and labels the screenshots as UI-enumeration proof only.
- Measured gain: six adversarial regressions moved red to green, and the focused
  Homebase suite now passes 21/21. Installed receipts cleanly distinguish a
  complete empty task inventory (`task_tools_missing`, error), all 16 advertised
  but uninvoked tools (`task_tools_advertised_callability_unproven`, non-error),
  and a successful named invocation (`fresh`, callability verified).
- Verification: sequential source and installed harness 91/91, pytest 58/58,
  and validator 134/134 pass. Source benchmark remains 77/77; plugin validation,
  compile, self-correction, EVAL drift, and diff hygiene pass. Source/cache hashes
  match for the Homebase MCP, its tests, and the perception skill. Same-version
  cache refresh left the config SHA-256 unchanged.
- Boundary: the classifier can now describe host/task evidence without
  false-green callability, but this task still contains no SIPS MCP tool to
  invoke. Historical rollouts prove explicit plugin selection is neither
  necessary nor sufficient by itself. The next controlled discriminator is a
  separate task launched through SIPS Homebase's actual plugin picker, followed
  by a named `homebase_status` invocation and rollout inspection.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/63bad1fd07295054`.

## 2026-07-15 — focused selfloop cycle 3: plugin-picker discriminator blocked

- Baseline: source, installed cache, config, child `tools/list`, host hooks, and
  post-restart task timing are proven. The current task still has a complete
  416-tool inventory with zero SIPS/Homebase tools and exposes no `tool_search`
  capability, so it cannot perform a task-local Homebase invocation.
- Historical discriminator: a July 2 task successfully resolved and invoked
  SIPS without explicit plugin selection, while a July 3 task explicitly selected
  SIPS and resolved no Homebase tools. Explicit activation is therefore neither
  necessary nor sufficient in the available evidence; it remains a controlled
  host discriminator rather than a proven repair.
- Outcome: blocked with no runtime mutation. The required next proof must begin
  in a separate task launched through SIPS Homebase's actual plugin picker, ask
  for `homebase_status`, and preserve evidence of capability injection,
  `tool_search` resolution, and the actual call. Another restart or ordinary
  source/cache refresh would repeat already-proven layers.
- Stop: the focused selfloop was paused after recording the external block. It
  should resume against the plugin-picker task receipt, not restart this audit.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/b69eab9570cc9b5f`.

## 2026-07-15 — focused selfloop cycle 4: preserve fallback transport truth

- Baseline: the plugin-picker `Try now` task reported `isError: false`, but its
  rollout contained no SIPS tool advertisement or native invocation. The outer
  task call was `exec`; it piped JSON-RPC `initialize` and `tools/call` records
  into the repo-local Homebase Python script.
- Change: `homebase_status` now emits structured proof layers for source,
  worktree, installed cache, host config, task advertisement, task callability,
  and transport. Missing source roots return `source_not_found` with an MCP
  error. The control-plane skill preserves the successful inner source
  subprocess while forbidding native-task wording or invocation credit.
- Measured gain: the same receipt is now classified as a successful repo-local
  source-subprocess call with native host callability unproven, rather than a
  native SIPS call.
- Verification: adversarial missing-root, transport, and wording regressions
  pass; source and installed harness 91/91, pytest 61/61, validator 134/134;
  source benchmark 77/77; plugin validation, compile, self-correction, EVAL
  drift, diff hygiene, source/cache hashes, and config-hash preservation pass.
- Boundary: this cycle corrected the proof language. It did not repair the
  plugin MCP launch failure discovered in the next cycle.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/b69eab9570cc9b5f`.

## 2026-07-15 — focused selfloop cycle 5: repair plugin MCP launch and prove native callability

- Baseline: Codex CLI 0.144.1 launched plugin MCP arguments literally. The SIPS
  manifest passed `${PLUGIN_ROOT}/scripts/harness_homebase_mcp.py`, producing a
  file-not-found error; the identical server registered globally with an
  absolute path invoked `homebase_status` successfully.
- Change: `.mcp.json` now uses `./scripts/harness_homebase_mcp.py` with
  `cwd: "."`, matching the portable shape used by bundled plugins. The existing
  validator check now requires that exact launch form, a regression protects it,
  README documents it, and the control-plane skill searches deferred tools
  before declaring Homebase missing.
- Measured gain: post-refresh host trace reports `sips-homebase` startup complete
  with all 16 tools. A fresh isolated task with
  `features.tool_search_always_defer_mcp_tools=false` exposed and invoked
  `mcp__sips_homebase__homebase_status` successfully. Source/cache hashes match,
  and the same-version refresh preserved the config SHA-256
  `7b40165c08bd4754ab4991d7502b1e92abb3b559e42177e1852c73ae506e60c1`.
- Verification: source and installed harness 91/91, pytest 62/62, validator
  134/134; source benchmark 77/77; plugin validation, Python compile,
  self-correction, EVAL drift, and diff hygiene pass. The initial post-edit
  pytest run correctly failed only on generated EVAL drift; regenerating EVAL
  moved the complete suite green.
- Boundary: native plugin transport and callability are proven in a fresh CLI
  task. The eager-exposure override was intentionally not persisted because it
  is host-global and increased that task's input from roughly 23k to 51k tokens.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/a38cc8c826892ed1`.

## 2026-07-15 — focused selfloop cycle 6: post-refresh Desktop rediscovery blocked

- Evidence: two fresh default Codex 0.144.1 tasks still reported
  `tool_search` unavailable and did not call Homebase, even though host trace
  listed the repaired `sips-homebase` server and 16 tools. Disabling deferred
  MCP exposure for one isolated task produced the successful native call above.
- Outcome: blocked. The remaining layer is default deferred-tool injection, not
  SIPS transport or source behavior. No supported plugin manifest field was
  found that safely forces eager task exposure, and a global context-expanding
  workaround was not persisted.
- Required next proof: restart ChatGPT after this repaired cache refresh, create
  a fresh task through SIPS Homebase's `Try now` surface, ask it to invoke
  `homebase_status`, and preserve the actual native call event. This task was
  created before the repaired installed cache and cannot prove Desktop
  rediscovery.
- Stop: the focused selfloop is paused at that external post-refresh Desktop
  boundary.

## 2026-07-18 — focused selfloop cycle 7: bound MCP receipt rendering

- Baseline: `homebase_recall` rendered 18,109 Markdown characters, including
  15,357 characters of duplicated raw receipt stdout even though the complete
  receipt was already present in `structuredContent`.
- Change: the generic Homebase renderer now omits raw `receipt.stdout` from
  Markdown and emits bounded status, command, return code, stdout size, and
  bounded stderr metadata. Machine-readable `structuredContent` is unchanged.
- Measured gain: source Markdown fell to 2,321 characters and installed-cache
  Markdown to 2,358 characters; raw stdout is absent from both while six
  structured records and the complete receipt remain available.
- Verification: source and installed Homebase pytest 26/26, source and
  installed harness 91/91, full pytest, `validate_v2.py --check-eval` 134/134,
  Memory Fabric benchmark 77/77, self-correction zero gaps, source/cache
  hashes, diff hygiene, and YAML parsing pass.
- Boundary: source and installed rendering are proven. Ordinary fresh-task MCP
  rediscovery remains a separate host proof layer.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/6ad6b2c1f0ce47f5`.

## 2026-07-18 — focused selfloop cycle 8: bound selfloop state rendering

- Baseline: installed `homebase_selfloop` status rendered 10,122 Markdown
  characters, serializing the full nested cycle history as a scalar.
- Change: the generic Homebase renderer now emits bounded state metadata:
  status, mode, focus/objective, turn and cycle counts, current-cycle outcome
  and summary, and history count. Full state remains in `structuredContent`.
- Measured gain: source Markdown fell to 1,240 characters and installed-cache
  Markdown to 1,277 characters; all seven history entries remain structured.
- Verification: source and installed Homebase pytest 27/27, source and
  installed harness 91/91, full pytest, `validate_v2.py --check-eval` 134/134,
  self-correction zero gaps, source/cache hashes, diff hygiene, and YAML
  parsing pass.
- Boundary: rendering is proven in source and installed cache. Ordinary
  fresh-task MCP rediscovery remains a separate host proof layer.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/6bbd59c1a16d0aa7`.

## 2026-07-18 — focused selfloop cycle 9: bound Homebase surface lists

- Baseline: installed `homebase_status` rendered 10,723 Markdown characters,
  including all 206 script names in its human-readable Surfaces section.
- Change: list-valued surfaces now render a bounded count and 12-item sample;
  the complete values remain in `structuredContent`.
- Measured gain: source Markdown fell to 4,019 characters and installed-cache
  Markdown to 4,056 characters; the full scripts list is absent from both.
- Verification: source and installed Homebase pytest 28/28, source and
  installed harness 91/91, full pytest, `validate_v2.py --check-eval` 134/134,
  self-correction zero gaps, source/cache hashes, diff hygiene, and YAML
  parsing pass.
- Boundary: status rendering is proven in source and installed cache. Ordinary
  fresh-task MCP rediscovery remains a separate host proof layer.
- Checkpoint: `$HOME/.codex/sips/backups/snapshots/c5ff5ea79d1d487e`.

## 2026-07-18 — focused selfloop cycle 10: fresh-task rediscovery blocked

- Baseline: the current task is green: `homebase_mcp_freshness` reports local
  freshness, 16/16 configured and child-advertised tools, a complete current
  task inventory, 16/16 present, and verified callability after native
  invocations.
- Outcome: blocked. No source mutation was made. The remaining proof requires
  restarting ChatGPT or launching a separate SIPS Homebase `Try now` task and
  preserving its native server/tool event; this task cannot create that external
  boundary.
- Boundary: further local renderer changes would be scope churn until the
  fresh-task discriminator is available.
