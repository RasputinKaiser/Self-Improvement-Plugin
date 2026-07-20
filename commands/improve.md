---
description: Run a self-correction sweep and act on the top recommendation. Closes the loop on demand.
---
Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_correct.py --json` and read the
result. Then act on the highest-priority finding:

1. If `untested_scripts` is non-empty → dispatch the `test-author` agent for the
   first entry. Wait for it, then re-run `/verify`.
2. Else if `failure_patterns` is non-empty → pick the top failure topic, search
   Memory Fabric for the most recent success on that scope (`/recall <topic>`),
   and propose a concrete fix. Do not apply it without snapshotting first
   (`/checkpoint`).
3. Else if `stale_scripts` is non-empty → summarize them; suggest archiving.

Finish by appending a one-line summary to ~/.ncode/improvements.md under a new
`## /improve sweep — <ts>` heading. Do not edit `${CLAUDE_PLUGIN_ROOT}/scripts/*` without a
snapshot — the autonomy gate will remind you, but snapshot proactively.
