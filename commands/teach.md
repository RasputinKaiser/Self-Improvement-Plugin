---
description: Record a scoped, evidence-linked lesson with explicit applicability and uncertainty.
---
Follow `references/command-protocol.md`.

Classify $ARGUMENTS as a user instruction, observation, hypothesis, or verified
procedure. Manual authorship alone does not imply high confidence. Search for an
existing scoped lesson before adding a duplicate. Retain contradictory evidence.

Use `homebase_record` or `scripts/memory_fabric.py record`. Include a concise
symptom, intervention, outcome, assumptions, invalidation conditions, and exact
evidence reference. Use provenance user_instruction for an actual user decision,
verified_command/source_document only for inspected supporting evidence, and
user_or_agent_observation otherwise. Hypotheses use --confidence unknown,
--status candidate, and --verify-before-use. Record missing evidence explicitly.

A reusable procedure goes through the adaptation artifact workflow with pinned
source episodes and consumer/transfer evaluation. Report the record ID and status;
do not promise that a lesson is effective or will always be retrieved.
