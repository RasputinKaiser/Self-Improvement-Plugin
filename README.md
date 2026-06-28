# harness-self-improvement

A self-improving agent harness plugin for NCode (Claude Code fork). Provides
hooks across the full agent lifecycle so each task starts informed by prior
work and each session closes with recorded learnings.

## What's included

22 Python scripts and 1 shell wrapper covering:

- **PreToolUse**: autonomy gate (blocks critical paths), Memory Fabric preflight (surfaces prior learnings)
- **PostToolUse**: script syntax smoke test, coverage tips
- **SessionStart**: drift check, Memory Fabric doctor + recent work, proactive drift, agent patterns brief
- **UserPromptSubmit**: Memory Fabric prompt-time search
- **PreCompact**: thread-brief injection, continuity packet write
- **PostCompact**: session record, continuity restore
- **Stop**: session close, task outcome metrics

Plus on-demand utilities: validator, GC, tool factory, repo forensics, snapshot/restore, self-correct, run_tests (38 regression cases).

## Installation

```bash
/plugin marketplace add RasputinKaiser/harness-self-improvement
```

Then install `harness-self-improvement@harness-local` from the marketplace UI.

## Requirements

- Python 3.8+
- Codex Memory Fabric plugin installed (for Memory Fabric features)
- CSI Host Surface Audit plugin (optional, for `harness_gc.py --deep`)

## License

MIT — see LICENSE.
