---
description: Tier-aware Memory Fabric search for the current scope. Prints ranked prior lessons.
---
Argument: $ARGUMENTS (optional query; defaults to the current scope/recent objective).

Run the tier-aware recall:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/recall_ranker.py --query "$ARGUMENTS" --json`

Read the result and present it as a ranked list:
- rank, tier, confidence, title, one-line body excerpt.
- If any record is tagged `failure`, surface it FIRST with a `⚠ prior failure`
  marker and the matching last-successful approach beneath it.

Do not act on the recalled lessons automatically — they are advisory. Confirm
relevance to the current task before relying on them. If the active tier is
`workhorse`, you may also spawn a `repo-scout` agent to map where the recalled
file/topic sits in the current repo.
