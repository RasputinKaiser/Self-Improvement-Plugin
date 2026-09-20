# Local tool creation and correction

The factory supports behavioral contracts, versioned packages, contract-aware candidate selection, and bounded typed composition. Correction episodes use the existing runtime EventStore. These features provide inspectable evidence; they do not establish general improvement without comparative task evaluation.

## Create and validate

```sh
python3 scripts/tool_factory.py scaffold receipt_normalizer --summary 'Normalize local receipts'
```

This creates the helper, documentation, and a draft `.contract.json` under `$SIPS_HOME/scripts` (default `~/.codex/sips/scripts`). The scaffold returns `not_implemented` and exits 2 except for help. Implement the operation, fill the contract, and set status to `implemented`. Existing helpers without contracts remain usable directly, but cannot pass factory promotion based on test-name mentions.

Example contract:

```json
{
  "schema": "sips.tool-contract.v1",
  "status": "implemented",
  "version": "1",
  "description": "Normalize a receipt supplied as a positional argument",
  "inputs": ["receipt.raw.v1"],
  "outputs": ["receipt.normalized.v1"],
  "preconditions": ["local"],
  "effects": ["stdout only"],
  "failure_semantics": "Invalid JSON exits 2",
  "resources": [],
  "cases": [
    {
      "id": "normal",
      "args": ["{\"amount\":2}"],
      "exit": 0,
      "json": {"amount": 2}
    },
    {
      "id": "invalid",
      "args": ["not-json"],
      "exit": 2,
      "stdout": ""
    }
  ]
}
```

Cases assert exact stdout, parsed JSON equality, and/or file contents. Optional `fixtures` maps relative paths to initial text; `files` maps relative paths to expected final text. Each case gets a fresh working directory and SIPS_HOME. Declared resource files are copied into the package. Help-only cases and empty cases cannot satisfy behavioral verification. A default 10-second limit applies per invocation. Contract cases are trusted local specifications; they are not an independent correctness oracle. Include counterexamples and independently chosen cases.

```sh
python3 scripts/tool_factory.py validate receipt_normalizer
python3 scripts/tool_factory.py promote receipt_normalizer
```

Validation receipts are saved under `$SIPS_HOME/tool_factory/validations`. Promotion copies declared files into `$SIPS_HOME/skills/<name>/versions/<digest>`, revalidates the packaged entrypoint, and atomically updates SKILL.md and active.json individually. Previous versions remain available. The active manifest records the exact entrypoint and contract. Host discovery remains explicitly unverified: packaging and direct invocation do not refresh the installed plugin or prove exposure in an open task. Promotion is not a cross-file transaction between SKILL.md and active.json; the skill's entrypoint remains independently pinned.

Validation executes trusted helpers. Disposable fixture directories are not an operating-system sandbox, and unlisted external dependencies are not vendored or fingerprinted. Interpreter metadata is recorded. Add required local modules and data as resources. Do not interpret an artifact hash as identity for every external service or package.

## Select or compose

`homebase_tool_factory` preserves its existing inputs and adds `available_types` and `required_types` arrays. Whole-token filename/description matches replace substring matches. An explicit existing script receives preference. Shell helpers are included.

When types are supplied, direct candidates must satisfy joint input and precondition requirements. A bounded breadth-first search can propose multi-tool compositions (at most four steps and approximately 1,000 visited states). Types and prerequisites are symbolic declarations; the caller must establish their real-world validity. A proposed composition does not execute tools or demonstrate behavioral compatibility.

Results distinguish `reuse_or_improve`, `compose`, `insufficient_fit`, and explicit `force_new` scaffolding. `next_argv` provides an argument array and `next_command` its shell-quoted equivalent. Recommendations pin the factory executable and candidate helper path; validate/promote also accept `--script /absolute/path/to/helper.py` for project-local helpers. Insufficient fit does not automatically authorize creating another tool. Contract-free candidates are labeled unavailable and require a contract before promotion.

## Diagnose and record correction

The 0.5 controller supersedes the prototype replay-command protocol. See [SIPS 0.5](sips-05.md) for revision-checked writes, isolated candidates, built-in evaluators, review, activation, and recovery. Historical v1 episodes remain readable but cannot authorize activation.

The generated skill invokes a dispatcher that reads the authoritative active.json pointer. Version directories remain immutable. Composition requires current validation receipts; stale capabilities remain discoverable for revalidation but are not used in proposed compositions.
