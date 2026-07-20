# EVAL - SIPS v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 144/144 (100%)
- **errors**: 0
- **warnings**: 0
- **verdict**: COHERENT — v2 manifest is wired end-to-end (inherit-only)

## Coverage

| Layer | Surface | Count | Status |
|---|---|---|---|
| L0 live surface | hooks wired | 20 | ok |
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
| 1 | pyproject.toml project version 0.4.0 | PASS |
| 2 | marketplace.json valid + version 0.4.0 | PASS |
| 3 | marketplace declares delegation/inherit keywords | PASS |
| 4 | Codex marketplace name harness-local | PASS |
| 5 | Codex marketplace declares harness-self-improvement | PASS |
| 6 | Codex marketplace source points at named plugin wrapper | PASS |
| 7 | Codex marketplace has install policy | PASS |
| 8 | Codex marketplace category present | PASS |
| 9 | plugin.json version 0.4.0 | PASS |
| 10 | plugin.json surfaces skills | PASS |
| 11 | plugin.json surfaces mcpServers | PASS |
| 12 | plugin.json omits host hooks field | PASS |
| 13 | plugin.json omits host agents field | PASS |
| 14 | plugin.json omits host commands field | PASS |
| 15 | plugin.json has interface object | PASS |
| 16 | plugin.json interface.displayName | PASS |
| 17 | plugin.json interface.shortDescription | PASS |
| 18 | plugin.json interface.longDescription | PASS |
| 19 | plugin.json interface.developerName | PASS |
| 20 | plugin.json interface.category | PASS |
| 21 | plugin.json interface.defaultPrompt respects Codex maximum of 3 | PASS |
| 22 | plugin.json has NO lib field (dropped in v2) | PASS |
| 23 | MCP manifest declares sips-homebase | PASS |
| 24 | MCP server uses stdio | PASS |
| 25 | MCP server points at harness_homebase_mcp.py | PASS |
| 26 | home-base MCP script exists+exec | PASS |
| 27 | pyproject.toml project version 0.4.0 | PASS |
| 28 | 0.4 graph runtime modules present | PASS |
| 29 | 0.4 graph runtime CLI exists+exec | PASS |
| 30 | Graph-Theory canonical docs present | PASS |
| 31 | Homebase exposes sips_runtime_read | PASS |
| 32 | Homebase exposes sips_runtime_write | PASS |
| 33 | indexed Memory Fabric frontier present | PASS |
| 34 | compatibility modes default to legacy | PASS |
| 35 | agents/ exists | PASS |
| 36 | commands/ exists | PASS |
| 37 | skills/ exists | PASS |
| 38 | no lib/ directory (model_router dropped) | PASS |
| 39 | retired NCode presence path is an inert compatibility tombstone | PASS |
| 40 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 41 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 42 | hook command uses PLUGIN_ROOT-first root (PreToolUse) | PASS |
| 43 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 44 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 45 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 46 | hook command uses PLUGIN_ROOT-first root (PostToolUse) | PASS |
| 47 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 48 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 49 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 50 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 51 | hook command uses PLUGIN_ROOT-first root (SessionStart) | PASS |
| 52 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 53 | hook command uses PLUGIN_ROOT-first root (UserPromptSubmit) | PASS |
| 54 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 55 | hook command uses PLUGIN_ROOT-first root (PreCompact) | PASS |
| 56 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 57 | hook command uses PLUGIN_ROOT-first root (PostCompact) | PASS |
| 58 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 59 | hook command uses PLUGIN_ROOT-first root (Stop) | PASS |
| 60 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 61 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 62 | hook script exists+exec: hook_event_tap.py (PreToolUse) | PASS |
| 63 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 64 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 65 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 66 | hook script exists+exec: hook_event_tap.py (PostToolUse) | PASS |
| 67 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 68 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 69 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 70 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 71 | hook script exists+exec: hook_event_tap.py (SessionStart) | PASS |
| 72 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 73 | hook script exists+exec: hook_event_tap.py (UserPromptSubmit) | PASS |
| 74 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 75 | hook script exists+exec: hook_event_tap.py (PreCompact) | PASS |
| 76 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 77 | hook script exists+exec: hook_event_tap.py (PostCompact) | PASS |
| 78 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 79 | hook script exists+exec: hook_event_tap.py (Stop) | PASS |
| 80 | agent escalate has frontmatter + model: | PASS |
| 81 | agent escalate model: inherit | PASS |
| 82 | agent fan-out has frontmatter + model: | PASS |
| 83 | agent fan-out model: inherit | PASS |
| 84 | agent memory-curator has frontmatter + model: | PASS |
| 85 | agent memory-curator model: inherit | PASS |
| 86 | agent repo-scout has frontmatter + model: | PASS |
| 87 | agent repo-scout model: inherit | PASS |
| 88 | agent test-author has frontmatter + model: | PASS |
| 89 | agent test-author model: inherit | PASS |
| 90 | all 5 agents present | PASS |
| 91 | command brainstorm has description | PASS |
| 92 | command checkpoint has description | PASS |
| 93 | command escalate has description | PASS |
| 94 | command fan-out has description | PASS |
| 95 | command goal has description | PASS |
| 96 | command improve has description | PASS |
| 97 | command patterns has description | PASS |
| 98 | command recall has description | PASS |
| 99 | command selfloop has description | PASS |
| 100 | command teach has description | PASS |
| 101 | command verify has description | PASS |
| 102 | all 11 commands present | PASS |
| 103 | selfloop command wires state, proof, and learning cycle | PASS |
| 104 | skill sips-context-distiller has SKILL.md frontmatter | PASS |
| 105 | skill sips-context-distiller has Codex display metadata | PASS |
| 106 | skill sips-context-distiller icons exist | PASS |
| 107 | skill sips-control-plane has SKILL.md frontmatter | PASS |
| 108 | skill sips-control-plane has Codex display metadata | PASS |
| 109 | skill sips-control-plane icons exist | PASS |
| 110 | skill sips-delegation-router has SKILL.md frontmatter | PASS |
| 111 | skill sips-delegation-router has Codex display metadata | PASS |
| 112 | skill sips-delegation-router icons exist | PASS |
| 113 | skill sips-execution-repro has SKILL.md frontmatter | PASS |
| 114 | skill sips-execution-repro has Codex display metadata | PASS |
| 115 | skill sips-execution-repro icons exist | PASS |
| 116 | skill sips-memory-fabric has SKILL.md frontmatter | PASS |
| 117 | skill sips-memory-fabric has Codex display metadata | PASS |
| 118 | skill sips-memory-fabric icons exist | PASS |
| 119 | skill sips-perception-plan has SKILL.md frontmatter | PASS |
| 120 | skill sips-perception-plan has Codex display metadata | PASS |
| 121 | skill sips-perception-plan icons exist | PASS |
| 122 | skill sips-proof-scanner has SKILL.md frontmatter | PASS |
| 123 | skill sips-proof-scanner has Codex display metadata | PASS |
| 124 | skill sips-proof-scanner icons exist | PASS |
| 125 | skill sips-repo-map has SKILL.md frontmatter | PASS |
| 126 | skill sips-repo-map has Codex display metadata | PASS |
| 127 | skill sips-repo-map icons exist | PASS |
| 128 | skill sips-selfloop has SKILL.md frontmatter | PASS |
| 129 | skill sips-selfloop has Codex display metadata | PASS |
| 130 | skill sips-selfloop icons exist | PASS |
| 131 | skill sips-tool-factory has SKILL.md frontmatter | PASS |
| 132 | skill sips-tool-factory has Codex display metadata | PASS |
| 133 | skill sips-tool-factory icons exist | PASS |
| 134 | all 10 SIPS skills present | PASS |
| 135 | new script escalation_advisor.py exec | PASS |
| 136 | new script improvement_injector.py exec | PASS |
| 137 | new script recall_ranker.py exec | PASS |
| 138 | no runtime script imports model_router (v2 pivot) | PASS |
| 139 | observe (Stop: task_outcome_tracker) | PASS |
| 140 | distill (self_correct.py exists) | PASS |
| 141 | inject (SessionStart: improvement_injector) | PASS |
| 142 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 143 | delegate (PostToolUse: escalation_advisor) | PASS |
| 144 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (11): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach, /goal, /selfloop, /brainstorm, /fan-out — v1 had zero.
- **Codex skill surface** (10): SIPS control plane, proof scanner, delegation router, Memory Fabric, repo map, context distiller, execution repro, perception plan, tool factory, and selfloop.
- **delegation agent surface** (5): escalate, repo-scout, memory-curator, test-author, fan-out — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on Claude Code and Codex.
- **hook behavior preserved with portable roots** — commands now prefer `${PLUGIN_ROOT}` and fall back to `${CLAUDE_PLUGIN_ROOT}`; hook-contract tests still pass.
