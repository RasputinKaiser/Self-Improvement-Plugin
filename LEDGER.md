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
