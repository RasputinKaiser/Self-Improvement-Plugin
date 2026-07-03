# SIPS Improvement Ledger

## 2026-07-03 - 0.2.2

- Added `.agents/plugins/marketplace.json` so the SIPS repo is a supported Codex marketplace root, not only an NCode marketplace/plugin source.
- Bumped Codex/NCode plugin versions to 0.2.2 for the marketplace packaging change.

Score: 96 -> 98. Context delta: 0 skill-description chars, 0 SKILL.md body words.

## 2026-07-03 - 0.2.1

- Updated the Codex plugin interface with a shorter display subtitle plus `composerIcon` and `logo` assets so the local plugin renders with a real SIPS identity in Codex.
- Changed `hooks/hooks.json` command roots from `${CLAUDE_PLUGIN_ROOT}` to `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`, preserving legacy host behavior while making SIPS plugin-root resolution Codex-first.
- Updated `validate_v2.py` to require the portable hook-root syntax and to track the 0.2.1 manifest/marketplace version.

Score: 91 -> 96. Context delta: 0 skill-description chars, 0 SKILL.md body words.

Deliberately not done: no new skills were added because SIPS is currently an MCP/homebase plugin and the pass target was package quality, not a new invocation surface.
