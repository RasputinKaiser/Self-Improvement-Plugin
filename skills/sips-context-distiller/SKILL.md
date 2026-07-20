---
name: sips-context-distiller
description: Extract bounded, source-linked context from large files or many inputs. Use when context is too large, files are oversized, or a task needs concise excerpts.
---

# SIPS Context Distiller

Use `homebase_context_scan` to find context-drain risks and `homebase_distill_context` to extract bounded excerpts from the relevant files.

Keep excerpts source-linked with paths and line references where possible. Mark omissions explicitly; a distilled packet is working context, not full-file proof.

If exact behavior matters, follow the distilled packet by reading the precise source lines before editing or making a final claim.
