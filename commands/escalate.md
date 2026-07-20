---
description: Force-route the next bounded step to the frontier (claude-opus) escalation agent.
---
Argument: $ARGUMENTS — the bounded subtask to escalate.

Dispatch the `escalate` agent with this single, well-scoped task:
"$ARGUMENTS"

Before dispatching, confirm the task is genuinely bounded (one decision or one
localized fix). If it is broad, decompose it first and escalate only the slice
the main session is stuck on — escalation is a scalpel, not a session
swap.

When the agent returns its `DIFF:` and `LESSON:` blocks:
1. Apply the diff (the autonomy gate will snapshot first if it touches ~/.ncode/).
2. Record the LESSON to Memory Fabric scoped to the touched file:
   `python3 <mf_cli> record --tier learning --title "escalation lesson: <topic>" \
      --body "$LESSON" --tags lesson,escalation,frontier --scope <touched_file>`
   so the workhorse recalls it next time and solves this class itself.
3. Run `/verify`.
