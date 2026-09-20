---
name: sips-in-run-improvement
description: Capture and develop a reusable skill, tool repair, or behavior improvement noticed while completing a task. Use when instructions are stale, a recurring workflow deserves a skill, or a tool contract fails in practice.
---

# Improve while doing the work

When a concrete bump exposes reusable knowledge, preserve the evidence before
continuing. Prefer completing the user's task; capture a short notice when a separate
improvement would interrupt it. Do not create a skill for generic advice or a one-off
fact. A reproducible failure can justify repair without waiting for recurrence.

Inspect the relevant existing skill or tool first. Choose:
- extend_skill: useful guidance missing from an applicable skill;
- refresh_skill: instructions conflict with verified current behavior;
- create_skill: a reusable workflow has no suitable home;
- repair_tool: executable behavior or an interface is wrong;
- create_tool or compose_tools: a demonstrated capability gap;
- update_behavior: an existing local behavioral instruction needs a scoped correction.

Use adaptation action `notice` with kind, path, title, rationale, evidence_indices,
and acceptance. Evidence indices refer to the current episode's recorded evidence.
Include expected behavior, a relevant consumer regression and a counterexample in
the acceptance requirements. Record the corrected command or observed result, not
only your explanation. Example: a skill selects the wrong interpreter; retain the
failed invocation and a successful comparison using the verified interpreter.

Read `opportunities` to inspect notices and source freshness. A notice is an
agent-authored hypothesis, not approval or verified effectiveness. Its observation
template starts a separate episode scoped to the target. Freeze an executable suite,
build isolation, edit the candidate, evaluate and inspect its diff. Requirements in a
notice do not replace evaluator checks. Adding a source file requires explicit scope
in that episode; capturing a notice never expands the current candidate's scope.

For skills, test applicability and wrong-trigger cases as well as the instructions'
commands. Markdown substring tests establish wording only, not behavioral transfer.
For tools, retain contract, dependency, original failure and consumer checks.
New guidance remains a reviewed candidate until exact-candidate activation is requested.
Use verified task-local findings immediately where appropriate, while keeping shared
skill installation and the current task's loaded skill version distinct.
