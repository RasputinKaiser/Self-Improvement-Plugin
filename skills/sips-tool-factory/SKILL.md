---
name: sips-tool-factory
description: Decide whether to reuse, improve, or scaffold a deterministic helper. Use when repeated work is slow, brittle, or blocked by a missing local tool.
---

# SIPS Tool Factory

Use `homebase_tool_factory` with the task, desired helper, and any existing script. Prefer improving a nearby working helper over creating a new one.

Create a tool only when it removes repeated manual work or closes a real capability gap. Keep it repo-local, deterministic, and covered by a small smoke or regression check.

After the helper works, record the command and proof path in `state.yaml`, `LEDGER.md`, or memory when the lesson is durable.

Use `available_types` and `required_types` when the task has known artifact contracts. Treat a composition as a proposal requiring consumer checks; `insufficient_fit` calls for more evidence or an explicit creation decision.

Scaffolding creates a draft `.contract.json`. Implement the helper and populate its inputs, outputs, prerequisites, effects, failure semantics, resources, and behavioral cases before setting status to `implemented`. `validate` executes those cases and records exact artifact identities; help output and test-name mentions are insufficient. `promote` packages the validated version and pins the skill entrypoint. Host discovery remains a separate check.

For corrections, preserve the original acceptance criterion and connect diagnosis, candidate, and frozen evaluation in an `adaptation.py` episode. Passing evaluation stops at `ready_for_review`. Activate only on an explicit request naming the reviewed candidate digest. See `docs/sips-05.md` in the plugin source for contracts and commands.

## SIPS 0.6 evidence workflow

Use the shared adaptation controller for structured investigations and bounded probes.
Prefer current v2 contracts and joint-prerequisite composition before new helpers.
Use additive counterexamples; preserve raw episodes when proposing procedures.
Policy trials are declarative proposals, never changes to evaluation or activation.
See `docs/sips-06.md` for request shapes, supported schemas, and research limits.

## Research methods (0.7)

Use `coverage` to propose consumer interaction cases and `morphology` to explore repair/reuse alternatives. Feasible combinations remain proposals until executable consumer checks pass. See [method API](../../references/research-methods.md) and [command protocol](../../references/command-protocol.md).

## Semantic composition (0.9)

Use contract v3 for explicit semantic roles, units, literal context identities,
and numeric ranges. Missing or incompatible declarations reject a binding; no
implicit conversion is available. Runtime bounds do not prove declared meaning.
Keep independent consumer checks. Inspect adaptation `dependencies` before reuse;
changed evaluator or dependency identities require revalidation. See
`docs/sips-09.md` for the supported vocabulary and limitations.
