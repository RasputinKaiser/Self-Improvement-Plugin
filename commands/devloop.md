---
description: Development feels slow or the AI keeps picking soft, safe choices. Measure the dev loop, name the hard hit, land it.
argument-hint: "[focus: build|test|verify|agents|ambition|all] [--audit-only]"
---
The user says development feels slow, and that the agents (you, subagents, Codex workers) sometimes choose
soft options when a harder, higher-leverage move is available. Your job: find where the dev loop loses time,
find where the work has gone soft, and land the hardest change the evidence supports. Focus: `$ARGUMENTS`
(default `all`; `--audit-only` = steps 1–4, no edits).

## 1. Measure the loop (numbers, this machine, now)
Time one real cycle of: edit → build → fast check → full verify → see the result (screenshot, test output, metric).
Use the project's own scripts; `/optimize` probes in `.optimize/` if they exist. Record per stage: wall time, how often
it runs per change, and what blocks (locks, queues, shared servers, rebuilds of unchanged parts, cold starts).
Also measure agent throughput if workers run: rounds per hour, share of rounds that landed a kept change,
share that ended in "no change", a question, a revert, or a crash.

## 2. Audit for soft choices
Read the last few rounds of work (worker final reports, `git log`, ledgers, your own recent turns). Flag each:
- **Micro-wins**: changes worth < 2–3 % on the target metric, or inside measurement noise, presented as progress.
- **Symptom patches**: a special case, retry, timeout bump, flag or "warn instead of fail" where a root cause exists.
- **Retreats**: reverting, deferring or "recording for the owner" a fix that was in reach and in scope.
- **Re-measuring**: rounds spent re-collecting evidence that already settled the question.
- **Busy work**: reports, tables, provenance prose with no change behind them.
- **Scope shrink**: the goal quietly redefined smaller ("passes the gate" instead of "is fast/correct/good").
For each, write the hard alternative: the structural change that would move the metric by a large factor
(rewrite the hot path, change the data layout, remove the stage, make the slow thing not run at all, pick a
better architecture, cache across runs, parallelise independent work).

## 3. Rank
One table: bottleneck or soft choice | evidence (number) | hard hit | expected gain | risk | effort.
Rank by expected gain × confidence. Prefer a change that removes a whole stage or a whole class of waits over
one that shaves a stage. A hard hit must be safe: behaviour-preserving (tests, replays, digests) or explicitly
approved by the user if it changes behaviour.

## 4. Decide out loud
State the top hard hit in two lines: what changes, what number it should move, how you'll prove it.
Name any soft choice you are deliberately NOT fixing and why (one line each). Do not ask "should I?" for
routine, reversible work; ask only for destructive, shared or outward-facing actions (CLAUDE.md rules apply).

## 5. Land it
- Snapshot first (`/checkpoint`) when touching shared tooling.
- Implement the top item fully. No half-landed migrations, no "phase 1 of 3" unless the user asked.
- Re-measure the same stage with the same probe; report before → after.
- If workers/agents produced the soft choices, fix the cause in their briefs or prompts: put the hard target at
  the top as a number, forbid the specific soft pattern you found, and give the structural direction.
- If a dev-loop tool is missing (fast subset runner, warm server, fixture, cached build, one-shot capture), build it
  (`/sips-tool-factory` or a project script) and register it where agents will find it.

## 6. Record
Append to `.optimize/ledger.md` (create if missing): date, focus, measured loop before/after, soft choices found,
hard hit landed, what is next. Record the durable lesson with `/teach` (or Memory Fabric) so the next session
starts from it. Report to the user in a short table: loop time before/after, what was soft, what was done.
