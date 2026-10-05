# SIPS troubleshooting

Start with the [installation steps](../README.md#install) and the
[first-session checks](../README.md#first-session-checks). Diagnose source wiring,
installed bytes, and live host discovery separately.

## Plugin or Homebase tools are missing

1. Check the selected marketplace and plugin identifier. Claude Code's repository
   marketplace is `sips-local`; Codex's is `harness-local`. The plugin name is
   `harness-self-improvement` on both.
2. Confirm the checkout includes the host manifest, `skills/`, and `.mcp.json`.
   The [Codex manifest](../.codex-plugin/plugin.json) points to the shared skills
   and MCP configuration. [The MCP configuration](../.mcp.json) starts
   `scripts/harness_homebase_mcp.py` with `python3`.
3. Restart or reload the host after installation or refresh. If the host supports
   deferred tool discovery, search for the exact Homebase capability before
   concluding that it is unavailable.
4. Use the `sips-control-plane` skill to inspect status, routes, host wiring, and
   MCP freshness. Record which tools were actually callable in that host session.

A direct source subprocess or fresh installed subprocess can verify its own MCP
transport. It does not prove native tools were advertised to an already-open
session. See [the control-plane skill](../skills/sips-control-plane/SKILL.md)
for these evidence boundaries.

## Source checks fail

From a complete repository checkout, use Python 3.10 or newer and run:

```bash
python3 --version
python3 scripts/validate_v2.py --check-eval
```

Inspect the error rather than changing a manifest version or deleting a reference
to make it pass. `--check-eval` fails when committed `EVAL.md` differs from the
generated contract. `--write-eval` is a deliberate file rewrite, useful only after
you understand and review the underlying change. [EVAL.md](../EVAL.md) records
manifest coherence, not a substitute for runtime tests or host integration.

For pytest setup and CI-equivalent suites, see [Contributing](../CONTRIBUTING.md).
A partial download missing scripts or assets is not a valid full-suite checkout.

## Hooks appear silent or use unexpected state

The [hook definitions](../hooks/hooks.json) are the source of truth for event
names and matchers. A defined hook still needs host support and registration;
manifest validation alone does not establish that a live host invoked it.

The event tap is silent by default. When investigating a reproducible issue,
`SIPS_DEBUG=1` enables failure details in `logs/hook_errors.jsonl` under the SIPS
state home. Review and sanitize those logs before sharing them.

[State resolution](../scripts/sips_paths.py) uses `SIPS_HOME` first, then
`~/.codex/sips`. Plugin-root resolution is separate and checks `SIPS_PLUGIN_ROOT`,
`CLAUDE_PLUGIN_ROOT`, then `PLUGIN_ROOT` before falling back to the checkout.
Inspect these environment variables if a command reads a different tree than you
expected. Retired `.ncode` directories are not current runtime fallbacks.

## Local staging or refresh fails

The [`install.sh`](../install.sh) wrapper calls
[`local_release.py`](../scripts/local_release.py). `--stage DIR` requires a new
directory; it refuses to overwrite an existing stage. Choose a new stage path
rather than deleting an older receipt or recovery backup blindly.

The separate `--install DIR` action requires the Codex CLI, verifies staged
content, changes the plugin cache/configuration, and writes install evidence and
recovery data under the stage. Inspect the reported installation or byte-parity
error before retrying. Even a successful fresh-process probe leaves discovery by
the current desktop task as a separate, unverified condition until tested there.

The staging script includes an explicit list of distribution documents. A new
repository guide is not automatically part of that package; read repository
documentation from the source checkout if it is absent from an installed copy.

## Share a useful bug report

Include the host, OS, Python version, source commit, manifest version, exact
sanitized command, exit status, and shortest reproducible symptom. Distinguish
source checks, installed-cache checks, and live-session checks. Do not publish
private memory records, transcripts, secrets, personal paths, or unreviewed logs.
Use [SECURITY.md](../SECURITY.md) for vulnerability reporting.
