---
name: sips-control-plane
description: Inspect SIPS Homebase status, manifest wiring, routes, host visibility, and MCP freshness. Use when asked for SIPS status, command center, host audit, plugin visibility, or whether Homebase is fresh.
---

# SIPS Control Plane

Use the `sips-homebase` MCP first: call `homebase_status` for the status card, `homebase_routes` for route inventory, `homebase_host_audit` for Codex wiring, and `homebase_mcp_freshness` before claiming the live host is fresh.

Report the proof boundary explicitly: source/cache/config/child-process freshness is not the same as an already-open Codex session rediscovering the refreshed plugin.

If the MCP surface is unavailable, inspect `.codex-plugin/plugin.json`, `.mcp.json`, `.agents/plugins/marketplace.json`, `state.yaml`, and `scripts/harness_homebase_mcp.py` directly, then say the MCP path was unavailable.
