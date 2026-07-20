---
name: sips-tool-factory
description: Decide whether to reuse, improve, or scaffold a deterministic helper. Use when repeated work is slow, brittle, or blocked by a missing local tool.
---

# SIPS Tool Factory

Use `homebase_tool_factory` with the task, desired helper, and any existing script. Prefer improving a nearby working helper over creating a new one.

Create a tool only when it removes repeated manual work or closes a real capability gap. Keep it repo-local, deterministic, and covered by a small smoke or regression check.

After the helper works, record the command and proof path in `state.yaml`, `LEDGER.md`, or memory when the lesson is durable.
