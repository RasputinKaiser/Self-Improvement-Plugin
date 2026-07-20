# EVAL - SIPS v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 138/138 (100%)
- **errors**: 0
- **warnings**: 0
- **verdict**: COHERENT — v2 manifest is wired end-to-end (inherit-only)

## Coverage

| Layer | Surface | Count | Status |
|---|---|---|---|
| L0 live surface | hooks wired | 19 | ok |
| L0 live surface | slash commands | 11 | ok |
| L0 live surface | Codex skills | 10 | ok |
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
| 1 | marketplace.json valid + version 0.4.0 | PASS |
| 2 | marketplace declares delegation/inherit keywords | PASS |
| 3 | Codex marketplace name harness-local | PASS |
| 4 | Codex marketplace declares harness-self-improvement | PASS |
| 5 | Codex marketplace source points at named plugin wrapper | PASS |
| 6 | Codex marketplace has install policy | PASS |
| 7 | Codex marketplace category present | PASS |
| 8 | plugin.json version 0.4.0 | PASS |
| 9 | plugin.json surfaces skills | PASS |
| 10 | plugin.json surfaces mcpServers | PASS |
| 11 | plugin.json omits host hooks field | PASS |
| 12 | plugin.json omits host agents field | PASS |
| 13 | plugin.json omits host commands field | PASS |
| 14 | plugin.json has interface object | PASS |
| 15 | plugin.json interface.displayName | PASS |
| 16 | plugin.json interface.shortDescription | PASS |
| 17 | plugin.json interface.longDescription | PASS |
| 18 | plugin.json interface.developerName | PASS |
| 19 | plugin.json interface.category | PASS |
| 20 | plugin.json has NO lib field (dropped in v2) | PASS |
| 21 | MCP manifest declares sips-homebase | PASS |
| 22 | MCP server uses stdio | PASS |
| 23 | MCP server points at harness_homebase_mcp.py | PASS |
| 24 | home-base MCP script exists+exec | PASS |
| 25 | pyproject.toml project version 0.4.0 | PASS |
| 26 | 0.4 graph runtime modules present | PASS |
| 27 | 0.4 graph runtime CLI exists+exec | PASS |
| 28 | Graph-Theory canonical docs present | PASS |
| 29 | Homebase exposes sips_runtime_read | PASS |
| 30 | Homebase exposes sips_runtime_write | PASS |
| 31 | indexed Memory Fabric frontier present | PASS |
| 32 | compatibility modes default to legacy | PASS |
| 33 | agents/ exists | PASS |
| 34 | commands/ exists | PASS |
| 35 | skills/ exists | PASS |
| 36 | no lib/ directory (model_router dropped) | PASS |
| 37 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 38 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 39 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 40 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 41 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 42 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 43 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 44 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 45 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 46 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 47 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 48 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 49 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 50 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 51 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 52 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 53 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 54 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 55 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 56 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 57 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 58 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 59 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 60 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 61 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 62 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 63 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 64 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 65 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 66 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 67 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 68 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 69 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 70 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 71 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 72 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 73 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 74 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 75 | agent escalate has frontmatter + model: | PASS |
| 76 | agent escalate model: inherit | PASS |
| 77 | agent fan-out has frontmatter + model: | PASS |
| 78 | agent fan-out model: inherit | PASS |
| 79 | agent memory-curator has frontmatter + model: | PASS |
| 80 | agent memory-curator model: inherit | PASS |
| 81 | agent repo-scout has frontmatter + model: | PASS |
| 82 | agent repo-scout model: inherit | PASS |
| 83 | agent test-author has frontmatter + model: | PASS |
| 84 | agent test-author model: inherit | PASS |
| 85 | all 5 agents present | PASS |
| 86 | command brainstorm has description | PASS |
| 87 | command checkpoint has description | PASS |
| 88 | command escalate has description | PASS |
| 89 | command fan-out has description | PASS |
| 90 | command goal has description | PASS |
| 91 | command improve has description | PASS |
| 92 | command patterns has description | PASS |
| 93 | command recall has description | PASS |
| 94 | command selfloop has description | PASS |
| 95 | command teach has description | PASS |
| 96 | command verify has description | PASS |
| 97 | all 11 commands present | PASS |
| 98 | skill sips-context-distiller has SKILL.md frontmatter | PASS |
| 99 | skill sips-context-distiller has Codex display metadata | PASS |
| 100 | skill sips-context-distiller icons exist | PASS |
| 101 | skill sips-control-plane has SKILL.md frontmatter | PASS |
| 102 | skill sips-control-plane has Codex display metadata | PASS |
| 103 | skill sips-control-plane icons exist | PASS |
| 104 | skill sips-delegation-router has SKILL.md frontmatter | PASS |
| 105 | skill sips-delegation-router has Codex display metadata | PASS |
| 106 | skill sips-delegation-router icons exist | PASS |
| 107 | skill sips-execution-repro has SKILL.md frontmatter | PASS |
| 108 | skill sips-execution-repro has Codex display metadata | PASS |
| 109 | skill sips-execution-repro icons exist | PASS |
| 110 | skill sips-memory-fabric has SKILL.md frontmatter | PASS |
| 111 | skill sips-memory-fabric has Codex display metadata | PASS |
| 112 | skill sips-memory-fabric icons exist | PASS |
| 113 | skill sips-perception-plan has SKILL.md frontmatter | PASS |
| 114 | skill sips-perception-plan has Codex display metadata | PASS |
| 115 | skill sips-perception-plan icons exist | PASS |
| 116 | skill sips-proof-scanner has SKILL.md frontmatter | PASS |
| 117 | skill sips-proof-scanner has Codex display metadata | PASS |
| 118 | skill sips-proof-scanner icons exist | PASS |
| 119 | skill sips-repo-map has SKILL.md frontmatter | PASS |
| 120 | skill sips-repo-map has Codex display metadata | PASS |
| 121 | skill sips-repo-map icons exist | PASS |
| 122 | skill sips-selfloop has SKILL.md frontmatter | PASS |
| 123 | skill sips-selfloop has Codex display metadata | PASS |
| 124 | skill sips-selfloop icons exist | PASS |
| 125 | skill sips-tool-factory has SKILL.md frontmatter | PASS |
| 126 | skill sips-tool-factory has Codex display metadata | PASS |
| 127 | skill sips-tool-factory icons exist | PASS |
| 128 | all 10 SIPS skills present | PASS |
| 129 | new script escalation_advisor.py exec | PASS |
| 130 | new script improvement_injector.py exec | PASS |
| 131 | new script recall_ranker.py exec | PASS |
| 132 | no runtime script imports model_router (v2 pivot) | PASS |
| 133 | observe (Stop: task_outcome_tracker) | PASS |
| 134 | distill (self_correct.py exists) | PASS |
| 135 | inject (SessionStart: improvement_injector) | PASS |
| 136 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 137 | delegate (PostToolUse: escalation_advisor) | PASS |
| 138 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (10): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach, /goal, /brainstorm, /fan-out — v1 had zero.
- **Codex skill surface** (9): SIPS control plane, proof scanner, delegation router, Memory Fabric, repo map, context distiller, execution repro, perception plan, and tool factory.
- **delegation agent surface** (5): escalate, repo-scout, memory-curator, test-author, fan-out — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on Claude Code and Codex.
- **hook behavior preserved with portable roots** — commands now prefer `${PLUGIN_ROOT}` and fall back to `${CLAUDE_PLUGIN_ROOT}`; hook-contract tests still pass.
