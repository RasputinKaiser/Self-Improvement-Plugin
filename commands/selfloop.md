---
description: Run a bounded foreground adaptation cycle and stop at evidence-based review.
---
Follow `references/command-protocol.md`.

Use `goal_state.py selfloop-set <focus>` only for an explicitly requested loop.
`status`, `pause`, `resume`, `complete`, and `clear` retain their documented state
controls. A request for status never starts a cycle. No background scheduler or
automatic child-agent campaign is implied.

For each authorized foreground cycle: inspect `self_correct.py --json` and
reproducible failures; use /checkpoint for recoverable state; create an adaptation
episode; declare competing hypotheses; inspect diagnostic_design for hypotheses
that no proposed probe can separate; gather evidence or propose one intervention.
The active agent authors the isolated candidate and evaluates it against the
frozen original, consumer, and counterexample checks.

Record review-ready, rejected, unavailable, or plateau evidence. Use
`selfloop-record` only with the corresponding supported result; evaluation does
not mean an improvement is deployed. Stop at ready_for_review for generated
changes. Use /teach for a durable candidate lesson, not every iteration.

A plateau means no supported next intervention within the current evidence and
budget; it is not proof that no improvement exists. Keep one candidate at a time
and the episode's persisted limits. Honor pause/stop immediately and report an
external blocker accurately without silently changing user goal controls.

Use adaptation view `next` and action `advance` for the resumable foreground
cycle. Match packet identity and required output exactly. Link later evaluated
uses with `link_outcome`; report unmatched comparisons as unmeasured.
