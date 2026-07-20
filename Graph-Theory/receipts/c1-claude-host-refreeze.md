# C1 re-freeze receipt — Claude Code host enablement

- Captured at: `2026-07-19T23:30:00Z`
- Frozen checkout: `~/Code/Self-Improvement-Plugin`
- HEAD: `bde0ca863781d22822a0239cefec434e9580fed9` (unchanged from C0)
- Reason: the C0 freeze was deliberately broken to add Claude Code host manifests.
  This receipt supersedes the C0 digests in `c0-freeze.md` and the
  "Frozen checkout comparison" table in `source-verification.md`.

## Why the freeze was broken

Claude Code requires a `.claude-plugin/` manifest to install a plugin, and the
repo carried only `.codex-plugin/` and `.ncode-plugin/`. SIPS was therefore not
installed in Claude Code at all — it was never a stale-version problem.

## Exactly what changed

| Change | Kind | Effect on C0 |
|---|---|---|
| `.claude-plugin/plugin.json` | added, untracked | untracked manifest digest |
| `.claude-plugin/marketplace.json` | added, untracked | untracked manifest digest |
| `.mcp.json` | modified, already-dirty tracked file | tracked diff digest |

No pre-existing work was removed or rewritten. The 45 modified tracked entries
from C0 are still 45; untracked entries went from 35 to 37.

## Digest transition

| Surface | C0 | C1 |
|---|---|---|
| HEAD | `bde0ca86…80fed9` | identical |
| tracked binary diff | `f26668f8…dba1e5` | `e921b069…33b9c8` |
| porcelain-v2 state | `76b2b94e…1664ad` | `34ee2916…e1ccd0` |
| untracked manifest | `752ec714…2fdf7e0` | `52771722…709534ba` |
| `state.yaml` | `beeb91f6…588251` | identical (untouched) |

C0 digests were re-verified as intact immediately before the change, so the
transition is from a known-good baseline. Capture procedure matches C0:
`git diff --binary`, NUL-delimited `git status --porcelain=v2`, and
NUL-delimited `git ls-files --others --exclude-standard`.

## The `.mcp.json` fix

C0 shipped a server entry that cannot work under a plugin host:

```json
"args": ["./scripts/harness_homebase_mcp.py"], "cwd": "."
```

A relative path with `cwd: "."` resolves against the *session* working
directory, not the plugin root. Probed directly: with cwd at the plugin root the
server completes an MCP `initialize` handshake; from an unrelated directory it
fails with `can't open file '/private/tmp/…/./scripts/harness_homebase_mcp.py'`.
`claude mcp list` from a neutral cwd confirmed the host-level symptom:

```
plugin:harness-self-improvement:sips-homebase - ✘ Failed to connect
```

Replaced with `${CLAUDE_PLUGIN_ROOT}/scripts/harness_homebase_mcp.py` and no
`cwd`. Re-probed from the same neutral cwd:

```
plugin:harness-self-improvement:sips-homebase - ✔ Connected
```

This token is also safe for the Codex install path, which substitutes both
`${PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_ROOT}` at install time
(`scripts/memory_fabric_install_mcp.py:46-47`).

## Claude Code install state

- Marketplace `sips-local` registered from the repo directory (user settings).
- `harness-self-improvement@sips-local` 0.3.1 installed, user scope, enabled.
- Component inventory resolved: 21 skills, 5 agents, 7 hook events, 1 MCP server.
- Projected always-on cost: ~1,201 tokens per session.

## Explicit non-claims

- `${CLAUDE_PLUGIN_ROOT}` resolved to the **repo directory**, not the plugin
  cache copy at `~/.claude/plugins/cache/sips-local/harness-self-improvement/0.3.1`.
  That cache copy still holds the pre-fix `.mcp.json`; `claude plugin update`
  no-ops because the version did not change. Cache-vs-source parity is therefore
  NOT proven, and edits to the repo will not refresh the cache without a version
  bump.
- Skill, agent, and hook execution under Claude Code were not exercised — only
  discovery and MCP connectivity were verified.
- This installs 0.3.1 from the canonical repo. The 0.4.0 graph runtime on
  `codex/sips-graph-runtime-v0.4.0` is NOT part of this install.
- Cowork plugin state was not changed; Cowork plugins are managed through
  Settings → Capabilities and cannot be installed from a session.
