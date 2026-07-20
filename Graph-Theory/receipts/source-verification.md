# SIPS 0.4.0 source verification receipt

- Captured at: `2026-07-19T01:48:06Z`
- Feature worktree: `~/Code/.worktrees/sips-graph-runtime-v0.4.0`
- Feature branch: `codex/sips-graph-runtime-v0.4.0`
- Base HEAD: `bde0ca863781d22822a0239cefec434e9580fed9`
- Proof layer: source worktree only

## Passing checks

| Check | Result |
|---|---:|
| `python3 -m pytest -q` | 72/72 passed |
| `python3 scripts/run_tests.py fan_out --verbose` | 4/4 passed |
| `python3 scripts/run_tests.py homebase_mcp --verbose` | 2/2 passed |
| `python3 scripts/memory_fabric_benchmark.py --output <temp>` | 77/77 passed |
| `python3 scripts/validate_v2.py --check-eval` | 134/134 passed |
| `python3 -m compileall -q scripts tests` | passed |
| plugin-creator `validate_plugin.py .` | passed |
| `git diff --check` | passed |

The 77-case benchmark receipt used for this check had SHA-256 `b4eb535da092a08d80114c8d9d57511073ba38d4c3203543c478cbeb8ecebd89`. It reported `ok=true`, 107 records written, and zero failed scenarios.

## Frozen checkout comparison

The original dirty checkout `~/Code/Self-Improvement-Plugin` still matches the C0 preservation boundary:

| Surface | C0 digest/current value | Recheck |
|---|---|---:|
| HEAD | `bde0ca863781d22822a0239cefec434e9580fed9` | identical |
| tracked binary diff | `f26668f88c82cc5755b14d6c0c5ec4d98bf6e908a2898e2fa3f2e2e7a2dba1e5` | identical |
| porcelain-v2 state | `76b2b94e0c33ef1abae368468c760196f948b8722a2a8fdf579ffba3391664ad` | identical |
| untracked manifest | `752ec714b753fecbe2c646433c003630333d57378e5a0b276f313e2172fdf7e0` | identical |
| `state.yaml` | `beeb91f6b89aa0a00efac809134cbf491eeeb7edcc9c33b8078af237ba588251` | identical |
| modified tracked entries | 45 | identical |
| untracked entries | 18 | identical |

The comparison used `git diff --binary`, NUL-delimited `git status --porcelain=v2`, and NUL-delimited `git ls-files --others --exclude-standard`, matching the C0 capture procedure.

## Inline visualization

The repaired workspace and inline-cache copies of `sips-graph-runtime.html` are byte-identical with SHA-256 `97bf65e71beb95ca3b9e0d7ac9cc0c6e11d7560234f909608d23fa1a783887e6`. The inline JavaScript passes `node --check`, and static assertions confirm separate task-control and memory-context domains, a context-only memory bridge, candidate-only lesson flow, and the explicit invariant that memory edges never unlock tasks.

The in-app browser kept the existing visualization tab open but refused DOM inspection of the local `file://` URL under its URL policy. This receipt therefore does not claim browser-rendered or interactive visual proof.

## Explicit non-claims and blockers

- The plugin cache was not updated or compared; installed-cache parity is not proven.
- Host configuration was not changed; child-process or fresh-host MCP discovery is not proven.
- `legacy` remains the default. `shadow` is read-only.
- Controller-authoritative `dual` and `runtime` execution remain fail-closed until legacy results carry the runtime lease, fencing, structured evidence, and resource contracts.
- Clean integration, production-equivalent parity, rollback rehearsal, active cutover, and public release are not claimed.
- Python wheel installation is not a release surface in this proof; `pyproject.toml` does not package the runtime modules.

These are independent cutover gates, not failures of the verified source test layer.
