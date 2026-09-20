# Improving skills and tools during a run

Use the `sips-in-run-improvement` skill when task evidence reveals reusable guidance,
a stale instruction, or a reproducible tool defect. Capture first, then choose
whether to develop a separate candidate now or return to it after the main task.

The controller's `notice` action uses the same revision, event, locking and
idempotency machinery as other adaptation actions. It records a bounded target,
reason, acceptance requirements, evidence identities, and source identity. It
neither edits the target nor changes the active episode's allowed files.

```json
{
  "episode":"<episode>", "expected_revision":3, "idempotency_key":"interpreter-notice",
  "kind":"refresh_skill", "path":"skills/example/SKILL.md",
  "title":"Correct the interpreter used by the documented command",
  "rationale":"Recorded invocation fails under the documented interpreter; the verified interpreter succeeds",
  "evidence_indices":[0,1],
  "acceptance":["Replay the original command successfully", "Retain documented consumer behavior", "Reject the unsupported interpreter explicitly"]
}
```

Supported kinds: create_skill, extend_skill, refresh_skill, create_tool, repair_tool,
compose_tools, update_behavior. A refresh/extension/repair needs an existing target;
a creation must not overwrite one. Skill targets use `skills/name/SKILL.md` inside
the episode workspace. To improve a different plugin, open a scoped episode rooted
at its source workspace. Cache paths are installations, not preferred authoring roots.

Read `opportunities` via CLI or MCP. It returns proposed or stale notices and an
observation template. Supply a frozen executable suite and explicit supporting
context to turn the template into a new episode. Its acceptance text is a requirement,
not a successful check. Identical notices deduplicate; the default hard limit is
64 notices per episode. Evidence references identify observed records but do not
prove the agent's interpretation of them.

`next` packets expose the capture action so the active task agent can notice a
reusable improvement without losing its current work. No scheduled scanner, hidden
model call, or global instruction writer is installed. Verified task-local corrections
can guide the current task immediately; shared skill/tool candidates follow independent
evaluation and exact-candidate activation. Capture remains useful even when the
correct outcome is to defer an improvement or decide that no new skill is warranted.

The skill itself is included in the authorized SIPS source update. Subsequent generated
skill candidates remain reviewable proposals. Markdown shape validation is distinct
from behavioral validation; use trigger/counter-trigger cases and real consumer commands.
