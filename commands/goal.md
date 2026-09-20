---
description: Track an explicitly requested objective, its evidence obligations, and bounded foreground progress.
---
Follow `references/command-protocol.md`.

Use `goal_state.py set <objective>` for an explicitly requested new goal. Preserve
existing state on status reads. `status`, `board`, `next`, and `progress` inspect;
`pause`, `resume`, `complete`, `clear`, and `increment-turn` retain their documented
semantics. Do not replace an active objective just because a new message steers it.

Model the objective as deliverables plus independent acceptance evidence and
prerequisites. Use add-subtask/complete-subtask/fail-subtask for actual transitions.
Distinguish capability failure from missing information and missing authorization.
A review-ready proposal satisfies a proposal objective; it does not satisfy a
separate deployment objective. Complete only when the requested result is verified.

Use the runtime Goal Board and campaign spine when already attached. Source
receipts, cached projections, and host conversation handles are different evidence.
Attach only handles actually returned by the host. No campaign, child process,
or scheduler is created implicitly. Continue authorized foreground work while
respecting budgets and exact-candidate activation boundaries.
