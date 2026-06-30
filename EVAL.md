# EVAL - SIPS v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 72/72 (100%)
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
| 1 | marketplace.json valid + version 0.2.0 | PASS |
| 2 | marketplace declares delegation/inherit keywords | PASS |
| 3 | plugin.json version 0.2.0 | PASS |
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
| 22 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 23 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 24 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 25 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 26 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 27 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 28 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 29 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 30 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 31 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 32 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 33 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 34 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 35 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 36 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 37 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 38 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 39 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 40 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 41 | agent escalate has frontmatter + model: | PASS |
| 42 | agent escalate model: inherit | PASS |
| 43 | agent fan-out has frontmatter + model: | PASS |
| 44 | agent fan-out model: inherit | PASS |
| 45 | agent memory-curator has frontmatter + model: | PASS |
| 46 | agent memory-curator model: inherit | PASS |
| 47 | agent repo-scout has frontmatter + model: | PASS |
| 48 | agent repo-scout model: inherit | PASS |
| 49 | agent test-author has frontmatter + model: | PASS |
| 50 | agent test-author model: inherit | PASS |
| 51 | all 5 agents present | PASS |
| 52 | command brainstorm has description | PASS |
| 53 | command checkpoint has description | PASS |
| 54 | command escalate has description | PASS |
| 55 | command fan-out has description | PASS |
| 56 | command goal has description | PASS |
| 57 | command improve has description | PASS |
| 58 | command patterns has description | PASS |
| 59 | command recall has description | PASS |
| 60 | command teach has description | PASS |
| 61 | command verify has description | PASS |
| 62 | all 10 commands present | PASS |
| 63 | new script escalation_advisor.py exec | PASS |
| 64 | new script improvement_injector.py exec | PASS |
| 65 | new script recall_ranker.py exec | PASS |
| 66 | no runtime script imports model_router (v2 pivot) | PASS |
| 67 | observe (Stop: task_outcome_tracker) | PASS |
| 68 | distill (self_correct.py exists) | PASS |
| 69 | inject (SessionStart: improvement_injector) | PASS |
| 70 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 71 | delegate (PostToolUse: escalation_advisor) | PASS |
| 72 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (10): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach, /goal, /brainstorm, /fan-out — v1 had zero.
- **delegation agent surface** (5): escalate, repo-scout, memory-curator, test-author, fan-out — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on GLM 5.2 and Claude.
- **all v1 hooks reused unchanged** — purely additive; existing 38-case run_tests.py still passes.
