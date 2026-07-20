---
name: sips-delegation-router
description: Route a task through SIPS commands, agents, scripts, MCP tools, or bounded delegation. Use when asked to route, split, fan out, escalate, or choose the right SIPS path.
---

# SIPS Delegation Router

Use `homebase_route` with the user's task, harness, and desired mode. Prefer read-only routing when the user is asking where work should go; switch to edit mode only when they asked for implementation.

For fresh-context work, map the route to existing SIPS agents or commands rather than inventing a new lane. Use `homebase_routes` when you need the available command, agent, script, and MCP equivalents.

Keep the parent task's proof boundary visible: say what was delegated, what remains in the parent context, and which verification command closes the loop.
