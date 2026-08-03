---
description: Run an evidence-gated retrospective, capture reusable SIPS lessons with provenance, and leave one clear next action.
---
# /retro — close the loop on this session

Argument: `$ARGUMENTS` is an optional focus. Use it to narrow the review to a
repo, task, failure, or capability. A retrospective is a reusable learning
pass, not a diary entry and not a reason to manufacture a lesson.

## 1. Establish the evidence boundary

Resolve the current scope and collect the smallest useful evidence set:

1. Run `pwd -P`, `git status --short`, and `git diff --stat` for the current
   repository. Treat existing dirty changes as user-owned unless the current
   task clearly explains them.
2. Query recent structured outcomes:
   `python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/task_outcome_tracker.py --query --limit 8`.
3. Search scoped prior lessons:
   `python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/recall_ranker.py --query "$ARGUMENTS" --json`.
4. Re-read the current conversation for the actual failed attempt, working
   correction, user direction, and final proof. If the host exposes an exact
   transcript path, preserve it as the evidence path; do not invent a path
   from a session id. If a separately installed Retro transcript miner is
   available, it may supplement this pass, but its absence is not a SIPS
   failure and this command must not duplicate that miner.
5. Inspect `state.yaml` or relevant receipts only when they can confirm or
   disprove a conclusion. Keep source, cache, runtime, host, and public proof
   layers separate.

## 2. Classify the signal

Rank fix-ups and recurring hurdles before new observations. For each candidate,
identify the exact evidence and classify it as one of:

- **record** — a durable retry chain, unresolved failure, user correction,
  prerequisite, environment fact, or repeated friction that another session
  could reuse;
- **skip** — one-off noise, a typo, a transient provider/network issue, or a
  conclusion supported only by absence;
- **unclear** — plausible but not yet supported; name the missing proof.

An unresolved failure is not a success lesson. A workaround is not a fix unless
the working form and its verification are both visible. Preserve the user's
standing preferences separately from inferred technical facts.

## 3. Write only durable, provenance-backed lessons

For every **record** item, write one scoped learning-tier Memory Fabric record
through the native `homebase_record` tool when it is available. Otherwise use
the local CLI:

```bash
python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/memory_fabric.py record \
  --tier learning \
  --title "retro: <short reusable lesson>" \
  --body "<symptom, cause, durable fix or boundary, and verification>" \
  --scope "$(pwd -P)" \
  --tags retro,lesson,<failure-or-fix-up> \
  --provenance-type source_backed_agent_run \
  --provenance "retro review of <session/task>; evidence: <why this is durable>" \
  --evidence-path "<exact transcript, test, receipt, or source path>" \
  --confidence medium \
  --status candidate \
  --verify-before-use
```

Use `--status active` only when a concrete source, receipt, or repeated
verified run supports the lesson. Otherwise keep the record
`candidate`/`verify-before-use`; never promote a guess just because it sounds
useful. Omit `--evidence-path` only when the host supplied no path and the
current conversation itself is the complete evidence boundary; say so in the
report.

If an existing lesson recurred or failed to prevent the hurdle, call that out
as a **fix-up** and repair the owning procedure or preference rather than
creating a duplicate record. Do not edit another plugin's source from this
command.

## 4. Report the receipt

Keep the result compact and evidence-linked:

```text
RETRO
target: <scope/session/focus>
evidence: <sources actually inspected>
signals: <retry/unresolved/correction/recurrence counts>
recorded: <record IDs, or "none">
skipped: <count and why>
unclear: <count and missing proof>
next: <one concrete verification or fix-up action>
```

If no hurdle meets the durability bar, report `recorded: none` and
`No reusable lessons; wrote nothing.` That is a valid retrospective. Do not
claim transcript, cache, host, or public-release proof that was not actually
observed.
