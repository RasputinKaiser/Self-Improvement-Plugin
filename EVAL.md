# EVAL - SIPS v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 96/96 (100%)
- **errors**: 0
- **warnings**: 0
- **verdict**: COHERENT — v2 manifest is wired end-to-end (inherit-only)

## Coverage

| Layer | Surface | Count | Status |
|---|---|---|---|
| L0 live surface | hooks wired | 19 | ok |
| L0 live surface | slash commands | 10 | ok |
| L0 live surface | subagents (all model: inherit) | 5 | ok |
| L1 guardrails | autonomy_gate + script_smoke + snapshot | 3 | ok |
| L2 observation | session_close + outcome_tracker | 2 | ok |
| L3 recall | preflight + recall_ranker + continuity | 3 | ok |
| L4 distillation | self_correct + agent_patterns | 2 | ok |
| L5 promotion | tool_factory + test-author agent + /improve | 3 | ok |
| delegation | escalate agent + escalation_advisor + /escalate | 3 | ok |
| model routing | (dropped — all agents inherit) | 0 | ok by design |

## Loop-closure chain

`observe → distill → inject → recall → delegate` — the actual self-improvement mechanism.

| Step | Wiring | Present |
|---|---|---|
| observe | Stop: task_outcome_tracker | yes |
| distill | self_correct.py exists | yes |
| inject | SessionStart: improvement_injector | yes |
| recall | UserPromptSubmit: recall_ranker | yes |
| delegate | PostToolUse: escalation_advisor | yes |
| delegate target | escalate agent exists, model: inherit | yes |

## Per-check results

| # | Check | Result |
|---|---|---|
| 1 | marketplace.json valid + version 0.2.2 | PASS |
| 2 | marketplace declares delegation/inherit keywords | PASS |
| 3 | Codex marketplace name harness-local | PASS |
| 4 | Codex marketplace declares harness-self-improvement | PASS |
| 5 | Codex marketplace source points at named plugin wrapper | PASS |
| 6 | Codex marketplace has install policy | PASS |
| 7 | Codex marketplace category present | PASS |
| 8 | plugin.json version 0.2.2 | PASS |
| 9 | plugin.json surfaces mcpServers | PASS |
| 10 | plugin.json omits host hooks field | PASS |
| 11 | plugin.json omits host agents field | PASS |
| 12 | plugin.json omits host commands field | PASS |
| 13 | plugin.json has interface object | PASS |
| 14 | plugin.json interface.displayName | PASS |
| 15 | plugin.json interface.shortDescription | PASS |
| 16 | plugin.json interface.longDescription | PASS |
| 17 | plugin.json interface.developerName | PASS |
| 18 | plugin.json interface.category | PASS |
| 19 | plugin.json has NO lib field (dropped in v2) | PASS |
| 20 | MCP manifest declares sips-homebase | PASS |
| 21 | MCP server uses stdio | PASS |
| 22 | MCP server points at harness_homebase_mcp.py | PASS |
| 23 | home-base MCP script exists+exec | PASS |
| 24 | agents/ exists | PASS |
| 25 | commands/ exists | PASS |
| 26 | no lib/ directory (model_router dropped) | PASS |
| 27 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 28 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 29 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 30 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 31 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 32 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 33 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 34 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 35 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 36 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 37 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 38 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 39 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 40 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 41 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 42 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 43 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 44 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 45 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 46 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 47 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 48 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 49 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 50 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 51 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 52 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 53 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 54 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 55 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 56 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 57 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 58 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 59 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 60 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 61 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 62 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 63 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 64 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 65 | agent escalate has frontmatter + model: | PASS |
| 66 | agent escalate model: inherit | PASS |
| 67 | agent fan-out has frontmatter + model: | PASS |
| 68 | agent fan-out model: inherit | PASS |
| 69 | agent memory-curator has frontmatter + model: | PASS |
| 70 | agent memory-curator model: inherit | PASS |
| 71 | agent repo-scout has frontmatter + model: | PASS |
| 72 | agent repo-scout model: inherit | PASS |
| 73 | agent test-author has frontmatter + model: | PASS |
| 74 | agent test-author model: inherit | PASS |
| 75 | all 5 agents present | PASS |
| 76 | command brainstorm has description | PASS |
| 77 | command checkpoint has description | PASS |
| 78 | command escalate has description | PASS |
| 79 | command fan-out has description | PASS |
| 80 | command goal has description | PASS |
| 81 | command improve has description | PASS |
| 82 | command patterns has description | PASS |
| 83 | command recall has description | PASS |
| 84 | command teach has description | PASS |
| 85 | command verify has description | PASS |
| 86 | all 10 commands present | PASS |
| 87 | new script escalation_advisor.py exec | PASS |
| 88 | new script improvement_injector.py exec | PASS |
| 89 | new script recall_ranker.py exec | PASS |
| 90 | no runtime script imports model_router (v2 pivot) | PASS |
| 91 | observe (Stop: task_outcome_tracker) | PASS |
| 92 | distill (self_correct.py exists) | PASS |
| 93 | inject (SessionStart: improvement_injector) | PASS |
| 94 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 95 | delegate (PostToolUse: escalation_advisor) | PASS |
| 96 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (10): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach, /goal, /brainstorm, /fan-out — v1 had zero.
- **delegation agent surface** (5): escalate, repo-scout, memory-curator, test-author, fan-out — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on GLM 5.2 and Claude.
- **hook behavior preserved with portable roots** — commands now prefer `${PLUGIN_ROOT}` and fall back to `${CLAUDE_PLUGIN_ROOT}`; hook-contract tests still pass.
