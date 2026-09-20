---
description: Prepare independent slices with explicit ownership and integration evidence for authorized delegation.
---
Follow `references/command-protocol.md`.

Use parallel work only when the user explicitly requests delegation and the
slices can proceed independently. Map shared inputs, permitted writes, resource
conflicts, integration order, and one owner for shared interfaces. Shared files
or unresolved sequential dependencies call for serial work.

`fan_out.py prepare --parent <objective> --slices <slice...>` creates handoffs;
it does not prove execution or OS isolation. Inspect the returned cwd and scope.
Use current native delegation tools and configured role preflights, with compact
context and explicit allowed_files/verify/stop_if. Preserve others' edits.

Ingest actual SLICE/DIFF/LESSON/BLOCKED responses using the existing ingest action.
Preserve failed, dissenting, and unavailable results. Validate the merged consumer
behavior; individual slice tests cannot establish integration success. Lessons
remain candidates. Attach real returned task handles to an existing campaign via
`sips_campaign_fleet.py attach`; status/list remain read-only inspections.
