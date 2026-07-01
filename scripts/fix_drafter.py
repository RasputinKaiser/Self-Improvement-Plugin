#!/usr/bin/env python3
"""fix_drafter.py — drafts proposed fixes for eval regressions (Phase C).

The harness can observe, distill, inject, recall, and delegate — but it
could not FIX. When find_eval_regressions() flags a regression, nothing
drafted a fix; it just appended to improvements.md and waited for a human.

This script closes that gap. For each active regression:
1. Reads the failing case definition + its most recent EvalRun
2. Analyzes WHY the case likely failed based on check results + tool sequence
3. Drafts a proposed fix — either a prompt-nudge (improve the case prompt)
   or a diagnostic report identifying the root cause
4. Writes it to ~/.ncode/eval/proposed_fixes/<caseId>.md
5. Does NOT apply — surfaces for human or agent review

Wire into weekly_sweep.py after self_correct.py --eval-regressions.

CLI:
  fix_drafter.py                    # draft fixes for all active regressions
  fix_drafter.py --case <caseId>    # draft for one case even if not flagged
  fix_drafter.py --json             # emit JSON instead of files
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import harness_home

NCODE_DIR = harness_home()
CASES_DIR = NCODE_DIR / "eval" / "cases"
RESULTS_PATH = NCODE_DIR / "eval" / "results.jsonl"
PROPOSED_FIXES_DIR = NCODE_DIR / "eval" / "proposed_fixes"


def load_cases():
    """Load all eval cases. Returns {id: case_dict}."""
    cases = {}
    if not CASES_DIR.is_dir():
        return cases
    for f in CASES_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text())
            cases[c["id"]] = c
        except (json.JSONDecodeError, KeyError):
            continue
    return cases


def load_latest_runs():
    """Load the most recent run per case from results.jsonl. Returns {caseId: run_dict}."""
    if not RESULTS_PATH.exists():
        return {}
    latest = {}
    with open(RESULTS_PATH) as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = r.get("caseId", "")
            if not cid:
                continue
            # Keep the latest (file is append-only, last = most recent)
            latest[cid] = r
    return latest


def find_active_regressions():
    """Find cases where the latest run failed AND there's history (warmup passed)."""
    latest_runs = load_latest_runs()
    if not latest_runs:
        return []

    # Group runs by case to check baseline
    runs_by_case = {}
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as fp:
            for line in fp:
                try:
                    r = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                cid = r.get("caseId", "")
                if cid:
                    runs_by_case.setdefault(cid, []).append(r)

    regressions = []
    for cid, runs in runs_by_case.items():
        if len(runs) < 2:
            continue  # need at least 2 runs to call it a regression
        latest = runs[-1]
        if latest.get("errorMessage") or latest.get("passed"):
            if latest.get("passed"):
                continue  # latest passed — not a regression
        # Latest failed (either errorMessage or score < threshold)
        had_prior_pass = any(r.get("passed") for r in runs[:-1])
        if had_prior_pass:
            regressions.append({
                "caseId": cid,
                "latest": latest,
                "priorRuns": runs[:-1],
            })
    return regressions


def analyze_failure(case, run):
    """Diagnose WHY the case likely failed. Returns a structured analysis dict."""
    checks = case.get("grading", [])
    check_results = run.get("checkResults", [])
    tool_sequence = run.get("toolCount", 0)  # not the actual sequence, but count

    analysis = {
        "summary": "",
        "failedChecks": [],
        "passedChecks": [],
        "rootCause": "",
        "proposedFix": "",
        "fixType": "",  # "prompt_nudge" | "case_adjustment" | "agent_behavior"
    }

    for i, check in enumerate(checks):
        result = check_results[i] if i < len(check_results) else {"passed": False, "evidence": "(no result)"}
        if not result.get("passed"):
            analysis["failedChecks"].append({
                "kind": check.get("kind"),
                "arguments": check.get("arguments"),
                "evidence": result.get("evidence", ""),
            })
        else:
            analysis["passedChecks"].append(check.get("kind"))

    # Root cause heuristics
    failed_kinds = {c["kind"] for c in analysis["failedChecks"]}

    if "fileExists" in failed_kinds:
        analysis["rootCause"] = "Agent did not create the expected file."
        analysis["fixType"] = "prompt_nudge"
        analysis["proposedFix"] = (
            f"Strengthen the case prompt to explicitly state 'create a file at <path>'. "
            f"Current prompt: \"{case.get('prompt', '')[:100]}\". "
            f"Consider adding 'You MUST create the file using the Write tool.'"
        )
    elif "grep" in failed_kinds:
        grep_check = next((c for c in analysis["failedChecks"] if c["kind"] == "grep"), None)
        if grep_check:
            path = grep_check.get("arguments", {}).get("path", "")
            pattern = grep_check.get("arguments", {}).get("pattern", "")
            analysis["rootCause"] = f"File {path} exists but doesn't contain expected pattern '{pattern}'."
            analysis["fixType"] = "prompt_nudge"
            analysis["proposedFix"] = (
                f"The agent created {path} but the content didn't match '{pattern}'. "
                f"Strengthen the prompt to specify exact content. "
                f"Or relax the grep pattern if the match is too strict."
            )
    elif "transcriptSequence" in failed_kinds:
        analysis["rootCause"] = "Agent did not follow the expected tool sequence (e.g., Read before Edit)."
        analysis["fixType"] = "agent_behavior"
        analysis["proposedFix"] = (
            "The agent skipped the Read step before editing. "
            "This is a behavioral regression — check if a recent prompt or model change "
            "caused the agent to stop reading files before editing. "
            "Consider adding a SessionStart reminder about Read-before-Edit protocol."
        )
    else:
        analysis["rootCause"] = "Unknown failure pattern — no checks failed but case didn't pass."
        analysis["fixType"] = "case_adjustment"
        analysis["proposedFix"] = (
            "Review the case definition and the latest run's check results manually. "
            "The passThreshold may be too high, or a check may be misconfigured."
        )

    if run.get("errorMessage"):
        analysis["rootCause"] = f"Run errored: {run['errorMessage']}"
        analysis["fixType"] = "agent_behavior"
        analysis["proposedFix"] = (
            f"The eval run itself failed with: {run['errorMessage']}. "
            f"Check if the ncode binary, sandbox, or timeout is misconfigured. "
            f"This is not an agent quality issue — it's infrastructure."
        )

    analysis["summary"] = (
        f"Case '{case.get('id')}' failed: {len(analysis['failedChecks'])} of {len(checks)} checks failed. "
        f"Root cause: {analysis['rootCause']}"
    )
    return analysis


def draft_fix(case, run, analysis):
    """Build the markdown fix proposal."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Proposed Fix — {case.get('id', '?')}",
        f"",
        f"**Drafted**: {ts}",
        f"**Fix type**: {analysis['fixType']}",
        f"**Root cause**: {analysis['rootCause']}",
        f"",
        f"## Summary",
        f"",
        analysis["summary"],
        f"",
        f"## Failed checks ({len(analysis['failedChecks'])})",
        f"",
    ]
    for fc in analysis["failedChecks"]:
        lines.append(f"- **{fc['kind']}** — {fc.get('evidence', '(no evidence)')}")
        lines.append(f"  - arguments: `{json.dumps(fc.get('arguments', {}))}`")

    lines.extend([
        f"",
        f"## Passed checks ({len(analysis['passedChecks'])})",
        f"",
    ])
    for pc in analysis["passedChecks"]:
        lines.append(f"- {pc}")

    lines.extend([
        f"",
        f"## Proposed fix",
        f"",
        analysis["proposedFix"],
        f"",
        f"## Latest run details",
        f"",
        f"- Score: {run.get('score', '?')}",
        f"- Passed: {run.get('passed', '?')}",
        f"- Tool count: {run.get('toolCount', '?')}",
        f"- Error: {run.get('errorMessage', '(none)')}",
        f"- Sandbox: {run.get('sandboxURL', '?')}",
        f"",
        f"## Next steps",
        f"",
        f"1. Review the proposed fix above.",
        f"2. If the fix is a prompt-nudge: edit the case JSON at `~/.ncode/eval/cases/{case.get('id')}.json`.",
        f"3. If the fix is agent-behavior: add a SessionStart reminder or adjust the system prompt.",
        f"4. Re-run: `python3 ~/.ncode/scripts/eval_harness.py --case {case.get('id')}`",
        f"5. If the case passes: this proposed fix can be archived. If it fails again: escalate to fan-out.",
    ])
    return "\n".join(lines) + "\n"


def cmd_draft(case_id=None, emit_json=False):
    """Draft fixes for all active regressions (or one specific case)."""
    cases = load_cases()
    latest_runs = load_latest_runs()

    if case_id:
        # Draft for one specific case
        if case_id not in cases:
            print(f"ERR: case {case_id} not found", file=sys.stderr)
            return 1
        if case_id not in latest_runs:
            print(f"ERR: no runs found for {case_id}", file=sys.stderr)
            return 1
        regressions = [{"caseId": case_id, "latest": latest_runs[case_id], "priorRuns": []}]
    else:
        regressions = find_active_regressions()

    if not regressions:
        msg = "No active regressions to draft fixes for." if not case_id else f"No runs for case {case_id}."
        if emit_json:
            print(json.dumps({"ok": True, "drafted": 0, "message": msg}))
        else:
            print(msg)
        return 0

    PROPOSED_FIXES_DIR.mkdir(parents=True, exist_ok=True)
    drafted = []
    for reg in regressions:
        cid = reg["caseId"]
        case = cases.get(cid)
        if not case:
            continue
        run = reg["latest"]
        analysis = analyze_failure(case, run)
        markdown = draft_fix(case, run, analysis)

        fix_path = PROPOSED_FIXES_DIR / f"{cid}.md"
        fix_path.write_text(markdown, encoding="utf-8")
        drafted.append({
            "caseId": cid,
            "fixPath": str(fix_path),
            "fixType": analysis["fixType"],
            "rootCause": analysis["rootCause"],
            "summary": analysis["summary"],
        })

    if emit_json:
        print(json.dumps({"ok": True, "drafted": len(drafted), "fixes": drafted}, indent=2))
    else:
        print(f"Drafted {len(drafted)} proposed fix(es):")
        for d in drafted:
            print(f"  {d['caseId']}: {d['fixType']} — {d['rootCause'][:80]}")
            print(f"    → {d['fixPath']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Draft proposed fixes for eval regressions (Phase C)")
    ap.add_argument("--case", help="draft for one case (even if not flagged as regression)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of writing files")
    args = ap.parse_args()
    return cmd_draft(args.case, args.json)


if __name__ == "__main__":
    sys.exit(main())
