---
description: Retrieve scoped lessons and evaluate their assumptions, conflicts, and applicability.
---
Follow `references/command-protocol.md`.

Run `python3 <plugin-root>/scripts/recall_ranker.py --query "$ARGUMENTS" --json`.
Check scope, relevance, source identity, validity, and negative applicability.
Rank relevant failures and their verified corrections; unrelated failures do not
outrank an applicable lesson simply because they have a failure tag.

For a chain of conditional lessons, use method `assumptions`: identify premises,
evidence references, positive and negative support, and derivation rules. An
unsupported cycle establishes nothing. Recompute after withdrawing a premise.
An inconsistent premise can support competing conclusions; disclose that conflict.
This method does not verify cited sources or implement a complete ATMS.

Show why a lesson applies, what would invalidate it, and any missing verification.
Separate user instructions from empirical claims. Return no match when appropriate.
