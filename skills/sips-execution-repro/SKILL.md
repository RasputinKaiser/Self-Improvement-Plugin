---
name: sips-execution-repro
description: Turn failures, logs, symptoms, or flaky behavior into a compact repro and verification plan. Use when debugging needs a reproducible failure path.
---

# SIPS Execution Repro

Use `homebase_execution_repro` with the goal, symptoms, logs, and failing tests the user supplied or you observed.

Separate observed evidence from hypotheses. Prefer the smallest command or UI path that reproduces the failure, then name the exact verification command that should turn green after the fix.

If no repro is available yet, report that clearly and give the next observation needed rather than treating a hypothesis as confirmed.

## Research methods (0.7)

Use `diagnosis` to expose unresolved hypothesis pairs before executing probes. A coverage design still needs an oracle; unavailable results never discriminate hypotheses. See [method API](../../references/research-methods.md) and [command protocol](../../references/command-protocol.md).
