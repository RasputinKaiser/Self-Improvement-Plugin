# harness-self-improvement

A self-improving agent harness plugin for NCode (Claude Code fork). Provides
hooks across the full agent lifecycle so each task starts informed by prior
work and each session closes with recorded learnings — and a delegation agent
surface so a stuck subtask can be carved into a fresh, bounded context.

## What's included

**v0.2.0** adds a live-service command surface (7 slash commands), a delegation
agent surface (4 subagents, all `model: inherit`), and loop closure. All agents
inherit the session model (GLM 5.2 by default) — versatility comes from bounded
fresh-context delegation and forced lesson capture, not model swaps.

### Lifecycle hooks (22 scripts + 3 new in v0.2.0)

- **PreToolUse**: autonomy gate (blocks critical paths), Memory Fabric preflight (surfaces prior learnings)
- **PostToolUse**: script syntax smoke test, **escalation advisor** (detects "stuck", suggests /escalate)
- **SessionStart**: drift check, Memory Fabric doctor + recent work, proactive drift, agent patterns brief, **improvement injector** (loop closure)
- **UserPromptSubmit**: **recall ranker** (scoped failure-then-success recall ranking)
- **PreCompact**: thread-brief injection, continuity packet write
- **PostCompact**: session record, continuity restore
- **Stop**: session close, task outcome metrics

### Slash commands (new in v0.2.0)

`/improve` `/recall` `/escalate` `/checkpoint` `/verify` `/patterns` `/teach`

### Delegation agents (new in v0.2.0, all `model: inherit`)

`escalate` `repo-scout` `memory-curator` `test-author`

### On-demand utilities

validator, GC, tool factory, repo forensics, snapshot/restore, self-correct,
run_tests (38 v1 cases + 9 v2 cases = 47 regression cases).

## Installation

```bash
/plugin marketplace add RasputinKaiser/harness-self-improvement
```

Then install `harness-self-improvement@harness-local` from the marketplace UI.

## Requirements

- Python 3.8+
- Codex Memory Fabric plugin installed (for Memory Fabric features)
- CSI Host Surface Audit plugin (optional, for `harness_gc.py --deep`)

## Verifying

```bash
python3 scripts/validate_v2.py   # manifest coherence check, writes EVAL.md
python3 scripts/run_tests.py     # 47-case regression harness
```

## License

MIT — see LICENSE.
