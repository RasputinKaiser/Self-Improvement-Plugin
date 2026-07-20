---
name: brainstorm
description: Survey current capabilities, identify gaps, dispatch the escalate agent to draft a concrete build plan for the top gap. Proactive — the complement to /improve (which is reactive).
---

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brainstorm.py --json` to survey current capabilities and identify gaps. The script returns a JSON array of 3-5 ranked proposals, each with: name, description, effort estimate, leverage score, and capability_area.

Read the result. Then **dispatch the `escalate` agent** to draft a full build plan for the highest-leverage gap (the top entry). Give the escalate agent:

- The gap name and description
- The current capability map (from `references/capability_map.md` in this plugin)
- Instruction to produce: a phased plan with concrete file paths, new types/modules, UX patterns to borrow from Codex App / Claude Code, test strategy, and risk/rollback notes
- Constraint: do NOT write any code — produce the plan only. The user will review and decide whether to implement.

Present the user with:

1. **Ranked gap list** (3-5 items with effort + leverage scores)
2. **The escalated plan** for the top gap (full architecture, phased build order)

Append a one-line summary to `~/.ncode/improvements.md` under `## /brainstorm sweep — <ts>` noting what the top gap was and whether the escalate agent produced a plan.

Do not edit `${CLAUDE_PLUGIN_ROOT}/scripts/*` or the SIPS plugin source beyond the journal append. If the escalate agent suggests code changes, surface them as proposals only - the user explicitly reviews before any implementation.
