---
name: fan-out
description: Decompose a parent task into parallel slices and dispatch one fan-out agent per slice. Each slice runs in its own slice directory with a HANDOFF.md describing the parent and its scope. Use /fan-out "parent objective" with slice descriptions as args (semicolon-separated).
---

# /fan-out — multi-agent fan-out coordinator

Fan-out outputs can be displayed as board cards when attached to a runtime
campaign. Preserve the role boundary in each card (`Scout`, `Judge`, `Worker`,
or `PM`) and keep `SLICE`, `DIFF`, and `LESSON` as separate receipt fields.
`LESSON` is a candidate memory record until it passes the existing
verify-before-use path; a progress card is not evidence of execution.

When the host creates child tasks or conversations, attach the returned handles
to the campaign spine explicitly rather than guessing them:

```bash
python3 scripts/sips_campaign_fleet.py attach <campaign_id> \
  --child-id <slice_id> --title "<slice objective>" \
  --role Worker --thread-id <host_thread_id> --task-id <runtime_task_id>
```

Archive a finished child in the projection with `archive <campaign_id>
<child_id>`; use `reopen` when the work returns to the foreground. Reopen
creates a new child incarnation, so attach a new thread/task handle when one
exists. This keeps archived chat receipts searchable while leaving the host
conversation store untouched.

Parse user arguments:

### `/fan-out "<parent objective>"`
1. Split the objective from the slices. The user's input format:
   `<parent objective> | slice 1; slice 2; slice 3`
2. Call:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fan_out.py prepare \
     --parent "<parent objective>" \
     --slices "<slice 1>" "<slice 2>" "<slice 3>" \
     --campaign-id "<campaign_id>"
   ```
3. Read the resulting JSON. It contains a `runId` and per-slice `cwd` paths.
4. For **each** slice, dispatch a `fan-out` agent in parallel:
   - subagent_type: `fan-out`
   - cwd: the slice's directory (from `cwd` in the run state)
   - prompt: "Read HANDOFF.md in your cwd. Do your slice. End with SLICE/DIFF/LESSON or BLOCKED as the format requires."
5. Wait for all agents to return. Collect each agent's `result` field as the `response` for that slice.
6. Replay results back into the run state:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fan_out.py ingest --run-id <runId> \
     --outputs '[{"sliceId":"slice_1","response":"..."},{"sliceId":"slice_2","response":"..."}]'
   ```
7. Read the resulting summary. Surface disagreements and lessons to the user.
   `--campaign-id` only adds the explicit campaign reference to the fan-out
   projection; child host/thread handles are still attached after dispatch.

### `/fan-out status <runId>`
Show the state of a fan-out run.

### `/fan-out list`
List recent fan-out runs.

## Why fan-out

The harness's autonomy depends on bounded fresh-context delegation. With `escalate`, only one bounded task runs at a time. With `fan-out`, N independent slices run in parallel and merge — multiplying capability on decomposable tasks (porting a module, refactoring N files, validating N approaches).

Each slice:
- Reads `HANDOFF.md` for its scope and dependencies
- Ends with `SLICE: ... / DIFF: ... / LESSON: ...`
- The lesson is recorded to Memory Fabric so future fan-out runs avoid the same pain

## When NOT to fan-out

- Tasks with sequential dependencies (one slice needs another's output)
- Tasks that touch shared state (no isolation between slices)
- Single-step tasks where the main thread is well-suited to do it directly

Default to fanning out only when the parent decomposes into 2+ independent slices with bounded scope each.
