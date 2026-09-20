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

## Research methods (0.7)

The read-only `homebase_method` exposes five advisory analyses. Persist a receipt through adaptation action `analyze`; transition authority remains in the controller. See [method API](../../references/research-methods.md) and [command protocol](../../references/command-protocol.md).

## Foreground adaptation (0.8)

Use adaptation read views `next` and `outcomes`, and write actions `advance` and
`link_outcome`. Work packets are revision-bound. Review/stopped packets cannot
advance into activation. See ../../docs/sips-08.md for request contracts.

## Diagnostic branches and validity (0.9)

The adaptation `dependencies` read view explains current drift and its affected
receipts without modifying history. Registered `sips.policy.v2` artifacts can be
tried with `policy_trial` and an explicit `target_episode`; the controller consumes
durable executed probe outcomes and pins their source revision. Missing evidence,
unavailable outcomes, and expired assumptions remain distinct. Freeze `policy_cases`
checks to evaluate behavior independently. Policy trials propose interventions;
normal lifecycle actions and exact-candidate activation remain authoritative.

## In-run improvement capture

Adaptation `notice` records evidence-linked skill/tool opportunities; `opportunities`
reads their source freshness and candidate handoff. `next` exposes the capture cue.
Use `sips-in-run-improvement` for deciding between creation, extension and repair.
See ../../docs/sips-in-run-improvement.md for fields and limits.

## In-stream SIPS visualizations

For episode progress, diagnosis, dependency drift or review explanations, read the
adaptation `visual` view and render its Mermaid diagram in the response. Use compact
charts for experiment comparisons, showing missing results as unknown and keeping
synthetic, foreground and production evidence distinct. Link to underlying receipts.
Do not substitute a chart for failures or limitations, or claim that returning HTML
or Mermaid source proves the host displayed it. The existing HTML widget renderer
uses a host-specific preview directive; use ordinary Mermaid or local image embeds
when that host integration is unavailable.
