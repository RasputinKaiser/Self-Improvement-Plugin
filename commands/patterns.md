---
description: Show the full agent_patterns report — success rate, approach→outcome correlation, top patterns.
---
Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/agent_patterns.py` (full report, not
--brief) and present it to the user verbatim with light formatting.

Then add a one-line interpretation:
- If success rate < 70% → "success rate is low; consider `/improve` to attack the
  top failure topic."
- If an approach→outcome correlation shows a bucket with >=80% success and >=3
  samples → "approach `<metric>=<bucket>` correlates with success — lean into it."
- If no outcomes recorded → "no outcomes yet; complete tasks with the Stop hook
  active to populate metrics."

Do not edit anything. This is a read-only dashboard.
