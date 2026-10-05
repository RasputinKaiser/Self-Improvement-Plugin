# Contributing

Thanks for taking a look at Self-Improvement-Plugin.

This project is a local-first harness plugin for Claude Code and Codex for agent memory, verification, self-correction, delegation, and eval workflows. Contributions are welcome, but changes should stay focused on the harness loop.

## Good contribution areas

- Hook reliability
- Memory Fabric recall and record quality
- Test coverage for harness scripts
- Eval case quality
- Safer escalation and fan-out behavior
- Documentation fixes
- Install and verification cleanup

## Source checkout

Use Python 3.10 or newer. From the repository root, isolate development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install ".[dev]"
```

This installs the pytest development extra; it does not install the plugin in
Claude Code or Codex. Host installation is described in [the README](README.md#install).
For diagnostics and state-path caveats, see [troubleshooting](docs/troubleshooting.md).

## Before opening a pull request

1. Keep the change scoped.
2. Avoid committing local transcripts, private repo paths, API keys, screenshots with private data, or generated local harness state.
3. Run the validation script:

```bash
python3 scripts/validate_v2.py --check-eval
```

4. Run the regression harness:

```bash
python3 scripts/run_tests.py
```

5. Run the repo-local pytest bridge suite:

```bash
python3 -m pip install ".[dev]"
pytest
```

6. Mention what changed, why it changed, and how you tested it.

## Match the CI coverage

The [CI workflow](.github/workflows/ci.yml) runs these additional checks and targeted
suites before the complete pytest collection:

```bash
python -m compileall scripts
python -m pip install vermin
vermin --target=3.10- --no-tips scripts
python scripts/run_tests.py memory_fabric --verbose
python scripts/run_tests.py phase0_foundation --verbose
python scripts/run_tests.py hook_contract --verbose
python scripts/run_tests.py homebase_mcp --verbose
```

CI covers Python 3.10 and 3.12 on Ubuntu and macOS. A local run covers only your
current interpreter and OS. `--check-eval` reads the generated evaluation contract;
`--write-eval` explicitly rewrites `EVAL.md`. Do not regenerate it merely to hide
a failing check. Documentation-only changes should also resolve their relative
links and check command names against the scripts. State clearly which tests ran,
which failed, and which were not run.

## Pull request style

A good PR includes:

- a short summary
- the reason for the change
- test output or manual verification notes
- any known tradeoffs

For larger changes, open an issue first so the design can be discussed before code is written.

## Local data warning

This project touches local harness state. Do not include personal local harness state, private Memory Fabric records, private agent transcripts, or local machine paths unless they are already sanitized.

