---
name: sips-selfloop
description: Start, inspect, or continue a persistent SIPS self-improvement loop. Use when the user asks for /selfloop, wants the agent to iteratively improve itself, or wants a goal dedicated only to SIPS and agent capability.
---

# SIPS Selfloop

Start or control the persistent loop with `python3 scripts/goal_state.py
selfloop-set "<focus>"` from the SIPS plugin root, following
`commands/selfloop.md`. Use the `homebase_selfloop` MCP tool instead when the
live server exposes it.

For each active cycle, establish a measured baseline, select one evidence-backed
self-improvement target, checkpoint, make the smallest useful change, verify the
gain against the baseline, and record the outcome. Restrict work to SIPS or the
agent's reasoning, tools, memory, verification, context efficiency, autonomy,
and self-correction. Do not substitute unrelated product work or cosmetic churn.

After a proven gain, run `python3 scripts/goal_state.py selfloop-record improved
"<proof-bearing summary>"` (or `homebase_selfloop` with action `record` when
exposed), then record any durable lesson through
SIPS Memory Fabric. Continue immediately while the goal is active. Two
independent plateau cycles may complete the current objective. A real external
block pauses the loop; an explicit stop clears it.

## Cost-bounded planning and review

For a planning or research-heavy cycle, use one drafting pass, one independent
blocker audit, and one final validation pass. Give each delegated task a bounded
surface and acceptance check, reuse the same agent for corrections, and do not
start a fresh audit round after every repair. Prefer mailbox completion events to
repeated `list_agents`/short `wait_agent` polling.

If the user says to finish, stop, or mentions usage/cost, freeze scope
immediately: stop pending expansion, ask active agents for blocker-only results,
apply only material fixes, run the minimum gating validation, and hand off. Do not
spend another review round polishing an already executable plan.

Report the current cycle, target, baseline, verification, and outcome.
