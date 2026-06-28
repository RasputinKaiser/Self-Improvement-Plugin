# EVAL — harness-self-improvement v2 architecture (inherit-only)

Self-validation of the v2 plugin manifest coherence. Run command: `python3 scripts/validate_v2.py`. Exit 0 if clean, 1 on any ERROR.

## Summary

- **checks passed**: 56/56 (100%)
- **errors**: 0
- **warnings**: 0
- **verdict**: COHERENT — v2 manifest is wired end-to-end (inherit-only)

## Coverage

| Layer | Surface | Count | Status |
|---|---|---|---|
| L0 live surface | hooks wired | 19 | ok |
| L0 live surface | slash commands | 7 | ok |
| L0 live surface | subagents (all model: inherit) | 4 | ok |
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
| 4 | plugin.json surfaces hooks | PASS |
| 5 | plugin.json surfaces agents | PASS |
| 6 | plugin.json surfaces commands | PASS |
| 7 | plugin.json has NO lib field (dropped in v2) | PASS |
| 8 | agents/ exists | PASS |
| 9 | commands/ exists | PASS |
| 10 | no lib/ directory (model_router dropped) | PASS |
| 11 | hook script exists+exec: autonomy_gate.py (PreToolUse) | PASS |
| 12 | hook script exists+exec: memory_fabric_preflight.py (PreToolUse) | PASS |
| 13 | hook script exists+exec: autonomy_gate.py (PreToolUse) | PASS |
| 14 | hook script exists+exec: script_smoke.py (PostToolUse) | PASS |
| 15 | hook script exists+exec: escalation_advisor.py (PostToolUse) | PASS |
| 16 | hook script exists+exec: csi_presence_mirror.py (PostToolUse) | PASS |
| 17 | hook script exists+exec: validate_harness.py (SessionStart) | PASS |
| 18 | hook script exists+exec: memory_fabric_doctor.py (SessionStart) | PASS |
| 19 | hook script exists+exec: proactive_drift.py (SessionStart) | PASS |
| 20 | hook script exists+exec: agent_patterns.py (SessionStart) | PASS |
| 21 | hook script exists+exec: improvement_injector.py (SessionStart) | PASS |
| 22 | hook script exists+exec: recall_ranker.py (UserPromptSubmit) | PASS |
| 23 | hook script exists+exec: probe_hook.py (UserPromptSubmit) | PASS |
| 24 | hook script exists+exec: memory_fabric_compact_brief.py (PreCompact) | PASS |
| 25 | hook script exists+exec: compact_continuity.py (PreCompact) | PASS |
| 26 | hook script exists+exec: memory_fabric_session_record.py (PostCompact) | PASS |
| 27 | hook script exists+exec: compact_continuity.py (PostCompact) | PASS |
| 28 | hook script exists+exec: session_close.py (Stop) | PASS |
| 29 | hook script exists+exec: task_outcome_tracker.py (Stop) | PASS |
| 30 | agent escalate has frontmatter + model: | PASS |
| 31 | agent escalate model: inherit | PASS |
| 32 | agent test-author has frontmatter + model: | PASS |
| 33 | agent test-author model: inherit | PASS |
| 34 | agent memory-curator has frontmatter + model: | PASS |
| 35 | agent memory-curator model: inherit | PASS |
| 36 | agent repo-scout has frontmatter + model: | PASS |
| 37 | agent repo-scout model: inherit | PASS |
| 38 | all 4 agents present | PASS |
| 39 | command improve has description | PASS |
| 40 | command escalate has description | PASS |
| 41 | command verify has description | PASS |
| 42 | command checkpoint has description | PASS |
| 43 | command patterns has description | PASS |
| 44 | command recall has description | PASS |
| 45 | command teach has description | PASS |
| 46 | all 7 commands present | PASS |
| 47 | new script improvement_injector.py exec | PASS |
| 48 | new script escalation_advisor.py exec | PASS |
| 49 | new script recall_ranker.py exec | PASS |
| 50 | no runtime script imports model_router (v2 pivot) | PASS |
| 51 | observe (Stop: task_outcome_tracker) | PASS |
| 52 | distill (self_correct.py exists) | PASS |
| 53 | inject (SessionStart: improvement_injector) | PASS |
| 54 | recall (UserPromptSubmit: recall_ranker) | PASS |
| 55 | delegate (PostToolUse: escalation_advisor) | PASS |
| 56 | delegate target (escalate agent exists, model: inherit) | PASS |

## What v2 adds over v1

- **live-service commands** (7): /improve, /recall, /escalate, /checkpoint, /verify, /patterns, /teach — v1 had zero.
- **delegation agent surface** (4): escalate, repo-scout, memory-curator, test-author — all `model: inherit` — v1 had none.
- **loop closure**: improvement_injector reads self_correct output back into each session (v1 wrote it, never consumed).
- **deterministic delegation**: escalation_advisor detects 'stuck' from live signals and suggests /escalate — never spends a model call to decide whether to delegate.
- **scoped recall ranking**: recall_ranker ranks failure-then-success and scopes to cwd (replaces raw prompt_search).
- **no model routing**: dropped v1's tier-detection library entirely. Versatility comes from bounded fresh-context delegation + forced lesson capture, not model swaps. Same behavior on GLM 5.2 and Claude.
- **all v1 hooks reused unchanged** — purely additive; existing 38-case run_tests.py still passes.
