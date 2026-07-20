---
name: sips-repo-map
description: Map repository structure, likely tests, git state, and write scope before edits. Use when asked for repo mapping, blast radius, file inventory, or change planning.
---

# SIPS Repo Map

Use `homebase_repo_map` before touching unfamiliar repos or when the user asks for blast radius. Include any planned write set so the map can reason about scope.

Use the output to choose focused file reads and likely verification commands. Do not use broad recursive reads when `rg --files`, `rg`, and the repo map can narrow the target.

If the worktree is dirty, identify unrelated changes and leave them alone unless they directly affect the requested task.
