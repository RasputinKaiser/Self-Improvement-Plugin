---
name: sips-proof-scanner
description: Verify SIPS proof surfaces before reporting completion. Use when asked to scan, verify, validate, prove, audit, or check whether a repo or SIPS install is coherent.
---

# SIPS Proof Scanner

Use `homebase_verify` for manifest and optional suite checks. Pair it with `homebase_repo_map` when the requested proof depends on touched files, likely tests, or write scope.

For the SIPS repo itself, prefer the existing proof stack: `python3 scripts/validate_v2.py --check-eval`, `python3 scripts/run_tests.py homebase_mcp --verbose`, `python3 -m pytest tests/test_homebase_mcp.py`, and plugin validation.

Do not summarize failures away. Report failing command output and stop short of "done" until the specific proof surface passes or the user accepts the remaining gap.
