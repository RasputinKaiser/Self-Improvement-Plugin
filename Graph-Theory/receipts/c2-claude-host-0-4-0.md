# C2 receipt — Claude Code host moved to 0.4.0

- Captured at: `2026-07-19T23:50:00Z`
- Supersedes: `c1-claude-host-refreeze.md` (which installed 0.3.1 from canonical)
- Marketplace source: `~/Code/.worktrees/sips-graph-runtime-v0.4.0`
- Branch: `codex/sips-graph-runtime-v0.4.0`

## What changed

C1 installed 0.3.1 from the canonical checkout because that was the chosen
source. This moves the Claude Code host onto the 0.4.0 graph runtime.

| Change | Where |
|---|---|
| `.claude-plugin/plugin.json` (version 0.4.0) | added to worktree |
| `.claude-plugin/marketplace.json` | added to worktree |
| `.mcp.json` `${PLUGIN_ROOT}` -> `${CLAUDE_PLUGIN_ROOT}` | worktree |
| `skills/sips-selfloop/` (4 files) | ported from canonical |
| `commands/selfloop.md` | ported from canonical |

`sips-selfloop` and `selfloop` existed only in the canonical dirty checkout and
were never carried onto the branch. Without the port, moving to 0.4.0 would have
silently dropped both. Their only script dependency, `scripts/goal_state.py`,
was confirmed present in 0.4.0 before the port.

## The same `.mcp.json` class of bug, second instance

C1 fixed `"./scripts/…"` + `cwd: "."` in canonical. The worktree carried a
different but equally broken form, `${PLUGIN_ROOT}/scripts/…`, which Claude Code
does not expand — it sets `CLAUDE_PLUGIN_ROOT`. Both are now
`${CLAUDE_PLUGIN_ROOT}`, which the Codex installer also substitutes
(`scripts/memory_fabric_install_mcp.py:46-47`).

## Verification

```
claude plugin list      harness-self-improvement@sips-local  0.4.0  user  enabled
claude plugin details   21 skills, 5 agents, 7 hook events, 1 MCP server
claude mcp list         plugin:…:sips-homebase  ✔ Connected   (from neutral cwd)
```

Skill count held at 21 across the 0.3.1 -> 0.4.0 move, confirming the selfloop
port landed. The cache copy at
`~/.claude/plugins/cache/sips-local/harness-self-improvement/0.4.0` contains 19
`scripts/sips_runtime/` modules, and its `.mcp.json` is byte-identical to the
source.

## Resolved from C1

C1 recorded `cache_source_parity: not_proven` — the 0.3.1 cache held a pre-fix
`.mcp.json` because `claude plugin update` no-ops when the version is unchanged.
The 0.4.0 version bump forced a fresh copy, and parity now verifies. The
underlying gotcha stands: **edits to the source will not refresh the cache
without a version bump.**

## Explicit non-claims

- Skill, agent, and hook *execution* under Claude Code is still untested. Only
  discovery and MCP connectivity were verified.
- `default_mode` remains `legacy`; `dual` and `runtime` stay fail-closed. The
  graph runtime is installed, not active.
- The marketplace points at a git worktree. If that worktree is pruned or moved,
  the marketplace source breaks. A merge to canonical would remove this
  dependency.
- Cowork plugin state unchanged; it is managed through Settings -> Capabilities.
- The canonical checkout keeps the C1 digests and still carries 0.3.1 plus its
  `.claude-plugin/` manifests.
