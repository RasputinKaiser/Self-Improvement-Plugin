# Self-Improvement-Plugin

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: dev](https://img.shields.io/badge/status-dev-orange)
![NCode plugin](https://img.shields.io/badge/NCode-plugin-purple)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/W7W7C9TC7)

A self-improvement harness plugin for NCode, a Claude Code fork, pulled from my personal Codex plugins and combined. This is extremely experimental and WIP, testing ended and I'm out of usage, so here's some bones!

**Suggested GitHub topics:** `agent-harness`, `ai-agents`, `ncode`, `claude-code`, `memory-fabric`, `self-improvement`, `automation`, `evals`, `python`, `developer-tools`

*+Very Experimental Swift/MacOS Sibling-App | Not Quite Working, but free | Native macOS control surface for the [Swift-Harness](https://github.com/RasputinKaiser/Swift-Harness).*

Self-Improvement-Plugin gives an agent memory-aware startup, safer tool use, session closeout, verification hooks, and fresh-context delegation. It is built for long agent sessions where the agent needs to remember prior work, avoid repeated mistakes, recover from drift, and capture lessons before the context disappears.

The plugin does not try to make an agent smarter by changing models. It improves the work loop around the model.

It helps each session answer:

- What did we learn last time?
- Is this edit risky?
- Did the changed script still pass a smoke check?
- Is this task stuck enough to split out?
- What should future sessions remember?
- Which agent patterns have worked or failed before?

## Public status

This project is public-readable documentation for a local-first NCode harness workflow. It assumes a working local NCode setup and a `~/.ncode` harness directory.

The repo is useful if you are exploring:

- agent lifecycle hooks
- memory-aware coding agents
- local harness verification
- agent eval loops
- fresh-context delegation
- long-running agent workflows

Expect sharp edges. This is an active development harness, not a packaged end-user app.

## What it adds

Self-Improvement-Plugin adds four main surfaces:

| Surface | Purpose |
|---|---|
| Lifecycle hooks | Run checks and memory actions during startup, prompt submit, tool use, compaction, and session close. |
| Slash commands | Give the user direct control over recall, improvement, verification, goals, escalation, and fan-out. |
| Delegation agents | Send bounded subtasks into fresh context while keeping the parent session clean. |
| Utility scripts | Validate, test, snapshot, restore, inspect, and improve the harness over time. |

## Current release

### v0.2.0

This release adds:

- 10 slash commands
- 5 delegation agents
- live-service command surface
- loop closure through session learning capture
- bounded fresh-context delegation
- Memory Fabric recall before edits and prompts
- verification support for touched scripts
- persistent goal loop support through `/goal`
- fan-out support for parallel task slices

All delegation agents use:

```yaml
model: inherit
```

The default workflow model is GLM 5.2, but the plugin does not rely on model swaps. The main gain comes from context control, scoped recall, verification, and recorded outcomes.

## Related project

Swift Harness is the companion macOS GUI for this plugin:

```text
https://github.com/RasputinKaiser/Swift-Harness
```

Use this plugin for the harness logic. Use Swift Harness when you want a native desktop control surface for status, tests, memory, snapshots, hooks, browser control, evals, agents, telemetry, and plugin surfaces.

## Install

Add the marketplace source:

```bash
/plugin marketplace add RasputinKaiser/Self-Improvement-Plugin
```

Then install this plugin from the marketplace UI:

```text
Self-Improvement-Plugin@harness-local
```

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.8+ | Required for the hook and utility scripts. |
| Codex Memory Fabric plugin | Required for Memory Fabric recall, lesson capture, and memory health checks. |
| CSI Host Surface Audit plugin | Optional. Used for deeper cleanup through `harness_gc.py --deep`. |

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
| `/goal` | Sets, inspects, pauses, resumes, completes, or clears the RALPH goal loop. | You want the harness to keep a persistent goal across steps. |
| `/brainstorm` | Surveys capability gaps and asks the escalation agent for a build plan. | You want ideas for what the harness should improve next. |
| `/fan-out` | Decomposes a parent task into parallel slice agents and merges their outputs. | A task can be split into independent research, coding, or inspection slices. |

## Delegation agents

Delegation agents are meant to keep the parent session from getting overloaded.

Each agent gets a bounded job. It returns a focused result instead of taking over the whole task.

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
| `PostToolUse` | `Edit`, `Write`, `MultiEdit`, `Bash`, `apply_patch`, `mcp__.*` | `script_smoke.py`, `escalation_advisor.py`, `csi_presence_mirror.py` |
| `SessionStart` | `startup`, `resume`, `clear`, `compact` | `validate_harness.py`, `memory_fabric_doctor.py`, `proactive_drift.py`, `agent_patterns.py --brief`, `improvement_injector.py` |
| `UserPromptSubmit` | all prompts | `recall_ranker.py`, `probe_hook.py` |
| `PreCompact` | `manual`, `auto` | `memory_fabric_compact_brief.py`, `compact_continuity.py` |
| `PostCompact` | `manual`, `auto` | `memory_fabric_session_record.py`, `compact_continuity.py` |
| `Stop` | all stops | `session_close.py`, `task_outcome_tracker.py --record` |

## Hook behavior by phase

### Startup

Startup hooks prepare the session before the agent begins work.

They validate the harness, check Memory Fabric health, detect drift, surface prior patterns, and inject improvement context.

Relevant scripts:

| Script | Purpose |
|---|---|
| `validate_harness.py` | Validates installed harness health. |
| `memory_fabric_doctor.py` | Checks Memory Fabric health and recent work. |
| `proactive_drift.py` | Detects drift and untested scripts at session start. |
| `agent_patterns.py --brief` | Loads a short success/failure pattern brief. |
| `improvement_injector.py` | Injects current improvement guidance into the session. |

### Prompt submit

Prompt submit hooks run when the user sends a task.

They search prior memory, rank likely useful lessons, and emit markers for hook tests.

Relevant scripts:

| Script | Purpose |
|---|---|
| `recall_ranker.py` | Ranks prior lessons for the current prompt and scope. |
| `probe_hook.py` | Emits unique markers for hook invocation tests. |

### Before tool use

Pre-tool hooks run before edits, writes, patches, and shell commands.

They protect the harness from unsafe autonomous actions and surface lessons before risky changes.

Relevant scripts:

| Script | Purpose |
|---|---|
| `autonomy_gate.py` | Blocks or warns on risky autonomous tool use. |
| `memory_fabric_preflight.py` | Surfaces prior lessons before edits. |

### After tool use

Post-tool hooks run after edits, writes, shell commands, patches, and MCP calls.

They smoke-check changed scripts, advise escalation when the task appears stuck, and mirror CSI presence files into the NCode surface.

Relevant scripts:

| Script | Purpose |
|---|---|
| `script_smoke.py` | Runs syntax and smoke checks for changed harness scripts. |
| `escalation_advisor.py` | Flags cases where a bounded escalation may help. |
| `csi_presence_mirror.py` | Mirrors CSI presence files into the NCode surface. |

### Compaction

Compaction hooks preserve continuity before and after the context is compressed.

Relevant scripts:

| Script | Purpose |
|---|---|
| `memory_fabric_compact_brief.py` | Injects a Memory Fabric brief before compaction. |
| `compact_continuity.py` | Reads and writes continuity packets. |
| `memory_fabric_session_record.py` | Records post-compact session learnings. |

### Stop

Stop hooks close the loop after the session ends.

They record the session closeout and task outcome so future pattern analysis has real history to work from.

Relevant scripts:

| Script | Purpose |
|---|---|
| `session_close.py` | Handles stop-event session closeout. |
| `task_outcome_tracker.py --record` | Records task outcomes for pattern analysis. |

## Utility reference

### Validation and testing

| Utility | Purpose |
|---|---|
| `validate_harness.py` | Validates installed harness health. |
| `validate_v2.py` | Validates plugin manifest coherence and regenerates `EVAL.md`. |
| `run_tests.py` | Runs the regression harness. Current suite: 90 cases. |
| `script_smoke.py` | Runs syntax and smoke checks for changed harness scripts. |
| `eval_harness.py` | Python mirror of the Swift eval runner. |
| `eval_llm_judge.py` | LLM-as-judge grader for eval cases. |
| `eval_grader_parity.py` | Golden-vector parity checker between Python and Swift graders. |
| `fix_drafter.py` | Drafts candidate fixes for eval regressions. |

### Memory Fabric

| Utility | Purpose |
|---|---|
| `memory_fabric_preflight.py` | Surfaces prior lessons before edits. |
| `memory_fabric_doctor.py` | Checks Memory Fabric health and recent work. |
| `memory_fabric_prompt_search.py` | Searches Memory Fabric at prompt time. |
| `memory_fabric_compact_brief.py` | Injects a Memory Fabric brief before compaction. |
| `memory_fabric_session_record.py` | Records post-compact session learnings. |
| `worktree_scope.py` | Resolves the current working directory to a stable Memory Fabric scope. |

### Self-improvement and pattern analysis

| Utility | Purpose |
|---|---|
| `self_correct.py` | Analyzes failures, stale scripts, and untested surfaces. |
| `agent_patterns.py` | Aggregates approach and outcome patterns from task history. |
| `proactive_drift.py` | Detects drift and untested scripts at session start. |
| `tool_factory.py` | Scaffolds or improves local harness tools. |
| `weekly_sweep.py` | Weekly self-improvement sweep entrypoint. |
| `task_outcome_tracker.py` | Records task outcomes for pattern analysis. |
| `session_close.py` | Stop-event session close hook. |

### Recovery and maintenance

| Utility | Purpose |
|---|---|
| `snapshot_harness.py` | Snapshots live harness scripts for rollback. |
| `restore_harness.py` | Restores a known-good harness snapshot. |
| `harness_gc.py` | Garbage collects local harness state. |
| `branch_session.py` | Session branching helper. |
| `compact_continuity.py` | Continuity packet read/write helper. |

### Delegation and planning

| Utility | Purpose |
|---|---|
| `fan_out.py` | Prepares, ingests, lists, and inspects fan-out runs. |
| `brainstorm.py` | Ranks capability gaps for `/brainstorm`. |
| `goal_state.py` | Manages persistent `/goal` loop state. |
| `monitor_daemon.py` | Proactive monitoring daemon. |

### Integrations

| Utility | Purpose |
|---|---|
| `repo_forensics.sh` | Thin wrapper for CSI repo forensics. |
| `harness_browser_mcp.py` | Exposes browser tools to NCode through MCP stdio. |
| `patch_effort_message.py` | Patches local effort messaging for GLM 5.2 workflows. |
| `hook_event_tap.py` | Wraps hook commands and appends hook-event JSONL. |
| `probe_hook.py` | Emits unique markers for hook invocation tests. |
| `csi_presence_mirror.py` | Mirrors CSI presence files into the NCode surface. |

## Verify

Run the manifest coherence check:

```bash
python3 scripts/validate_v2.py
```

This validates plugin manifest coherence and regenerates `EVAL.md`.

Run the regression harness:

```bash
python3 scripts/run_tests.py
```

Current expected suite size:

```text
90 cases
```

## When to use each command

| Situation | Command |
|---|---|
| You are about to touch important harness code. | `/checkpoint` |
| You think the agent is repeating an old mistake. | `/recall` |
| The current session is stuck. | `/escalate` |
| You changed scripts and want confidence. | `/verify` |
| You found a reusable lesson. | `/teach` |
| You want to inspect what approaches have worked before. | `/patterns` |
| You want the harness to improve itself. | `/improve` |
| You want to keep a persistent goal active. | `/goal` |
| You want improvement ideas. | `/brainstorm` |
| You want to split a task into slices. | `/fan-out` |

## Design notes

This plugin is built around a few rules:

1. Memory should show up before it matters, not after the mistake.
2. Verification should run close to the edit that caused risk.
3. Escalation should be bounded, not a second uncontrolled agent session.
4. Session closeout should produce useful future signal.
5. The harness should be able to inspect and improve itself without hiding what changed.

## Security

This plugin runs local scripts and reads local harness state. Review scripts before using them in another environment.

Do not paste secrets, access tokens, private transcripts, or private repo content into public issues. See `SECURITY.md` for vulnerability reporting notes.

## Contributing

Contributions are welcome through issues and pull requests. See `CONTRIBUTING.md` before opening larger changes.

## License

MIT. See `LICENSE`.
