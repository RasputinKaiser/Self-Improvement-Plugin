---
name: goal
description: Set a goal and enter the RALPH loop — keep working autonomously until the goal is genuinely done or the user stops you. Use /goal "objective" to start, /goal status to check, /goal complete to finish, /goal clear to stop.
---

## /goal — RALPH goal loop

### Read-only Goal Board

Use the board for a compact, responsive progress view:

```bash
python3 scripts/goal_state.py board
python3 scripts/goal_state.py board <last_revision>
```

When a goal has a runtime attachment, this is projected from the event-backed
runtime and includes one foreground task, explicit presentation states,
bounded change deltas, suggestions, and task receipts. Without an attachment
it returns the same shape with `authority: legacy-goal-state`; that is a
compatibility projection, not runtime proof. The command is read-only and
never creates or advances a run.

### Campaign spine and child-thread fleet

For a goal that fans out into several child tasks or host conversations, create
one durable campaign spine and attach only the handles that the host actually
returns:

```bash
python3 scripts/sips_campaign_fleet.py create "Improve SIPS" \
  --campaign-id sips-overhaul \
  --contract-json '{"acceptance":["tests pass","proof boundaries recorded"]}'
python3 scripts/sips_campaign_fleet.py attach sips-overhaul \
  --child-id scout --title "Inspect archived task behavior" \
  --role Scout --thread-id '<host-thread-id>'
python3 scripts/sips_campaign_fleet.py status sips-overhaul --markdown
```

The fleet projection chooses one foreground child, retains bounded recent
activity, and supports `active`, `waiting`, `blocked`, `completed`, `failed`,
`canceled`, `archived`, and `reopen` lifecycle transitions. Reopen creates a
new child incarnation; pass a new `--thread-id` or `--task-id` when a fresh host
or runtime binding already exists. Search keeps archived handles retrievable
without treating them as active sidebar work. The registry does not enumerate,
archive, or mutate host conversations; those remain a separate host proof
layer.

The same surfaces are available as the read-only
`homebase_campaign_fleet_read` and write
`homebase_campaign_fleet_write` MCP tools. A runtime run can join its campaign
automatically by carrying `metadata.campaign_id`; the Goal Board then includes
the campaign projection without changing runtime event authority.

Parse the user's arguments:

### `/goal "<objective>"`
1. Write the goal to `${SIPS_HOME:-$HOME/.codex/sips}/goal_state.json`:
   ```json
   {"objective": "<the goal text>", "status": "active", "createdAt": "<ISO timestamp>", "turnCount": 0}
   ```
2. Confirm: "Goal set: **<objective>**. Entering RALPH loop — I will keep working until the goal is genuinely done or you say `/goal clear`."
3. Immediately start working toward the goal. Do not wait for another user message.

### `/goal status`
Read `${SIPS_HOME:-$HOME/.codex/sips}/goal_state.json` and print the current objective, status, turn count, and created-at timestamp.

### `/goal complete`
Mark the goal as `status: "complete"` in `${SIPS_HOME:-$HOME/.codex/sips}/goal_state.json`. Only do this when the objective is genuinely achieved — verified, not just attempted.

### `/goal clear`
Delete `${SIPS_HOME:-$HOME/.codex/sips}/goal_state.json`. Stop the RALPH loop immediately.

### `/goal pause`
Set `status: "paused"` in the state file. The loop continues on the next user message.

### `/goal resume`
Set `status: "active"` and continue working immediately.

## RALPH Loop Rules

While the goal status is `"active"`:

1. **Never stop at a summary.** A summary is not completion. If you wrote a summary, look at the evidence and choose the next concrete action.
2. **Never stop at "next steps" or a checklist.** A plan is evidence, not completion. Execute the plan.
3. **Never stop at a suggestion.** Suggestions are lazy — implement them.
4. **After each tool call or milestone, ask:** "Is the goal genuinely done? Verified?" If no, immediately choose and execute the next useful action without waiting for the user.
5. **If blocked by a real external dependency** (missing binary, network failure, auth prompt), stop and explain the blocker clearly. This is a valid stop.
6. **If you hit a hard system/tool limit** (context exhaustion, timeout), stop and explain.
7. **If the user sends any message that isn't a `/goal` command while the loop is active**, treat the message as steering input. Incorporate it, then continue working.
8. **Increment turnCount** in the state file after each turn.

## What "genuinely done" means

- The objective output exists
- Verification has passed (tests run, file checked, command succeeded)
- No remaining known steps are unfinished

If you're unsure whether the goal is done, it's NOT done. Keep working.

## Safety

- Snapshot before risky operations (call `snapshot_harness.py` or `/checkpoint`)
- Record each milestone as a Memory Fabric learning (use `/teach`)
- If the goal involves the binary (settings.json, ~/.local/ncode-builds/), autonomy_gate will remind you
- Do NOT override the user's explicit stop — `/goal clear` is authoritative

## Prohibited stop patterns

These are NOT valid reasons to stop while `status: "active"`:
- "Here's a summary of what I did"
- "Next steps would be..."
- "I'd suggest..."
- "Let me know if you want me to continue"
- "The plan is ready for your review"

If you catch yourself writing any of these, ask "is the goal done?" and if not, keep going.
