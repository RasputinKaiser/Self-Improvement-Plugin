# SIPS — Architecture

SIPS is a **self-improvement harness** for Claude Code and ChatGPT / Codex. It is
not literal weight self-improvement — it is a harness that makes an agent
measurably more agentic and more consistent across sessions by closing the loop:

> **observe → record → recall → delegate → correct.**

The plugin never changes the model. It improves the *work loop* around whatever
model the host session already runs, through four surfaces — **lifecycle hooks**,
**slash commands**, **delegation agents**, and a portable **Homebase MCP** — plus a
deterministic **graph runtime** for bounded task execution (v0.4.0).

Distributed as a marketplace plugin: `.claude-plugin/marketplace.json` for Claude
Code and `.agents/plugins/marketplace.json` for Codex, from the same repo.

---

## 1. Design principles

| Principle | Why it matters |
|---|---|
| **Advisory by default, block only on critical risk** | A chatty gate that blocks would destroy autonomy. Only genuinely dangerous actions (destructive `rm`, force-push, credential writes) block; everything else is added context. |
| **Silent on failure** | A hook that errors must never break the turn. Every script wraps its I/O in try/except and exits 0. The event tap is silent unless `SIPS_DEBUG=1`. |
| **Deterministic helpers, not model calls, in hooks** | Hooks fire on every tool use, so they must be fast (<8s) and free. All in-hook "intelligence" is cheap Python plus Memory Fabric lookups; the model is only invoked through the command and agent surfaces. |
| **Snapshot before self-edit** | Self-modification is the dangerous part of self-improvement. Edits to the harness's own scripts, agents, and commands are gated by the autonomy check and snapshotted for rollback. |
| **One model — the session's** | Every agent declares `model: inherit`. The harness never swaps models under the hood; versatility comes from *how* the model is invoked, not *which* model it is. |

---

## 2. Model policy — delegate, never swap

SIPS performs no model routing of its own. Every subagent declares
`model: inherit`, so the agent surface always runs on whatever model the host
session uses — Claude in Claude Code, or the configured model in Codex.

This is deliberate. Swapping models behind the user's back is unpredictable
(cost, latency, capability cliffs) and couples the plugin to model identifiers
that drift. Instead, versatility comes from **delegation patterns that work on any
model**:

| Pattern | What it buys | Why it's model-agnostic |
|---|---|---|
| **Bounded escalation** | Carve one stuck subtask out into a fresh subagent with a tight prompt and minimal tools. Even on the same model, a clean context window plus forced lesson capture unblocks what the main thread couldn't. | A fresh context is a fresh context regardless of model. |
| **Parallel fan-out** | Spawn N `repo-scout` (or `fan-out`) subagents to map different modules or solve independent slices at once. | Concurrency, not capability. |
| **Forced recall** | Every escalation ends with a `LESSON:` line recorded to Memory Fabric, scoped to the touched file — so the main thread recalls it next time without re-delegating. | Compounding memory works on any model. |

```
                      ┌─────────────────────────────────────────┐
   user task ───────► │  session model (inherit)                 │
                      │  full recall, main working context       │
                      └───────────────┬─────────────────────────┘
                                      │ escalation_advisor detects
                                      │ "stuck": 2+ fails same scope,
                                      │ or self_correct exhausted
                                      ▼
                      ┌─────────────────────────────────────────┐
   /escalate or  ───► │  escalate agent (model: inherit)         │
   auto-signal        │  SAME model, fresh context, bounded task │
                      │  minimal tools, forced LESSON: line      │
                      └───────────────┬─────────────────────────┘
                                      │ result + lesson
                                      ▼
                            Memory Fabric (recorded so the
                            session recalls it next time)
```

This is the honest form of "self-improvement": the agent gets permanently better
at a *class of task* because each solved subtask is captured as a recallable
lesson, scoped to the file/topic, and surfaced by the preflight hook on the next
encounter — no weight changes, no model swaps.

---

## 3. Component map

```
Self-Improvement-Plugin/            (marketplace plugin root)
├── .claude-plugin/marketplace.json  # Claude Code marketplace (sips-local)
├── .agents/plugins/marketplace.json # Codex marketplace (harness-local)
├── .codex-plugin/plugin.json        # plugin manifest → skills + MCP + metadata
├── hooks/hooks.json                 # lifecycle wiring
├── .mcp.json                        # Homebase MCP server declaration (sips-homebase)
├── commands/                        # 11 slash commands
├── agents/                          # 5 delegation subagents (all model: inherit)
├── skills/                          # 10 sips-* skill rows over the Homebase surfaces
├── scripts/                         # hook, utility, memory, and eval scripts
│   ├── harness_homebase_mcp.py      #   Homebase MCP control plane
│   ├── memory_fabric*.py            #   vendored SIPS-owned Memory Fabric
│   ├── sips_runtime.py              #   0.4.0 graph-runtime CLI
│   └── sips_runtime/                #   graph-runtime package (DAG, scheduler, …)
└── Graph-Theory/                    # 0.4.0 graph-runtime design docs + receipts
```

There is **no model-router library**. Nothing in the harness branches on which
model is active; the same behavior runs on Claude Code and Codex because every
agent inherits the session model.

### Lifecycle wiring (`hooks/hooks.json`)

| Event | Matcher | Scripts (in order) |
|---|---|---|
| **PreToolUse** | `Edit\|Write\|MultiEdit` | autonomy_gate → memory_fabric_preflight |
| | `Bash\|apply_patch` | autonomy_gate |
| **PostToolUse** | `Edit\|Write\|MultiEdit` | script_smoke → escalation_advisor |
| | `Bash\|apply_patch\|Edit\|Write\|mcp__.*` | sips_presence_mirror |
| **SessionStart** | `startup\|resume\|clear\|compact` | validate_harness → memory_fabric_doctor → proactive_drift → agent_patterns --brief → improvement_injector |
| **UserPromptSubmit** | all prompts | recall_ranker → probe_hook |
| **PreCompact** | `manual\|auto` | memory_fabric_compact_brief → compact_continuity |
| **PostCompact** | `manual\|auto` | memory_fabric_session_record → compact_continuity |
| **Stop** | all stops | session_close → task_outcome_tracker --record |

Hook commands are portable: they run `python3` against `${PLUGIN_ROOT}`, falling
back to `${CLAUDE_PLUGIN_ROOT}`, with the plugin-root path quoted so it survives
spaces in the install path.

---

## 4. The three control surfaces

SIPS covers the full control spectrum with three surfaces — automatic, user-driven,
and delegated — over a shared MCP control plane.

### Hooks (automatic)

The lifecycle table above. Hooks validate the harness, surface prior lessons
before risky edits, smoke-check changed scripts, preserve continuity across
compaction, and record outcomes at stop — all advisory, all silent on failure.

### Commands (user- and agent-driven)

Eleven slash commands map onto the lifecycle the harness manages: `/improve`,
`/recall`, `/escalate`, `/checkpoint`, `/verify`, `/patterns`, `/teach`, `/goal`,
`/brainstorm`, `/fan-out`, and `/selfloop`. See the README for the full command
table and when to use each.

### Agents (delegated, parallel)

Five subagents, all `model: inherit`. Each gets a bounded job and returns a
focused result instead of taking over the whole task:

| Agent | Purpose |
|---|---|
| **escalate** | Solve one bounded blocker in a fresh context; returns a diff plus a one-line lesson. |
| **repo-scout** | Cheap, parallel, read-only repo reconnaissance. Fan many of these. |
| **memory-curator** | Dedupe, promote, and expire Memory Fabric records without deleting data. |
| **test-author** | Write the missing `run_tests.py` regression for an untested or risky script. |
| **fan-out** | Solve one independent slice of a decomposed parent task, ready for merge. |

### Homebase MCP + skills (shared control plane)

`.mcp.json` exposes `scripts/harness_homebase_mcp.py` as `sips-homebase` — the
portable `homebase_*` tool set shared by Claude Code and Codex. The ten `sips-*`
skills present those surfaces as first-class rows (control plane, proof scanner,
delegation router, Memory Fabric, repo map, context distiller, execution repro,
perception plan, tool factory, selfloop). Skills and host commands are adapters;
the MCP keeps the underlying model portable across hosts.

---

## 5. Loop closure — the actual "self-improvement"

The compounding mechanism, end to end:

```
1. OBSERVE   Stop hook (task_outcome_tracker) records tool counts, edits, and
             success/failure per task → Memory Fabric (learning tier).
2. RECORD    session_close records shipped artifacts (work tier); the escalate
             agent records LESSON lines scoped to the touched file.
3. CORRECT   self_correct.py (via /improve or the weekly sweep) finds failure
             topics, untested scripts, and stale code → improvement notes, and
             dispatches test-author / memory-curator to FIX them, not just report.
4. INJECT    improvement_injector.py reads the latest improvement notes at
             SessionStart → context, so the session STARTS knowing the open items.
5. RECALL    recall_ranker (UserPromptSubmit) + memory_fabric_preflight
             (PreToolUse) surface the right prior lesson at the right moment.
6. DELEGATE  escalation_advisor detects "stuck" from live signals and suggests
             /escalate → a fresh-context subagent (same model) solves it →
             LESSON recorded → next time the main thread recalls it and solves it
             itself, no delegation needed.
```

Steps 3–4 and 6 are what make the loop *closed*: learnings are produced,
consumed, acted on, and recalled — instead of written and forgotten.

---

## 6. The graph runtime (v0.4.0)

v0.4.0 adds a deterministic execution layer under `scripts/sips_runtime/`, with
matching CLI (`sips_runtime.py`) and Homebase MCP read/write surfaces
(`sips_runtime_read` / `sips_runtime_write`). Full design in
[`Graph-Theory/`](Graph-Theory/README.md).

- A strict task **DAG** for readiness, fenced leases, budgets, execution, and fan-in.
- A separate **bounded cyclic Memory Fabric frontier** that supplies context but
  cannot unlock tasks (memory informs; it never gates execution).
- Append-only **hash-chained run events**, rebuildable snapshots, immutable slice
  and graph **receipts**, and **recovery-by-linked-fork**.
- Structured **result/evidence gates**, candidate-first lesson promotion, and
  failed-writer receipts.
- `legacy`, `shadow`, `dual`, and `runtime` **compatibility projections**, with
  `legacy` still the default.

The runtime is source-verified. Controller-authoritative `dual`/`runtime`
execution, plugin-cache parity, and fresh-host MCP exposure remain explicit
cutover gates — see [`Graph-Theory/verification.md`](Graph-Theory/verification.md).

---

## 7. Distribution

The same repo installs into either host from its own marketplace manifest.

```jsonc
// .codex-plugin/plugin.json  (excerpt)
{
  "name": "harness-self-improvement",
  "version": "0.4.0",
  "description": "SIPS graph runtime and home-base for bounded task execution, memory, verification, delegation, and lifecycle automation.",
  "license": "MIT",
  "skills": "./skills/",
  "mcpServers": "./.mcp.json"
}
```

```bash
# Claude Code
/plugin marketplace add RasputinKaiser/Self-Improvement-Plugin
# then install harness-self-improvement

# Codex: add the repo as a local marketplace, then install
#   harness-self-improvement@harness-local
```

---

## 8. Safety

- **Advisory gate.** `autonomy_gate.py` warns on risky autonomous actions and
  blocks only genuinely dangerous ones; the harness's own scripts, agents, and
  commands are treated as high-risk self-modification paths.
- **Snapshot before self-edit.** `snapshot_harness.py` captures a rollback point;
  `restore_harness.py` recovers a known-good snapshot.
- **Regression-gated.** `run_tests.py` (97 cases) and the pytest suite (360 tests)
  gate changes; CI runs both on macOS and Linux (Python 3.10 / 3.12).
- **Local-first.** The plugin runs local scripts and reads local harness state.
  Review scripts before using them elsewhere; see `SECURITY.md`.

## 9. Why this shape

- **Model-honest** — every agent runs `inherit`; no hidden swaps, no coupling to
  model identifiers that drift. Switch the session model and every agent follows.
- **Compounding** — each delegated solution becomes a scoped, recallable lesson,
  so the session permanently improves at that task class.
- **Versatile** — hooks (automatic), commands (user-driven), and agents
  (delegated/parallel) cover the full control spectrum; the graph runtime adds
  deterministic, receipted task execution when a plain session isn't enough.
- **Safe and low-risk** — the proven hook layer is advisory and silent on failure,
  self-edits are snapshotted and regression-gated, and the whole surface is
  verified in CI.
