# Contributing

Thanks for taking a look at Self-Improvement-Plugin.

This project is a local-first NCode harness plugin for agent memory, verification, self-correction, delegation, and eval workflows. Contributions are welcome, but changes should stay focused on the harness loop.

## Good contribution areas

- Hook reliability
- Memory Fabric recall and record quality
- Test coverage for harness scripts
- Eval case quality
- Safer escalation and fan-out behavior
- Documentation fixes
- Install and verification cleanup

## Before opening a pull request

1. Keep the change scoped.
2. Avoid committing local transcripts, private repo paths, API keys, screenshots with private data, or generated `.ncode` state.
3. Run the validation script:

```bash
python3 scripts/validate_v2.py
```

4. Run the regression harness:

```bash
python3 scripts/run_tests.py
```

5. Mention what changed, why it changed, and how you tested it.

## Pull request style

A good PR includes:

- a short summary
- the reason for the change
- test output or manual verification notes
- any known tradeoffs

For larger changes, open an issue first so the design can be discussed before code is written.

## Local data warning

This project touches local harness state. Do not include personal `.ncode` data, private Memory Fabric records, private agent transcripts, or local machine paths unless they are already sanitized.
