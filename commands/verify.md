---
description: Run run_tests.py + script_smoke on touched files. If a coverage gap is found, offer test-author.
---
Verify the harness is still sound after edits:

1. `python3 ~/.ncode/scripts/run_tests.py` (or `${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.py`
   if not installed) — report pass/fail counts.
2. For each file touched in this session, run
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/script_smoke.py` against it.
3. If a test FAILS: do not paper over it. Either the test caught a real regression
   (restore via `/checkpoint`'s snapshot) or the test is stale (flag it, don't
   silently delete it).
4. If `proactive_drift.py` reports an untested script, offer to dispatch the
   `test-author` agent to close the gap.

End with a one-line verdict: `VERIFY: OK (n/n tests, k scripts smoke-clean)` or
`VERIFY: FAIL (details above)`.
