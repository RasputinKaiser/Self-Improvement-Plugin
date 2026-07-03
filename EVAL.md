# EVAL - SIPS v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 91/91 (100%)
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
| 1 | marketplace.json valid + version 0.2.1 | PASS |
| 2 | marketplace declares delegation/inherit keywords | PASS |
| 3 | plugin.json version 0.2.1 | PASS |
| 4 | plugin.json surfaces mcpServers | PASS |
| 5 | plugin.json omits host hooks field | PASS |
| 6 | plugin.json omits host agents field | PASS |
| 7 | plugin.json omits host commands field | PASS |
| 8 | plugin.json has interface object | PASS |
| 9 | plugin.json interface.displayName | PASS |
| 10 | plugin.json interface.shortDescription | PASS |
| 11 | plugin.json interface.longDescription | PASS |
| 12 | plugin.json interface.developerName | PASS |
| 13 | plugin.json interface.category | PASS |
| 14 | plugin.json has NO lib field (dropped in v2) | PASS |
| 15 | MCP manifest declares sips-homebase | PASS |
| 16 | MCP server uses stdio | PASS |
| 17 | MCP server points at harness_homebase_mcp.py | PASS |
| 18 | home-base MCP script exists+exec | PASS |
| 19 | agents/ exists | PASS |
| 20 | commands/ exists | PASS |
| 21 | no lib/ directory (model_router dropped) | PASS |
| 22 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 23 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 24 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 25 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 26 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 27 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 28 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 29 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 30 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 31 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 32 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 33 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 34 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 35 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 36 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 37 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 38 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 39 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 40 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 41 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 42 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 43 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 44 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 45 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 46 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 47 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 48 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 49 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 50 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 51 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 52 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 53 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 54 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 55 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 56 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 57 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 58 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 59 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 60 | agent escalate has frontmatter + model: | PASS |
| 61 | agent escalate model: inherit | PASS |
| 62 | agent fan-out has frontmatter + model: | PASS |
| 63 | agent fan-out model: inherit | PASS |
| 64 | agent memory-curator has frontmatter + model: | PASS |
| 65 | agent memory-curator model: inherit | PASS |
| 66 | agent repo-scout has frontmatter + model: | PASS |
| 67 | agent repo-scout model: inherit | PASS |
| 68 | agent test-author has frontmatter + model: | PASS |
| 69 | agent test-author model: inherit | PASS |
| 70 | all 5 agents present | PASS |
| 71 | command brainstorm has description | PASS |
| 72 | command checkpoint has description | PASS |
| 73 | command escalate has description | PASS |
| 74 | command fan-out has description | PASS |
| 75 | command goal has description | PASS |
| 76 | command improve has description | PASS |
| 77 | command patterns has description | PASS |
| 78 | command recall has description | PASS |
| 79 | command teach has description | PASS |
| 80 | command verify has description | PASS |
| 81 | all 10 commands present | PASS |
| 82 | new script escalation_advisor.py exec | PASS |
| 83 | new script improvement_injector.py exec | PASS |
| 84 | new script recall_ranker.py exec | PASS |
| 85 | no runtime script imports model_router (v2 pivot) | PASS |
| 86 | observe (Stop: task_outcome_tracker) | PASS |
| 87 | distill (self_correct.py exists) | PASS |
| 88 | inject (SessionStart: improvement_injector) | PASS |
| 89 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 90 | delegate (PostToolUse: escalation_advisor) | PASS |
| 91 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (10): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach, /goal, /brainstorm, /fan-out — v1 had zero.
- **delegation agent surface** (5): escalate, repo-scout, memory-curator, test-author, fan-out — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on GLM 5.2 and Claude.
- **hook behavior preserved with portable roots** — commands now prefer `${PLUGIN_ROOT}` and fall back to `${CLAUDE_PLUGIN_ROOT}`; hook-contract tests still pass.
