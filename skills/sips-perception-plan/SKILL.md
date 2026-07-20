---
name: sips-perception-plan
description: Plan browser, app, screenshot, or UI checks before visual claims. Use when a task includes app shots, visual QA, generated assets, or runtime UI proof.
---

# SIPS Perception Plan

Use `homebase_perception_plan` with the surface, target, and expected visible state. For browser tasks, use Browser or Chrome tooling after the plan when available.

Do not claim a UI state from source alone when the user needs visual/runtime proof. Name the screenshot, route, app window, or pixel/canvas check that supports the claim.

If the user sends an app shot with little context, infer the likely desired triage from visible state, then update the relevant app-shot triage workflow when the lesson is durable.

Treat a plugin or MCP server listed in the app UI as enumeration proof only. Verify configuration separately, and do not claim task-callable exposure until the current task successfully invokes one of its tools; after restart or rediscovery, prefer a fresh-task invocation for that proof.
