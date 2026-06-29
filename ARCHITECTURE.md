# Self-Improvement Harness v2 — Architecture & Report

A design for the most capable practical "self-improvement" plugin for an NCode
(Claude Code fork) agent that **normally runs GLM 5.2** and **occasionally runs a
stronger model (Claude/Opus class)**. This is not literal weight self-improvement
— it is a *harness* that makes the agent measurably more agentic, more skilled,
and more versatile across sessions by closing the loop: **observe → record →
recall → delegate → correct.**

Distributed as a `marketplace.json` plugin (`/plugin marketplace add ...`).

---

## 1. Verdict up front

The repo today (`harness-self-improvement@0.1.0`) is a strong **lifecycle-hook
layer**: 22 scripts wired across PreToolUse → PostToolUse → SessionStart →
UserPromptSubmit → PreCompact → PostCompact → Stop, plus a Memory Fabric
integration and a 38-case regression harness. It already does the hard,
unglamorous parts well (advisory-only hooks, silent-on-failure, snapshot before
self-edit, outcome tracking).

It has **three gaps** that block "extremely versatile":

1. **No `commands/`** — zero slash-commands, even though `autonomy_gate.py`
   already references `~/.ncode/commands/` as a protected path. The user-facing
   control surface is missing.
2. **No `agents/`** — no subagents, so there is no way to *carve a stuck subtask
   out into a fresh, bounded context* or fan work out in parallel. This is the
   single biggest versatility win and the direct lever for "more agentic."
3. **The loop is open.** `self_correct.py` writes `~/.ncode/improvements.md` but
   nothing reads it back into a session or acts on it. Learnings are produced,
   never consumed → no compounding.

v2 keeps the entire existing hook layer and adds the **command surface**, the
**agent surface**, and **loop closure**. Net new artifacts: 4 agents, 7 commands,
3 hook scripts. Everything else is reused.

---

## 2. Design principles (carried from v1, made explicit)

| Principle | Why it matters here |
|---|---|
| **Advisory by default, block only on critical risk** | GLM 5.2 runs in `bypassPermissions`; a chatty gate that blocks would destroy autonomy. Only `rm -rf /`, force-push, credential writes block. Everything else is `additionalContext`. |
| **Silent on failure** | A hook that errors must never break the turn. Every script wraps stdin/subprocess in try/except and exits 0. |
| **Deterministic helpers, not LLM calls, in hooks** | Hooks fire on every tool use — they must be <8s and free. All "intelligence" is cheap Python + Memory Fabric lookups; the *model* is only invoked through the agent/command surface. |
| **Snapshot before self-edit** | Self-modification is the dangerous part of "self-improvement." Any edit to `~/.ncode/scripts/*` is snapshotted (already in `autonomy_gate.py`) and gated by `run_tests.py`. |
| **One model, the session's** | All agents and the session itself run on **`inherit`** — whatever the user has the session set to (GLM 5.2 by default). The harness never swaps models under the hood; versatility comes from *how* the model is invoked (bounded scope, fresh context, parallel fan-out, forced recall), not *which* model. |

---

## 3. The agent model — delegate, never swap

The agent normally runs **GLM 5.2** (cheap, fast, high context, `/effort max`
unlocked via `patch_effort_message.py`) and sometimes a **Claude/Opus-class
model** when the user switches the session. The harness **does not** perform any
model routing of its own: every subagent declares `model: inherit`, so the agent
surface always runs on whatever the user has chosen for the session.

This is a deliberate choice. Swapping models behind the user's back is
unpredictable (cost, latency, capability cliffs) and couples the plugin to
specific model identifiers that drift. Instead, the harness gets its versatility
from **delegation patterns** that work on any model:

| Pattern | What it buys | Why it's model-agnostic |
|---|---|---|
| **Bounded escalation** | Carve one stuck subtask out into a fresh subagent with a tight prompt + minimal tools. Even on the same model, a clean context window + forced lesson capture unblocks things the main thread couldn't. | A fresh context is a fresh context regardless of model. |
| **Parallel fan-out** | Spawn N `repo-scout` subagents to map different modules at once. | Concurrency, not capability. |
| **Forced recall** | Every escalation ends with a `LESSON:` line recorded to Memory Fabric, scoped to the touched file — so the main thread recalls it next time without re-delegating. | Compounding memory works on any model. |

```
                      ┌─────────────────────────────────────────┐
   user task ───────► │  session model (inherit) — GLM 5.2       │
                      │  fast, cheap, /effort max, full recall   │
                      └───────────────┬─────────────────────────┘
                                      │ escalation_advisor detects
                                      │ "stuck": 2+ fails same scope,
                                      │ or self_correct exhausted
                                      ▼
                      ┌─────────────────────────────────────────┐
   /escalate or  ───► │  escalate agent (model: inherit)          │
   auto-signal        │  SAME model, fresh context, bounded task  │
                      │  minimal tools, forced LESSON: line      │
                      └───────────────┬─────────────────────────┘
                                      │ result + lesson
                                      ▼
                            Memory Fabric (recorded so the
                            session recalls it next time)
```

This is the practical, honest form of "self-improvement": the agent gets
**permanently better at the class of task** because each solved subtask is
captured as a recallable lesson, scoped to the file/topic, surfaced by the
existing preflight hook on the next encounter — no weight changes, no model
swaps.

---

## 4. Full architecture (component map)

```
harness-self-improvement/  (marketplace plugin root)
├── .ncode-plugin/marketplace.json      # marketplace manifest (the distributable)
├── .codex-plugin/plugin.json           # plugin manifest → hooks + agents + commands
├── hooks/hooks.json                    # lifecycle wiring (existing + 3 new)
├── agents/                        [NEW] # subagent surface (all model: inherit)
│   ├── escalate.md                      #   bounded subtask in a fresh context
│   ├── memory-curator.md                #   dedupe/promote/expire Memory Fabric
│   ├── test-author.md                   #   write the missing regression case
│   └── repo-scout.md                    #   cheap parallel codebase recon
├── commands/                      [NEW] # slash-command surface
│   ├── improve.md                       #   run self-correct sweep + act on top item
│   ├── recall.md                        #   query Memory Fabric for the current scope
│   ├── escalate.md                      #   delegate the next step to the escalate agent
│   ├── checkpoint.md                    #   snapshot harness + write continuity packet
│   ├── verify.md                        #   run_tests.py + script_smoke on touched files
│   ├── patterns.md                      #   show agent_patterns full report
│   └── teach.md                         #   record a hand-written lesson into Memory Fabric
└── scripts/                             # 22 existing + 3 new lifecycle scripts
    ├── (existing 22 …)
    ├── escalation_advisor.py      [NEW] # PostToolUse: detect "stuck", suggest /escalate
    ├── improvement_injector.py    [NEW] # SessionStart: read improvements.md → context (loop closure)
    └── recall_ranker.py           [NEW] # UserPromptSubmit: scoped recall depth
```

Note there is **no `lib/model_router.py`** — v1's tier-detection library is
dropped entirely. Nothing in the harness branches on which model is active; the
same behavior runs on GLM 5.2 and on Claude, because all agents inherit the
session model.

### Lifecycle wiring (v2 hooks.json, additions in **bold**)

| Event | Matcher | Scripts (in order) |
|---|---|---|
| **PreToolUse** | `Edit\|Write\|MultiEdit` | autonomy_gate → memory_fabric_preflight |
| | `Bash\|apply_patch` | autonomy_gate |
| **PostToolUse** | `Edit\|Write\|MultiEdit` | script_smoke → **escalation_advisor** |
| | `Bash\|apply_patch\|Edit\|Write\|mcp__.*` | csi_presence_mirror |
| **SessionStart** | `startup\|resume\|clear\|compact` | validate_harness → memory_fabric_doctor → proactive_drift → agent_patterns --brief → **improvement_injector** |
| **UserPromptSubmit** | — | **recall_ranker** (replaces raw prompt_search) → probe_hook |
| **PreCompact** | `manual\|auto` | memory_fabric_compact_brief → compact_continuity |
| **PostCompact** | `manual\|auto` | memory_fabric_session_record → compact_continuity |
| **Stop** | — | session_close → task_outcome_tracker --record |

Three new scripts, one swap (`recall_ranker` wraps the existing
`memory_fabric_prompt_search` with scoped recall depth). The rest of the proven
v1 wiring is untouched.

---

## 5. The agent surface (new) — all `model: inherit`

NCode/Claude-Code subagents are markdown files with frontmatter that *can* pin a
model. v2 **pins none of them** — every agent declares `model: inherit`, so the
subagent runs on exactly the model the user has chosen for the session. Four
agents, identical in spirit whether the session is GLM 5.2 or Claude:

| Agent | Model | Purpose | When invoked |
|---|---|---|---|
| **escalate** | `inherit` | Take one bounded, well-specified subtask the main thread is stuck on, in a *fresh context window* with minimal tools; return a plan + minimal diff + a one-line lesson. | `/escalate`, or auto-suggested by `escalation_advisor.py` |
| **repo-scout** | `inherit` | Cheap, parallel codebase recon (find files, map call sites, summarize a module). Fan many of these. | Implicitly during planning; `/recall` may spawn |
| **memory-curator** | `inherit` | Dedupe near-identical Memory Fabric records, promote repeated work-tier → learning-tier, expire stale low-confidence ones. Keeps recall signal high. | `/improve`, weekly |
| **test-author** | `inherit` | Given an untested script (from `proactive_drift`/`self_correct`), write the missing `run_tests.py` regression case. | `/verify` when coverage gap found |

Example `agents/escalate.md` frontmatter:

```markdown
---
name: escalate
description: Solve one bounded subtask the main thread is stuck on, in a fresh context. Returns a plan, a minimal diff, and a one-line lesson to record.
model: inherit                  # always the session's model — never swapped
tools: Read, Grep, Glob, Edit, Bash
---
You are the escalation specialist. The main thread has handed you ONE bounded
subtask it could not resolve. You run on the SAME model as the session — your
advantage is a clean context window, a tight toolset, and a forced structured
output. Constraints:
- Do the minimum to unblock; do not re-architect.
- End with: (1) a unified diff, (2) `LESSON: <one line>` that will be recorded
  to Memory Fabric scoped to the touched file so the main thread recalls it
  next time and doesn't need to re-escalate.
```

> Why `inherit` and not a pinned stronger model? Three reasons: (1) it keeps the
> plugin decoupled from model identifiers that drift over time; (2) cost stays
> entirely under the user's control — if they want a stronger escalation model,
> they switch the session, and every agent follows; (3) a fresh, bounded context
> with minimal tools unblocks a stuck GLM 5.2 thread *on GLM 5.2 itself* far more
> often than people assume — the bottleneck is usually context pollution, not
> raw capability.

---

## 6. The command surface (new) — the user/agent control panel

Slash-commands are markdown prompt-templates the user (or the agent) can invoke.
Seven, mapped to the lifecycle the harness already manages:

| Command | What it does | Backed by |
|---|---|---|
| `/improve` | Run `self_correct.py`, read the top recommended action, and **act on it** (spawn `test-author`/`memory-curator` as needed). Closes the loop on demand. | self_correct.py + agents |
| `/recall [query]` | Scoped Memory Fabric search for the current scope; prints ranked prior lessons. | recall_ranker.py |
| `/escalate [task]` | Delegate the next step to the `escalate` agent (bounded, fresh-context delegation — same model). | escalate agent |
| `/checkpoint` | `snapshot_harness.py` + write a continuity packet — safe point before risky work. | snapshot_harness.py + compact_continuity.py |
| `/verify` | `run_tests.py` + `script_smoke` on touched files; if a coverage gap is found, offer `test-author`. | run_tests.py |
| `/patterns` | Full `agent_patterns.py` report — success rate, approach→outcome correlation. | agent_patterns.py |
| `/teach <lesson>` | Hand-record a lesson into Memory Fabric (learning tier, high confidence) so it's recalled later. | memory_fabric CLI |

Example `commands/improve.md`:

```markdown
---
description: Run a self-correction sweep and act on the top recommendation.
---
Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_correct.py --json`. Read the
result. Then:
1. If untested scripts exist → dispatch the `test-author` agent for the first one.
2. If duplicate/stale memory is implied → dispatch `memory-curator`.
3. Summarize what you changed and re-run `/verify`.
Do not edit `~/.ncode/scripts/*` without snapshotting first (the autonomy gate
will remind you).
```

`autonomy_gate.py` already lists `~/.ncode/commands/*.md` as a **high-risk
self-modification path** — so the command surface is *already* protected by the
existing gate. v1 anticipated this surface; v2 ships it.

---

## 7. Loop closure (the actual "self-improvement")

The compounding mechanism, end to end:

```
1. OBSERVE   Stop hook (task_outcome_tracker) records tool counts, edits,
             success/failure per task → Memory Fabric (learning tier).
2. RECORD    session_close records shipped artifacts (work tier). escalate
             agent records LESSON lines scoped to the touched file.
3. CORRECT   self_correct.py (via /improve or weekly) finds failure topics,
             untested scripts, stale code → improvements.md + dispatches
             test-author / memory-curator to FIX them, not just report.
4. INJECT    improvement_injector.py reads the latest improvements.md entry at
             SessionStart → additionalContext, so the session STARTS knowing the
             open self-improvement items. (This is the missing v1 read-back.)
5. RECALL    recall_ranker (UserPromptSubmit) + memory_fabric_preflight
             (PreToolUse) surface the right prior lesson at the right moment.
6. DELEGATE  escalation_advisor detects "stuck" from live signals and suggests
             /escalate → a fresh-context subagent (same model) solves it →
             LESSON recorded → next time the main thread recalls it and solves
             it itself, no delegation needed.
```

Steps 3-4 and 6 are net-new and are what turn v1's *open* loop (produce learnings,
ignore them) into a *closed* one (produce → consume → act → recall).

---

## 8. `marketplace.json` (the deliverable form)

The plugin is distributed via the marketplace manifest the user asked for. v2
declares the new agent and command surfaces alongside the existing hooks:

```jsonc
// .ncode-plugin/marketplace.json
{
  "name": "harness-local",
  "description": "Local marketplace for the self-improving NCode agent harness",
  "owner": { "name": "RasputinKaiser" },
  "plugins": [
    {
      "name": "harness-self-improvement",
      "description": "Self-improving agent harness: Memory Fabric recall, autonomy gate, continuity packets, outcome tracking, drift detection, self-correction loop, and a delegation agent surface. All agents inherit the session model (GLM 5.2 by default) — versatility comes from bounded fresh-context delegation and forced lesson capture, not model swaps.",
      "version": "0.2.0",
      "source": "./",
      "author": { "name": "RasputinKaiser" },
      "category": "engineering",
      "keywords": [
        "self-improvement", "memory-fabric", "delegation",
        "escalation", "inherit", "autonomy-gate", "continuity", "hooks"
      ]
    }
  ]
}
```

And the plugin manifest points NCode at all three surfaces:

```jsonc
// .codex-plugin/plugin.json
{
  "name": "harness-self-improvement",
  "version": "0.2.0",
  "description": "Self-improving agent harness with delegation agent surface.",
  "author": { "name": "RasputinKaiser" },
  "license": "MIT",
  "hooks": "./hooks/hooks.json",
  "agents": "./agents/",
  "commands": "./commands/",
  "keywords": ["self-improvement", "memory-fabric", "delegation", "harness"]
}
```

Install path is unchanged for the user:

```bash
/plugin marketplace add RasputinKaiser/Self-Improvement-Plugin
# then install Self-Improvement-Plugin@harness-local
```

---

## 9. Why this is the optimal shape

- **Model-honest**: every agent runs `inherit` — no hidden model swaps, no
  coupling to model identifiers that drift. If the user wants a stronger
  escalation model, they switch the session and every agent follows. Cost and
  capability stay entirely in the user's hands.
- **Compounding**: every delegated solution becomes a scoped, recallable lesson —
  so the session permanently improves at that task class. That is the only
  honest "self-improvement" available without touching weights.
- **Versatile**: three surfaces (hooks = automatic, commands = user-driven,
  agents = delegated/parallel) cover the full control spectrum. `repo-scout`
  fan-out makes recon cheap; `escalate`'s fresh context unblocks stuck threads
  without a model swap.
- **Safe**: the existing autonomy gate already protects the *new* surfaces
  (`commands/`, `agents/` sit under the self-modification patterns), snapshots
  precede self-edits, and `run_tests.py` gates regressions.
- **Low-risk to ship**: the entire proven v1 hook layer is reused unchanged. v2
  is purely additive — 4 agents, 7 commands, 3 scripts, two manifest bumps.

## 10. Build order (if implementing)

1. `commands/` (pure markdown, zero risk, immediate user value).
2. `agents/escalate.md` + `escalation_advisor.py` (the headline delegation feature).
3. `improvement_injector.py` (closes the loop — highest leverage script).
4. Remaining agents (`memory-curator`, `test-author`, `repo-scout`) + `recall_ranker.py`.
5. Add an `escalation_advisor` suite to `run_tests.py`; bump to 0.2.0.
