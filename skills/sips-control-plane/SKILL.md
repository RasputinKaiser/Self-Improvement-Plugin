---
name: sips-control-plane
description: Inspect SIPS Homebase status, manifest wiring, routes, host visibility, and MCP freshness. Use when asked for SIPS status, command center, host audit, plugin visibility, or whether Homebase is fresh.
---

# SIPS Control Plane

Use the `sips-homebase` MCP first: call `homebase_status` for the status card, `homebase_routes` for route inventory, `homebase_host_audit` for Codex wiring, and `homebase_mcp_freshness` before claiming the live host is fresh.

Plugin MCP tools may be deferred. If Homebase is absent from the initial tool
list, use `tool_search` where the host exposes it and search for the exact
Homebase capability before falling back. Do not declare the MCP unavailable
until discovery returns no matching SIPS namespace or tool. Preserve the actual
native server/tool event when a discovered call succeeds.

Report the proof boundary explicitly: source/cache/config/child-process freshness is not the same as an already-open Codex session rediscovering the refreshed plugin.

If the MCP surface is unavailable, inspect `.codex-plugin/plugin.json`, `.mcp.json`, `.agents/plugins/marketplace.json`, `state.yaml`, and `scripts/harness_homebase_mcp.py` directly, then say the MCP path was unavailable.

If a diagnostic MCP JSON-RPC request is sent by piping `initialize` and
`tools/call` into `python3 scripts/harness_homebase_mcp.py`, label the result a
**repo-local source subprocess**. Preserve both layers: the inner source-subprocess
`tools/call` succeeded, while native task MCP callability remains unproven.
Report the observed outer host transport conditionally—for example, if the
pipeline was launched through `exec`, say the outer host call was `exec`, not a
native `mcp__sips_homebase__*` call. Do not say that the MCP tool was called
from the task, and do not include it in `task_invoked_tools`. That fallback does
not prove the installed cache, host configuration, task advertisement, native
callability, or persistent host attachment.
