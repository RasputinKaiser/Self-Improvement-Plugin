# Selfloop C0 Compatible Controller and Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the current usable `/selfloop` while making the CLI, legacy goal-state entry point, MCP tool, slash command, and Codex skill delegate to one C0 controller without claiming machine-enforced adaptive experiments.

**Architecture:** Add the protected package boundary at `scripts/selfloop_supervisor/` and place the C0 controller and compatibility store there. `scripts/selfloop_cli.py` becomes the canonical executable adapter; `scripts/goal_state.py` and `scripts/harness_homebase_mcp.py` remain compatible thin adapters, while the Markdown surfaces point to the same CLI. The evolvable `scripts/selfloop_strategy/` package is created but remains empty except for its package marker until later plans.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `json`, `pathlib`, `argparse`, pytest 8+, existing JSON-RPC MCP transport.

## Global Constraints

- Normative contract is `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, version `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`; C0 MUST NOT advertise C1-C5 behavior.
- “This document is the single normative `/selfloop` contract. The slash command, Codex skill, Homebase MCP tool, controller CLI, and state projection are adapters. They MUST share one controller kernel and one state model rather than reimplementing the protocol in prose.”
- “Current cycles remain usable while reported as agent-executed, not machine-enforced adaptive experiments.”
- “Existing content-sensitive snapshot identity is preserved.”
- “C0 does not claim the every-invocation experiment guarantee.”
- “The existing `homebase.selfloop.v1` response MAY remain as a compatibility endpoint, but its meaning MUST NOT change silently and it MUST NOT advertise adaptive conformance.”
- Mutable state continues at `${SIPS_HOME:-~/.codex/sips}/goal_state.json` in C0; root-scoped replacement belongs to P01.
- `stop` maps to the existing C0 `clear` behavior; v2 evidence-retaining abort semantics do not exist yet.
- Source, installed cache, configuration, child process, host enumeration, task advertisement, and successful task-local invocation remain separate proof layers.

---

## File Map

- Create `scripts/selfloop_supervisor/__init__.py`: protected package exports.
- Create `scripts/selfloop_supervisor/contracts.py`: C0 request/result types and constants.
- Create `scripts/selfloop_supervisor/compat_controller.py`: only implementation of C0 selfloop transitions.
- Create `scripts/selfloop_supervisor/projection.py`: minimal marker-delimited C0 truth projection.
- Create `scripts/selfloop_strategy/__init__.py`: reserved evolvable package boundary.
- Create `scripts/selfloop_cli.py`: canonical executable adapter.
- Modify `scripts/goal_state.py`: delegate selfloop-specific actions while retaining generic goal/subtask behavior.
- Modify `scripts/harness_homebase_mcp.py`: call the canonical controller instead of spawning `goal_state.py`.
- Modify `commands/selfloop.md` and `skills/sips-selfloop/SKILL.md`: point at the CLI and state the C0 claim boundary.
- Create `tests/selfloop/test_c0_controller.py` and `tests/selfloop/test_c0_adapters.py`.
- Modify `tests/test_homebase_mcp.py`: pin the unchanged v1 envelope and C0 claim.

### Task 1: Define the C0 contract and controller

**Files:**
- Create: `scripts/selfloop_supervisor/__init__.py`
- Create: `scripts/selfloop_supervisor/contracts.py`
- Create: `scripts/selfloop_supervisor/compat_controller.py`
- Create: `scripts/selfloop_strategy/__init__.py`
- Test: `tests/selfloop/test_c0_controller.py`

**Interfaces:**
- Consumes: `sips_paths.goal_state_path() -> pathlib.Path`.
- Produces: `ControllerRequest(action, root, focus, outcome, summary)`, `ControllerResult(exit_code, payload)`, and `CompatibilityController.execute(request) -> ControllerResult`.

- [ ] **Step 1: Write controller tests that pin current start, record, pause, resume, complete, status, and clear behavior**

```python
from datetime import datetime, timezone
from pathlib import Path

from selfloop_supervisor.compat_controller import CompatibilityController
from selfloop_supervisor.contracts import ControllerRequest


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def test_c0_start_record_and_controls_preserve_legacy_fields(tmp_path: Path):
    controller = CompatibilityController(tmp_path / "goal_state.json", now=lambda: NOW)
    started = controller.execute(ControllerRequest(action="start", root=tmp_path, focus="tool reliability"))
    assert started.exit_code == 0
    assert started.payload == {
        "ok": True,
        "objective": started.payload["objective"],
        "status": "active",
        "mode": "selfloop",
        "focus": "tool reliability",
    }
    recorded = controller.execute(ControllerRequest(
        action="record", root=tmp_path, outcome="improved", summary="focused test passes"
    ))
    assert recorded.payload["cycleCount"] == 1
    assert recorded.payload["plateauStreak"] == 0
    assert recorded.payload["cycle"]["summary"] == "focused test passes"
    assert controller.execute(ControllerRequest(action="pause", root=tmp_path)).payload["status"] == "paused"
    assert controller.execute(ControllerRequest(action="resume", root=tmp_path)).payload["status"] == "active"
    assert controller.execute(ControllerRequest(action="complete", root=tmp_path)).payload["status"] == "complete"
    assert controller.execute(ControllerRequest(action="clear", root=tmp_path)).payload == {"ok": True, "cleared": True}


def test_c0_rejects_free_text_errors_without_adaptive_claims(tmp_path: Path):
    controller = CompatibilityController(tmp_path / "goal_state.json", now=lambda: NOW)
    result = controller.execute(ControllerRequest(action="record", root=tmp_path, outcome="improved", summary=""))
    assert result.exit_code == 1
    assert result.payload == {"ok": False, "error": "no goal set"}
```

- [ ] **Step 2: Run the focused tests and observe the missing package failure**

Run: `python3 -m pytest -q tests/selfloop/test_c0_controller.py`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'selfloop_supervisor'`.

- [ ] **Step 3: Implement the exact contract and transition surface**

```python
# scripts/selfloop_supervisor/contracts.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

V1_SCHEMA = "homebase.selfloop.v1"
C0_STAGE = "C0"

@dataclass(frozen=True)
class ControllerRequest:
    action: str
    root: Path
    focus: str = ""
    outcome: str = ""
    summary: str = ""

@dataclass(frozen=True)
class ControllerResult:
    exit_code: int
    payload: dict
```

Implement `CompatibilityController` in `compat_controller.py` by moving the bodies of `cmd_selfloop_set`, `cmd_selfloop_record`, `cmd_status`, `cmd_pause`, `cmd_resume`, `cmd_complete`, and `cmd_clear` from `goal_state.py` into `execute()`. Preserve their exact JSON fields, the 25-entry history cap, exit codes, focus objective text, and `improved|plateau|blocked` validation. Inject `now: Callable[[], datetime]` and write only the constructor-supplied state path. Export the three public types from `selfloop_supervisor/__init__.py`; make `selfloop_strategy/__init__.py` contain only `"""Evolvable selfloop strategy package."""`.

- [ ] **Step 4: Run the controller tests**

Run: `python3 -m pytest -q tests/selfloop/test_c0_controller.py`

Expected: `2 passed`.

- [ ] **Step 5: Commit the protected C0 controller**

```bash
git add scripts/selfloop_supervisor/__init__.py scripts/selfloop_supervisor/contracts.py scripts/selfloop_supervisor/compat_controller.py scripts/selfloop_strategy/__init__.py tests/selfloop/test_c0_controller.py
git commit -m "feat(selfloop): add protected C0 controller"
```

### Task 2: Add the canonical CLI and retain the legacy entry point

**Files:**
- Create: `scripts/selfloop_cli.py`
- Modify: `scripts/goal_state.py`
- Test: `tests/selfloop/test_c0_adapters.py`

**Interfaces:**
- Consumes: `CompatibilityController.execute(ControllerRequest) -> ControllerResult`.
- Produces: `selfloop_cli.run_action(action, root, focus="", outcome="", summary="") -> ControllerResult` and `selfloop_cli.main(argv=None) -> int`.

- [ ] **Step 1: Write subprocess parity tests**

```python
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def run(script: str, *args: str, home: Path):
    env = {**os.environ, "SIPS_HOME": str(home)}
    return subprocess.run([sys.executable, str(ROOT / script), *args], text=True, capture_output=True, env=env)

def test_cli_and_goal_state_share_one_c0_state(tmp_path: Path):
    started = run("scripts/selfloop_cli.py", "start", "tool reliability", home=tmp_path)
    assert started.returncode == 0
    assert json.loads(started.stdout)["focus"] == "tool reliability"
    recorded = run("scripts/goal_state.py", "selfloop-record", "improved", "proof receipt", home=tmp_path)
    assert recorded.returncode == 0
    status = run("scripts/selfloop_cli.py", "status", home=tmp_path)
    assert json.loads(status.stdout)["cycleCount"] == 1
```

- [ ] **Step 2: Run the parity test and observe the missing CLI**

Run: `python3 -m pytest -q tests/selfloop/test_c0_adapters.py`

Expected: FAIL because `scripts/selfloop_cli.py` does not exist.

- [ ] **Step 3: Implement the CLI and legacy delegation**

Create `run_action()` using `goal_state_path()` and `CompatibilityController`; parse `start [focus]`, `record <outcome> <summary>`, `status`, `pause`, `resume`, `complete`, `clear`, and alias `stop` to `clear`. Print `result.payload` once and return `result.exit_code`. In `goal_state.py`, replace only `cmd_selfloop_set` and `cmd_selfloop_record` bodies with calls to `run_action`; when generic `status|pause|resume|complete|clear` sees `mode == "selfloop"`, delegate that action. Leave ordinary goal and subtask functions byte-for-byte unchanged.

- [ ] **Step 4: Run adapter and legacy regressions**

Run: `python3 -m pytest -q tests/selfloop/test_c0_adapters.py && python3 scripts/run_tests.py goal_state --verbose`

Expected: adapter test passes and the `goal_state` suite reports `4 pass, 0 fail`.

- [ ] **Step 5: Commit the CLI adapters**

```bash
git add scripts/selfloop_cli.py scripts/goal_state.py tests/selfloop/test_c0_adapters.py
git commit -m "refactor(selfloop): route legacy CLI through C0 controller"
```

### Task 3: Route MCP, command, and skill through the controller

**Files:**
- Modify: `scripts/harness_homebase_mcp.py`
- Modify: `commands/selfloop.md`
- Modify: `skills/sips-selfloop/SKILL.md`
- Modify: `tests/test_homebase_mcp.py`

**Interfaces:**
- Consumes: `run_action(action, root, focus="", outcome="", summary="") -> ControllerResult`, `V1_SCHEMA`, and `C0_STAGE`.
- Produces: unchanged `homebase.selfloop.v1` envelope plus `conformanceStage: "C0"` and `adaptiveGuarantee: false`.

- [ ] **Step 1: Extend the MCP test to pin the compatibility claim**

```python
structured = started["result"]["structuredContent"]
assert structured["schema"] == "homebase.selfloop.v1"
assert structured["conformanceStage"] == "C0"
assert structured["adaptiveGuarantee"] is False
assert "agent must still execute" in structured["claim_boundary"]
```

- [ ] **Step 2: Run the MCP test and observe the missing C0 fields**

Run: `python3 -m pytest -q tests/test_homebase_mcp.py::test_homebase_selfloop_starts_and_records_cycle`

Expected: FAIL with `KeyError: 'conformanceStage'`.

- [ ] **Step 3: Replace MCP subprocess routing and align prose adapters**

Import `run_action`, `C0_STAGE`, and `V1_SCHEMA`; have `selfloop_payload()` call `run_action()` directly and preserve the existing `state`, `status`, `protocol`, and claim-boundary meanings. Preserve the existing receipt shape as `{"ok": exit_code == 0, "returncode": exit_code, "stdout": json.dumps(result.payload), "stderr": "", "command": ["selfloop-controller", action], "cwd": str(root)}`. Add only the two pinned compatibility fields. Update both Markdown adapters to invoke `python3 scripts/selfloop_cli.py`; explicitly say C0 persists an agent-executed loop and does not prove an experiment occurred.

- [ ] **Step 4: Run focused and full verification**

Run: `python3 -m pytest -q tests/selfloop tests/test_homebase_mcp.py && python3 scripts/run_tests.py homebase_mcp --verbose && python3 scripts/validate_v2.py`

Expected: all focused pytest tests pass, Homebase MCP reports zero failures, and the validator exits 0.

- [ ] **Step 5: Commit the adapter convergence**

```bash
git add scripts/harness_homebase_mcp.py commands/selfloop.md skills/sips-selfloop/SKILL.md tests/test_homebase_mcp.py
git commit -m "refactor(selfloop): converge C0 adapters"
```

### Task 4: Prove and record the C0 boundary

**Files:**
- Create: `scripts/selfloop_supervisor/projection.py`
- Modify: `scripts/validate_v2.py`
- Modify: `tests/selfloop/test_c0_adapters.py`

**Interfaces:**
- Consumes: C0 adapter constants and repository surfaces.
- Produces: release validation that rejects adaptive wording at C0 and `write_c0_projection(repo_root) -> Path`, which owns a marker-delimited non-authoritative live block.

- [ ] **Step 1: Add validator checks for one CLI route, v1 schema, C0 stage, and absent adaptive guarantee**

Add exact assertions that both Markdown adapters name `scripts/selfloop_cli.py`, MCP imports `V1_SCHEMA`, and no C0 surface contains `machine-enforced adaptive experiment` as a positive claim.

- [ ] **Step 2: Write and test the minimal generated projection**

Use markers `# >>> SIPS SELFLOOP GENERATED v1 >>>` and `# <<< SIPS SELFLOOP GENERATED v1 <<<`. `write_c0_projection()` preserves every byte outside the markers and renders exactly `spec_version: selfloop.spec.v1`, `conformance_stage: C0`, `adaptive_guarantee: false`, and `authority: supervisor-projection-only`. Call it after successful C0 mutations; status never writes. Test that an existing prefix and suffix are byte-identical after two writes and that no controller load path reads `state.yaml`.

- [ ] **Step 3: Run the release gate**

Run: `python3 -m pytest -q && python3 scripts/run_tests.py && python3 scripts/validate_v2.py && git diff --check`

Expected: every command exits 0; the validator reports no C1-C5 claim; `git diff --check` is silent.

- [ ] **Step 4: Commit the C0 proof boundary**

```bash
git add scripts/selfloop_supervisor/projection.py scripts/validate_v2.py tests/selfloop/test_c0_adapters.py
git commit -m "chore(selfloop): declare verified C0 boundary"
```
