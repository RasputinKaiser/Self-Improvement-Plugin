---
name: sips-memory-fabric
description: Search, inspect, and record SIPS-owned Memory Fabric lessons. Use when a task needs prior lessons, recurring-fix memory, recall health, scoped historical context, or when a just-fixed bump or error should be recorded.
---

# SIPS Memory Fabric

Use `homebase_recall` with the user's query and current repo root. Treat Memory Fabric as a SIPS-owned subsystem for recall, lesson capture, memory health, and future tooling.

Do not present recall as current proof. If a memory-derived fact is likely to drift, verify it with local files or runtime checks before using it as evidence.

When recall finds a relevant fix, cite the remembered boundary in the final answer and run the live command that proves the current repo still matches it.

After fixing any bump (failed command, wrong path, retry chain), record it immediately: run `python3 scripts/memory_fabric_cli.py record` from the SIPS plugin root with the symptom, the working fix, and repo scope (or `memory_fabric_record` on the codex-memory-fabric MCP when that host exposes it), then confirm it surfaces via `homebase_recall`. Unrecorded fixes recur across sessions.
