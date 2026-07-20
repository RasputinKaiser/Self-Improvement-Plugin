# SIPS — Self-Improvement Plugin System

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: dev](https://img.shields.io/badge/status-dev-orange)
![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-8A5CF6)
![Codex plugin](https://img.shields.io/badge/ChatGPT_Codex-plugin-10A37F)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/W7W7C9TC7)

**A self-improvement harness for Claude Code and ChatGPT / Codex.** SIPS wraps a coding-agent session with memory-aware startup, safer tool use, verification hooks, bounded fresh-context delegation, and session closeout — so long-running sessions remember prior work, avoid repeated mistakes, recover from drift, and capture lessons before the context window disappears.

It does not try to make an agent smarter by swapping models. It improves the *work loop* around whatever model you already run.

> Experimental, but CI-backed. The core is a deterministic graph runtime, SIPS-owned Memory Fabric recall, lifecycle hooks, slash-command and MCP surfaces, and focused regression suites — **97 harness cases + 360 pytest tests, green on macOS and Linux.**

*Companion app: a very experimental, free, native macOS control surface — [Swift Harness](https://github.com/RasputinKaiser/Swift-Harness).*

Each session can answer:

- What did we learn last time?
- Is this edit risky?
- Did the changed script still pass a smoke check?
- Is this task stuck enough to split out?
- What should future sessions remember?
- Which agent patterns have worked or failed before?

**Suggested GitHub topics:** `agent-harness`, `ai-agents`, `claude-code`, `codex`, `memory-fabric`, `self-improvement`, `automation`, `evals`, `python`, `developer-tools`

## Supported hosts

SIPS installs as a plugin in either harness, from the same repo:

- **Claude Code** — reads `.claude-plugin/marketplace.json` (marketplace `sips-local`).
- **ChatGPT / Codex** — reads `.agents/plugins/marketplace.json` (marketplace `harness-local`).

Delegation agents declare `model: inherit`, so they run on whatever model the host session already uses. The plugin never depends on a specific model or on model swaps; the gain comes from context control, scoped recall, verification, and recorded outcomes.

## Install

### Claude Code

```bash
/plugin marketplace add RasputinKaiser/Self-Improvement-Plugin
```

Then install **`harness-self-improvement`** from the marketplace UI.

### ChatGPT / Codex

Add the repo as a local marketplace, then install:

```text
harness-self-improvement@harness-local
```

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | Runs the hook and utility scripts. CI covers 3.10 and 3.12 on macOS and Linux. |
| Claude Code or Codex | Host harness that loads the plugin's hooks, commands, agents, and MCP server. |
| POSIX host | macOS / Linux. Windows is untested. |

Runtime scripts resolve `$SIPS_HOME` first for harness state, falling back to legacy locations when it is unset. The SIPS-owned Memory Fabric subsystem is vendored in-repo — no external memory plugin is required.

## What it adds

| Surface | Purpose |
|---|---|
| Lifecycle hooks | Run checks and memory actions during startup, prompt submit, tool use, compaction, and session close. |
| Slash commands | Direct user control over recall, improvement, verification, goals, escalation, and fan-out. |
| Delegation agents | Send bounded subtasks into fresh context while keeping the parent session clean. |
| SIPS Homebase MCP | Portable `homebase_*` tools shared across Claude Code and Codex. |
| Codex skills | Expose the Homebase surfaces as organized, first-class plugin rows. |
| Utility scripts | Validate, test, snapshot, restore, inspect, and improve the harness over time. |

## Core workflow

A typical session looks like this:

1. Session starts.
2. The harness validates itself.
3. Memory Fabric health is checked.
4. Prior patterns and lessons are surfaced.
5. The user submits a task.
6. Relevant prior lessons are ranked and injected.
7. Before risky edits, preflight checks run.
8. After tool use, smoke checks and escalation checks run.
9. Before compaction, a continuity packet is written.
10. After compaction, session learnings are recorded.
11. At stop, the task outcome is captured for future pattern analysis.

The intent is to make each session leave behind useful state instead of vanishing into a transcript.

## Slash commands

| Command | Purpose | Use when |
|---|---|---|
| `/improve` | Runs a self-correction sweep and acts on the top recommendation. | You want the harness to find and fix its most important weakness. |
| `/recall` | Searches Memory Fabric for ranked prior lessons in the current scope. | You are returning to a repo, task, bug, or design pattern from earlier work. |
| `/escalate` | Sends one bounded stuck subtask to a fresh-context escalation agent. | The current session is looping, confused, or overloaded. |
| `/checkpoint` | Snapshots the harness and writes a continuity packet before risky work. | You are about to edit core scripts, refactor logic, or try an uncertain fix. |
| `/verify` | Runs the regression harness plus smoke checks for touched scripts. | You changed hook scripts, command scripts, eval logic, or utilities. |
| `/patterns` | Shows the agent-patterns dashboard with success and failure correlations. | You want to see what kinds of approaches have worked before. |
| `/teach` | Manually records a high-signal lesson into Memory Fabric. | You found something future sessions should reuse. |
| `/goal` | Sets, inspects, pauses, resumes, completes, or clears the persistent goal loop. | You want the harness to keep a persistent goal across steps. |
| `/brainstorm` | Surveys capability gaps and asks the escalation agent for a build plan. | You want ideas for what the harness should improve next. |
| `/fan-out` | Decomposes a parent task into parallel slice agents and merges their outputs. | A task can be split into independent research, coding, or inspection slices. |

## Delegation agents

Delegation agents keep the parent session from getting overloaded. Each agent gets a bounded job and returns a focused result instead of taking over the whole task. All agents use `model: inherit`.

| Agent | Role | Expected output |
|---|---|---|
| `escalate` | Solves one bounded blocker in a fresh context. | `DIFF` plus `LESSON`. |
| `repo-scout` | Performs read-only repo reconnaissance. | File map, key findings, and one gotcha. |
| `memory-curator` | Dedupes, promotes, and archives Memory Fabric records without deleting data. | Cleaned or ranked memory records. |
| `test-author` | Adds one focused `run_tests.py` regression for an untested or risky script. | A regression case and notes on coverage. |
| `fan-out` | Solves one independent slice from a decomposed parent task. | Slice result ready for parent merge. |

## Lifecycle hooks

| Event | Matchers | Scripts |
|---|---|---|
| `PreToolUse` | `Edit`, `Write`, `MultiEdit`, `Bash`, `apply_patch` | `autonomy_gate.py`, `memory_fabric_preflight.py` |
| `PostToolUse` | `Edit`, `Write`, `MultiEdit`, `Bash`, `apply_patch`, `mcp__.*` | `script_smoke.py`, `escalation_advisor.py`, `sips_presence_mirror.py` |
| `SessionStart` | `startup`, `resume`, `clear`, `compact` | `validate_harness.py`, `memory_fabric_doctor.py`, `proactive_drift.py`, `agent_patterns.py --brief`, `improvement_injector.py` |
| `UserPromptSubmit` | all prompts | `recall_ranker.py`, `probe_hook.py` |
| `PreCompact` | `manual`, `auto` | `memory_fabric_compact_brief.py`, `compact_continuity.py` |
| `PostCompact` | `manual`, `auto` | `memory_fabric_session_record.py`, `compact_continuity.py` |
| `Stop` | all stops | `session_close.py`, `task_outcome_tracker.py --record` |

Hook commands are portable: they run `python3` against `${PLUGIN_ROOT}` and fall back to `${CLAUDE_PLUGIN_ROOT}`, with the plugin-root path quoted so it survives spaces in the install path. The event tap is silent by default; set `SIPS_DEBUG=1` to write hook failure details to `logs/hook_errors.jsonl`.

**By phase:**

- **Startup** — `validate_harness.py` (harness health), `memory_fabric_doctor.py` (memory health + recent work), `proactive_drift.py` (drift and untested scripts), `agent_patterns.py --brief` (success/failure brief), `improvement_injector.py` (loop-closure guidance).
- **Prompt submit** — `recall_ranker.py` (ranks prior lessons for the prompt and scope), `probe_hook.py` (markers for hook tests).
- **Before tool use** — `autonomy_gate.py` (blocks or warns on risky autonomous actions), `memory_fabric_preflight.py` (surfaces lessons before edits).
- **After tool use** — `script_smoke.py` (syntax/smoke checks changed scripts), `escalation_advisor.py` (flags when a bounded escalation may help), `sips_presence_mirror.py` (mirrors SIPS presence files into the local host surface).
- **Compaction** — `memory_fabric_compact_brief.py` and `compact_continuity.py` preserve continuity before compaction; `memory_fabric_session_record.py` records learnings after.
- **Stop** — `session_close.py` (session closeout), `task_outcome_tracker.py --record` (outcome capture for pattern analysis).

## SIPS Homebase MCP

`.mcp.json` exposes `scripts/harness_homebase_mcp.py` as `sips-homebase` — a portable control plane shared by Claude Code and Codex.

| MCP tool | Purpose |
|---|---|
| `homebase_status` | Inspect manifest, commands, agents, hooks, MCP tools, and git state. |
| `homebase_verify` | Run manifest validation and optional regression suites. |
| `homebase_route` | Choose the right command, agent, script, or MCP path for a task. |
| `homebase_repo_map` | Map repo files, git state, write scope, and likely test commands. |
| `homebase_context_scan` | Find oversized context-drain files with bounded-read advice. |
| `homebase_recall` | Search the SIPS Memory Fabric subsystem for scoped prior lessons. |
| `homebase_goal` | Inspect persistent harness goal state without mutating it. |
| `homebase_routes` | List SIPS routes and fallback commands. |
| `homebase_mcp_freshness` | Check source/cache/config MCP freshness. |
| `homebase_host_audit` | Audit host wiring for SIPS drift. |
| `homebase_distill_context` | Distill large files into bounded excerpts. |
| `homebase_execution_repro` | Build a focused repro and verification plan. |
| `homebase_perception_plan` | Plan browser/app visual QA loops. |
| `homebase_tool_factory` | Decide whether a local tool is warranted. |
| `sips_runtime_read` | Read runtime status, plan, events, receipt, or bounded memory frontier. |
| `sips_runtime_write` | Create, submit, lease, advance, cancel, or promote with idempotency and revision guards. |

## Codex skill surface

SIPS exposes compact skill rows for the major Homebase surfaces, so the plugin reads like a real toolbelt rather than a bare list of MCP servers and hooks:

| Skill | Purpose |
|---|---|
| `sips-control-plane` | Inspect status, route inventory, host wiring, and MCP freshness. |
| `sips-proof-scanner` | Verify manifest, repo, and plugin proof surfaces before completion claims. |
| `sips-delegation-router` | Route tasks through SIPS commands, agents, scripts, or MCP tools. |
| `sips-memory-fabric` | Search SIPS-owned Memory Fabric recall and memory health. |
| `sips-repo-map` | Map repo structure, write scope, likely tests, and blast radius. |
| `sips-context-distiller` | Compress large files into bounded, source-linked context. |
| `sips-execution-repro` | Turn failures, logs, and symptoms into repro plans. |
| `sips-perception-plan` | Plan screenshot, browser, app, or UI runtime proof. |
| `sips-tool-factory` | Decide whether to reuse, improve, or scaffold deterministic helpers. |

## Current release — v0.4.0

This additive release introduces the [SIPS Graph Runtime](Graph-Theory/README.md):

- a strict, deterministic task DAG for readiness, fenced leases, budgets, execution, and fan-in;
- a separate bounded cyclic Memory Fabric frontier that supplies context but cannot unlock tasks;
- append-only hash-chained run events, rebuildable snapshots, immutable slice and graph receipts, and recovery-by-linked-fork;
- structured result/evidence gates, candidate-first lesson promotion, and failed-writer receipts;
- matching CLI and compact Homebase MCP read/write surfaces;
- `legacy`, `shadow`, `dual`, and `runtime` compatibility projections, with `legacy` still the default.

The source implementation and baselines are verified in an isolated worktree. Controller-authoritative `dual`/`runtime` execution, plugin-cache parity, and fresh-host MCP exposure remain explicit cutover gates; see [verification](Graph-Theory/verification.md).

<details>
<summary>Earlier releases</summary>

- **v0.3.0** — Mapped the Homebase surfaces into nine first-class skill rows, each a thin adapter over the existing control plane.
- **v0.2.2** — Added the Codex marketplace manifest so the repo installs as a local marketplace.
- **v0.2.1** — `${PLUGIN_ROOT}`-first hook commands with `${CLAUDE_PLUGIN_ROOT}` fallback; plugin icon/metadata; validator bookkeeping.
- **v0.2.0** — 10 slash commands, 5 delegation agents, loop closure through session-learning capture, bounded fresh-context delegation, SIPS-owned Memory Fabric recall, touched-script verification, the persistent `/goal` loop, `/fan-out`, and the portable Homebase MCP tools.

</details>

## Status matrix

| Surface | Status | Notes |
|---|---|---|
| Plugin manifests | Works | `validate_v2.py` checks the manifest, skills, hooks, commands, agents, and MCP declaration (138 coherence checks). |
| SIPS Homebase MCP | Works | `homebase_status` and related read-only tools are exercised by regression tests. |
| SIPS graph runtime 0.4.0 | Source-verified, opt-in blocked | DAG, bounded memory frontier, receipts, CLI, and MCP surfaces are implemented. Default remains `legacy`; cache install, fresh-host exposure, and cutover are not yet claimed. |
| Memory Fabric | Works, SIPS-owned | Vendored under `scripts/memory_fabric*.py`; resolved before any legacy fallback. |
| Hook event tap | Works | Silent by default; `SIPS_DEBUG=1` writes failure details to `logs/hook_errors.jsonl`. |
| Regression runner | Works | `scripts/run_tests.py` — 97 cases. |
| pytest suite | Works | 360 repo-local tests covering core surfaces, the 0.4.0 runtime, indexed frontier, interfaces, recovery, and compatibility projections. |
| CI | Green | GitHub Actions compiles scripts, checks the Python floor, validates the manifest, and runs the suites on Ubuntu and macOS (3.10 / 3.12). |
| Packaging | Partial | `pyproject.toml` declares metadata and the Python floor; no package entry points yet. |
| Memory schema versioning | Partial | New records and the published schema carry `schema_version: 1.0`; migration tooling is planned. |
| Windows support | Untested | Current target is macOS / Linux POSIX hosts. |

## Verify

Run the manifest coherence check (fails if `EVAL.md` has drifted):

```bash
python3 scripts/validate_v2.py --check-eval
```

Regenerate `EVAL.md` explicitly:

```bash
python3 scripts/validate_v2.py --write-eval
```

Run the regression harness and the pytest suite:

```bash
python3 scripts/run_tests.py            # 97 cases
python3 scripts/run_tests.py homebase_mcp

python3 -m pip install ".[dev]"
pytest                                  # 360 tests
```

## Utility reference

**Validation & testing**

| Utility | Purpose |
|---|---|
| `validate_harness.py` | Validates installed harness health. |
| `validate_v2.py` | Validates plugin manifest coherence and regenerates `EVAL.md`. |
| `run_tests.py` | Runs the regression harness (97 cases). |
| `script_smoke.py` | Syntax and smoke checks for changed harness scripts. |
| `eval_harness.py` | Python eval runner. |
| `eval_llm_judge.py` | LLM-as-judge grader for eval cases. |
| `eval_grader_parity.py` | Golden-vector parity between the Python and Swift graders. |
| `fix_drafter.py` | Drafts candidate fixes for eval regressions. |

**SIPS Memory Fabric** (vendored under `scripts/memory_fabric*.py`)

| Utility | Purpose |
|---|---|
| `memory_fabric_preflight.py` | Surfaces prior lessons before edits. |
| `memory_fabric_doctor.py` | Checks Memory Fabric health and recent work. |
| `memory_fabric_prompt_search.py` | Searches Memory Fabric at prompt time. |
| `memory_fabric_compact_brief.py` | Injects a brief before compaction. |
| `memory_fabric_session_record.py` | Records post-compact session learnings. |
| `worktree_scope.py` | Resolves the working directory to a stable Memory Fabric scope. |

**Self-improvement & pattern analysis**

| Utility | Purpose |
|---|---|
| `self_correct.py` | Analyzes failures, stale scripts, and untested surfaces. |
| `agent_patterns.py` | Aggregates approach and outcome patterns from task history. |
| `proactive_drift.py` | Detects drift and untested scripts at session start. |
| `tool_factory.py` | Scaffolds or improves local harness tools. |
| `weekly_sweep.py` | Weekly self-improvement sweep entrypoint. |
| `task_outcome_tracker.py` | Records task outcomes for pattern analysis. |
| `brainstorm.py` | Ranks capability gaps for `/brainstorm`. |

**Recovery & maintenance**

| Utility | Purpose |
|---|---|
| `snapshot_harness.py` | Snapshots live harness scripts for rollback. |
| `restore_harness.py` | Restores a known-good harness snapshot. |
| `harness_gc.py` | Garbage-collects local harness state. |
| `branch_session.py` | Session branching helper. |
| `compact_continuity.py` | Continuity packet read/write helper. |
| `session_close.py` | Stop-event session close hook. |
| `monitor_daemon.py` | Proactive monitoring daemon. |

**Delegation, goals & plumbing**

| Utility | Purpose |
|---|---|
| `fan_out.py` | Prepares, ingests, lists, and inspects fan-out runs. |
| `goal_state.py` | Manages the persistent `/goal` loop state. |
| `sips_runtime.py` | 0.4.0 graph-runtime CLI. |
| `harness_homebase_mcp.py` | Serves the Homebase MCP control plane. |
| `harness_browser_mcp.py` | Exposes browser tools to the host harness over MCP stdio. |
| `hook_event_tap.py` | Wraps hook commands and appends hook-event JSONL. |
| `probe_hook.py` | Emits unique markers for hook invocation tests. |
| `sips_presence_mirror.py` | Mirrors SIPS presence files into the local host surface. |
| `repo_forensics.sh` | Wrapper for repo mapping via `homebase_repo_map`. |

## Design notes

This plugin is built around a few rules:

1. Memory should show up before it matters, not after the mistake.
2. Verification should run close to the edit that caused the risk.
3. Escalation should be bounded, not a second uncontrolled agent session.
4. Session closeout should produce useful future signal.
5. The harness should be able to inspect and improve itself without hiding what changed.

## Related project

**[Swift Harness](https://github.com/RasputinKaiser/Swift-Harness)** is the companion macOS GUI. Use this plugin for the harness logic; use Swift Harness when you want a native desktop control surface for status, tests, memory, snapshots, hooks, browser control, evals, agents, telemetry, and plugin surfaces.

## Security

This plugin runs local scripts and reads local harness state. Review the scripts before using them in another environment. Do not paste secrets, tokens, private transcripts, or private repo content into public issues. See `SECURITY.md` for vulnerability reporting.

## Contributing

Contributions are welcome through issues and pull requests. See `CONTRIBUTING.md` before opening larger changes.

## License

MIT. See `LICENSE`.
