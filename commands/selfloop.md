---
name: selfloop
description: Start or control a persistent SIPS loop whose only objective is improving SIPS and the agent operating it through measured, verified iterations.
---

## /selfloop — evidence-driven self-improvement loop

Parse the user's arguments:

- `/selfloop [focus]` starts a new self-improvement loop. `focus` is optional.
- `/selfloop status` prints the current goal state.
- `/selfloop pause` and `/selfloop resume` control the active loop.
- `/selfloop complete` marks a genuinely finished loop complete.
- `/selfloop stop` or `/selfloop clear` clears the goal and stops immediately.

Use `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/goal_state.py` for every state
transition. To start, run `selfloop-set` with the optional focus. For controls,
use the existing `status`, `pause`, `resume`, `complete`, and `clear` actions.
Immediately begin the first cycle after `selfloop-set`; do not wait for another
message.

### Scope lock

The loop's entire focus is improving SIPS or the agent operating it. Valid
targets include reasoning quality, tool reliability, Memory Fabric recall,
verification quality, context efficiency, autonomy, self-correction, and the
proof surfaces that measure those capabilities. Do not drift into unrelated
product work, cosmetic churn, score gaming, or changes without a measurable
benefit.

### One cycle

1. Inspect current goal state and recall prior lessons for the relevant scope.
2. Establish a baseline with SIPS status, `self_correct.py --json`, the most
   relevant tests, and any direct runtime proof needed for the target.
3. Rank evidence-backed weaknesses by expected capability gain, confidence,
   recurrence, and implementation cost. Choose one. If uncertainty could change
   the choice, verify it before editing.
4. State the candidate, baseline, expected gain, and acceptance check in one
   compact note.
5. Run `/checkpoint`, then implement the smallest reversible change that can
   produce the gain.
6. Run focused verification first, then the relevant SIPS regression checks.
   Compare against the baseline. Keep the change only when the evidence shows an
   improvement; otherwise repair it or restore the checkpoint.
7. Record the cycle with `goal_state.py selfloop-record improved "<summary and
   proof>"`, append the result to the SIPS improvement ledger, and use `/teach`
   for any durable lesson.
8. Increment the goal turn count and immediately begin the next cycle while the
   goal remains active.

If a discovery pass finds no defensible improvement, record
`selfloop-record plateau "<evidence>"` and run one independent discovery pass
using a different signal. Two consecutive evidence-backed plateau passes mean
the current objective is genuinely complete; mark it complete instead of
inventing churn. For a real external dependency, record `blocked`, pause the
goal, and report the exact blocker. The user's stop command is always
authoritative.

Progress reports must name the current cycle, target, baseline, verification,
and outcome. A plan or summary is not a completed cycle.
