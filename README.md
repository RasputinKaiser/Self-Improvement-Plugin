# harness-self-improvement

A self-improving agent harness plugin for NCode (Claude Code fork). Provides
hooks across the full agent lifecycle so each task starts informed by prior
work and each session closes with recorded learnings — and a delegation agent
surface so a stuck subtask can be carved into a fresh, bounded context.

## What's included

**v0.2.0** adds a live-service command surface (10 slash commands), a delegation
agent surface (5 subagents, all `model: inherit`), and loop closure. All agents
inherit the session model (GLM 5.2 by default) — versatility comes from bounded
fresh-context delegation and forced lesson capture, not model swaps.

### Lifecycle hooks

| Event | Matchers | Scripts |
|---|---|---|
| `PreToolUse` | `Edit`, `Write`, `MultiEdit`, `Bash`, `apply_patch` | `autonomy_gate.py`, `memory_fabric_preflight.py` |
| `PostToolUse` | `Edit`, `Write`, `MultiEdit`, `Bash`, `apply_patch`, `mcp__.*` | `script_smoke.py`, `escalation_advisor.py`, `csi_presence_mirror.py` |
| `SessionStart` | `startup`, `resume`, `clear`, `compact` | `validate_harness.py`, `memory_fabric_doctor.py`, `proactive_drift.py`, `agent_patterns.py --brief`, `improvement_injector.py` |
| `UserPromptSubmit` | all prompts | `recall_ranker.py`, `probe_hook.py` |
| `PreCompact` | `manual`, `auto` | `memory_fabric_compact_brief.py`, `compact_continuity.py` |
| `PostCompact` | `manual`, `auto` | `memory_fabric_session_record.py`, `compact_continuity.py` |
| `Stop` | all stops | `session_close.py`, `task_outcome_tracker.py --record` |

### Slash commands

| Command | Purpose |
|---|---|
| `/improve` | Run a self-correction sweep and act on the top recommendation. |
| `/recall` | Search Memory Fabric for ranked prior lessons in the current scope. |
| `/escalate` | Send one bounded stuck subtask to a fresh-context escalation agent. |
| `/checkpoint` | Snapshot the harness and write a continuity packet before risky work. |
| `/verify` | Run the regression harness plus smoke checks for touched scripts. |
| `/patterns` | Show the agent-patterns dashboard with success/failure correlations. |
| `/teach` | Hand-record a high-signal lesson into Memory Fabric. |
| `/goal` | Set, inspect, pause, resume, complete, or clear the RALPH goal loop. |
| `/brainstorm` | Survey capability gaps and ask the escalation agent for a build plan. |
| `/fan-out` | Decompose a parent task into parallel slice agents and merge their outputs. |

### Delegation agents

| Agent | Role |
|---|---|
| `escalate` | Solve one bounded blocker in a fresh context and return `DIFF` plus `LESSON`. |
| `repo-scout` | Read-only repo reconnaissance: files, map, and one gotcha. |
| `memory-curator` | Dedupe, promote, and archive Memory Fabric records without deleting data. |
| `test-author` | Add one focused `run_tests.py` regression for an untested or risky script. |
| `fan-out` | Solve one independent slice from a decomposed parent task. |

### On-demand utilities

| Utility | Purpose |
|---|---|
| `validate_harness.py` | Validate installed harness health. |
| `validate_v2.py` | Validate plugin manifest coherence and regenerate `EVAL.md`. |
| `run_tests.py` | Regression harness; current suite is 90 cases. |
| `script_smoke.py` | Syntax/smoke check changed harness scripts. |
| `snapshot_harness.py` | Snapshot live harness scripts for rollback. |
| `restore_harness.py` | Restore a known-good harness snapshot. |
| `harness_gc.py` | Garbage collect local harness state. |
| `self_correct.py` | Analyze failures, stale scripts, and untested surfaces. |
| `agent_patterns.py` | Aggregate approach/outcome patterns from task history. |
| `proactive_drift.py` | Detect drift and untested scripts at session start. |
| `tool_factory.py` | Scaffold or improve local harness tools. |
| `repo_forensics.sh` | Thin wrapper for CSI repo forensics. |
| `fan_out.py` | Prepare, ingest, list, and inspect fan-out runs. |
| `brainstorm.py` | Rank capability gaps for `/brainstorm`. |
| `goal_state.py` | Manage persistent `/goal` loop state. |
| `harness_browser_mcp.py` | Expose browser tools to NCode through MCP stdio. |
| `eval_harness.py` | Python mirror of the Swift eval runner. |
| `eval_llm_judge.py` | LLM-as-judge grader for eval cases. |
| `eval_grader_parity.py` | Golden-vector parity between Python and Swift graders. |
| `fix_drafter.py` | Draft candidate fixes for eval regressions. |
| `monitor_daemon.py` | Proactive monitoring daemon. |
| `patch_effort_message.py` | Patch local effort messaging for GLM 5.2 workflows. |
| `weekly_sweep.py` | Weekly self-improvement sweep entrypoint. |
| `worktree_scope.py` | Resolve cwd to stable Memory Fabric scope. |
| `hook_event_tap.py` | Wrap hook commands and append hook-event JSONL. |
| `probe_hook.py` | Emit unique markers for hook invocation tests. |
| `branch_session.py` | Session branching helper. |
| `compact_continuity.py` | Continuity packet read/write helper. |
| `session_close.py` | Stop-event session close hook. |
| `task_outcome_tracker.py` | Record task outcomes for pattern analysis. |
| `csi_presence_mirror.py` | Mirror CSI presence files into the NCode surface. |
| `memory_fabric_preflight.py` | Surface prior lessons before edits. |
| `memory_fabric_doctor.py` | Check Memory Fabric health and recent work. |
| `memory_fabric_prompt_search.py` | Prompt-time Memory Fabric search helper. |
| `memory_fabric_compact_brief.py` | Inject Memory Fabric brief before compaction. |
| `memory_fabric_session_record.py` | Record post-compact session learnings. |

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
python3 scripts/run_tests.py     # 90-case regression harness
```

## License

MIT — see LICENSE.
