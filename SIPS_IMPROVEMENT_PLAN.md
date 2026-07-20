# SIPS Improvement Plan — written 2026-07-07 by Claude (Cowork)

Context: SIPS is at 0.3.1, audit score 100/100 (rubric ceiling), all tests green,
live in Codex (proven via skill-roots in fresh rollout). Score can't go higher —
every item below targets *capability*, ordered by leverage. Each phase is
self-contained and sized for delegation to Codex sessions (separate quota).
Evidence sources: 2026-07-07 mining of 8 Codex rollouts, SIPS LEDGER.md,
plugin-improver LEDGER.md, .plugin-improver/baseline.json findings_remaining.

## Phase 1 — Close the memory loop (highest leverage)

Problem, proven by mining: identical bumps recur across sessions (superpowers
skill-path ENOENT ×3 sessions, rg-exit-1 retries, pytest-exit-5 reruns) and are
never recorded, despite AGENTS.md instructing capture. 0.3.1 added the write
path to sips-memory-fabric's description; that helps triggering but nothing
*enforces* capture.

1. Add a `homebase_record` tool to sips-homebase MCP (scripts/harness_homebase_mcp.py)
   that proxies memory_fabric_record with SIPS provenance, so capture works even
   when the codex-memory-fabric MCP isn't connected. Mirror the enabled_tools
   pattern in ~/.codex/config.toml [plugins."harness-self-improvement@harness-local"].
2. PostToolUse hook (hooks/hooks.json, follow existing escalation_advisor pattern):
   detect a failed→worked retry pair in-session (reuse the token-overlap pairing
   logic from ~/plugins/retro/skills/retro/scripts/mine_transcript.py) and inject
   a one-line reminder to record it. Deterministic, no model call — same design
   rule as escalation_advisor.
3. Success metric (measurable next week): re-run
   `python3 ~/plugins/retro/skills/retro/scripts/mine_transcript.py --codex --stats`
   over 5+ new sessions — recurring-bump count should be ~0; every retry chain
   should have a matching memory.jsonl record (store: ~/.codex/memory-fabric/memory.jsonl).

## Phase 2 — One-command version bump (kills a proven failure class)

Status 2026-07-14: the source-only portion is implemented by
`scripts/bump_version.py`. The helper now reduces machine-authoritative writes
to the plugin manifest, NCode marketplace manifest, and `pyproject.toml`,
regenerates `EVAL.md`, verifies transactionally, and deliberately stops before
cache install or publish. The older cache-sync proposal below is retained as
historical planning context, not current helper behavior.

The 0.3.1 bump required syncing SIX places by hand: .codex-plugin/plugin.json,
.ncode-plugin/marketplace.json, scripts/validate_v2.py EXPECTED_VERSION,
scripts/harness_homebase_mcp.py DEFAULT_PLUGIN_VERSION, EVAL.md, tests/test_homebase_mcp.py.
Two test failures during the pass came purely from missed spots.

1. Write scripts/bump_version.py <newver>: rewrites all six, then runs
   validate_v2.py + pytest as its own gate. Model: retro's build.sh version-sync
   (~/plugins/retro/build.sh), which paid off within one day of existing.
2. Add a cache-sync step to it: `git archive HEAD | tar -x -C
   ~/.codex/plugins/cache/harness-local/harness-self-improvement/<newver>/`
   (restart still required; Codex picks highest version dir — proven 2026-07-07).
3. Add a validate_v2 check: cache version dir for EXPECTED_VERSION exists and
   matches `git archive` content hash, for BOTH harness-local and any future owner.

## Phase 3 — Cache hygiene (cheap, do alongside Phase 2)

All under ~/.codex/plugins/cache/ — Codex-managed, so prune conservatively:
1. Delete the nested oddity `ralto-local/ralto-local/` (old June-9 code snapshot
   of codex-memory-fabric; verified 2026-07-07 it contains NO data store — only
   code + a rich-presence jsonl. Nothing to rejoin from it; memories live in
   ~/.codex/memory-fabric/memory.jsonl, 666 records, 2026-06-07 → present).
2. Delete the two .tgz backups inside ralto-local/codex-self-improvement/ (real
   backups belong outside cache; sources exist in ~/plugins/codex-self-improvement).
3. Old version dirs harness-local/harness-self-improvement/{0.2.0,0.2.2,0.2.3,0.3.0}
   and ralto-local/harness-self-improvement/0.3.1 (unreferenced by any manifest
   since the 2026-07-07 marketplace registration) — remove after one clean restart
   proves 0.3.1 stays selected.

## Phase 4 — Historical memory rejoin (the interrupted 2026-07-07 investigation)

Goal: fold knowledge from older memory systems into the live fabric, with provenance.
Findings so far (verified, don't re-derive):
- Old cached plugin snapshots hold NO records. Live store is the only fabric store:
  ~/.codex/memory-fabric/memory.jsonl (env override: CODEX_MEMORY_FABRIC_STORE).
- Real historical sources to evaluate:
  a. ~/.codex/sqlite/memories_1.sqlite, table stage1_outputs (7 rows: thread_id,
     raw_memory, rollout_summary) — Codex-native distilled memories.
  b. ~/.codex/memories_extensions/chronicle/resources/*.md — 10-minute ambient
     summaries (many files; high noise, mine selectively).
- Procedure: for each candidate, memory_fabric_record with provenance.detail
  naming the source (e.g. "rejoined from memories_1.sqlite stage1_outputs
  thread <id>"), kind = Knowledge or Learning per content. Dedup against the
  666 existing records by body similarity BEFORE writing. Then
  memory_fabric_doctor + store_audit as the gate.

## Phase 5 — Retro-miner integration (structural)

Status 2026-07-14: the base sweep-to-memory closure is implemented. Each weekly
sweep now writes a JSON step receipt and records a scoped Memory Fabric lesson;
failed capture fails the sweep. Automatic retro-miner ingestion of unresolved
cross-session retry chains remains future work.

weekly_sweep.py already exists in scripts/. Extend it to run the retro miner
(--codex --stats) over the week's rollouts and file unresolved failures +
retry chains into the fabric automatically. This turns Phase 1's manual metric
into a standing feedback loop — SIPS observes its own host's failures.

## Ground rules for whoever executes (Codex: read this)

- plugin-improve discipline: max 3 changes per pass, baseline before, ledger after,
  version bump via Phase 2 script once it exists, context budget +10% max.
- Never edit ~/.codex/plugins/cache/** as a source (read-only snapshots; the one
  exception is the Phase 2/3 cache-sync/prune steps, which are explicitly cache ops).
- Back up ~/.codex/config.toml before any edit; tomllib-verify after.
- Verify live pickup: `cd /tmp && codex exec --skip-git-repo-check "Reply OK" </dev/null`,
  then grep newest rollout for harness-self-improvement/<ver>/skills.
- Order: 2 → 1 → 3 → 4 → 5 is also viable if the bump script feels safer first.
