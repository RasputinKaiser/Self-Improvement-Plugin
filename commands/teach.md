---
description: Hand-record a lesson into Memory Fabric (learning tier, high confidence) so it is recalled later.
---
Argument: $ARGUMENTS — the lesson text.

Record a deliberate, hand-written lesson (as opposed to one auto-captured from a
transcript). These are the highest-signal records because a human/agent chose to
write them down.

Write it scoped to the current working directory:
`python3 <mf_cli> record --tier learning --title "taught lesson: <short topic>" \
   --body "$ARGUMENTS" --tags lesson,taught,manual --scope "$CWD" \
   --provenance-type source_backed_agent_run --confidence high --status active`

(The memory_fabric CLI path is resolved the same way the other scripts resolve
it — see `scripts/memory_fabric_preflight.py` for the lookup.)

Confirm with: `RECORDED: <record_id>` and remind that it will surface via
`memory_fabric_preflight` the next time the touched scope is edited.
