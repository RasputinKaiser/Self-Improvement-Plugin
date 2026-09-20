---
description: Report observed outcomes, missing data, and possible drift without causal promotion.
---
Follow `references/command-protocol.md`.

Run `python3 <plugin-root>/scripts/agent_patterns.py --json`. Report the denominator,
unknown/conflicting outcomes, and missing metric fields alongside observed rates.
A small successful bucket is a hypothesis for a matched comparison, not a policy
recommendation. Edit counts, fewer tool calls, and absent errors are not acceptance.

For comparable chronological measurements, method `drift` accepts a frozen stable
baseline, explicit measurement identity, and numeric or missing observations.
Its EWMA signal suggests investigation; it identifies neither cause nor a win.
Do not pool different task families, environments, or evaluators into one chart.
No baseline, changed identity, or zero variance means no usable control chart.
Keep this command read-only and return an evidence-gathering next step.
