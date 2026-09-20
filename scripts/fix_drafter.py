#!/usr/bin/env python3
"""Draft evidence-preserving correction hypotheses and durable local episodes.

Failed checks, missing evidence, and infrastructure errors remain distinct.
--json emits a summary alongside proposal files; no fixes are auto-applied.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import harness_home

SIPS_DIR = harness_home()
CASES_DIR = SIPS_DIR / "eval" / "cases"
RESULTS_PATH = SIPS_DIR / "eval" / "results.jsonl"
PROPOSED_FIXES_DIR = SIPS_DIR / "eval" / "proposed_fixes"


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
        had_prior_pass = any(r.get("passed") and r.get("caseVersion") == latest.get("caseVersion")
                             and r.get("model") == latest.get("model") for r in runs[:-1])
        if had_prior_pass:
            regressions.append({
                "caseId": cid,
                "latest": latest,
                "priorRuns": runs[:-1],
            })
    return regressions


def analyze_failure(case, run):
    """Separate observations from hypotheses; never infer missing results failed."""
    from sips_runtime.canonical import canonical_hash
    analysis = {'summary': '', 'failedChecks': [], 'passedChecks': [], 'unavailableChecks': [],
                'rootCause': 'Unestablished', 'hypotheses': [], 'fixType': 'diagnostic',
                'intervention': 'gather_evidence', 'evaluator_digest': canonical_hash(case)}
    if (case.get('version') is not None and run.get('caseVersion') is not None
            and case['version'] != run['caseVersion']):
        analysis.update(fixType='evidence_unavailable',
                        summary='Case version differs from the recorded run; replay required.',
                        proposedFix='Recover the original case version or establish a new baseline before diagnosis.')
        analysis['unavailableChecks'] = list(case.get('grading', []))
        return analysis
    results = run.get('checkResults') or []
    for index, check in enumerate(case.get('grading', [])):
        result = results[index] if index < len(results) else None
        record = {'kind': check.get('kind'), 'arguments': check.get('arguments'),
                  'evidence': result.get('evidence', '') if isinstance(result, dict) else '(no result)'}
        if not isinstance(result, dict) or type(result.get('passed')) is not bool:
            analysis['unavailableChecks'].append(record)
        elif result['passed']:
            analysis['passedChecks'].append(check.get('kind'))
        else:
            analysis['failedChecks'].append(record)
    if run.get('errorMessage'):
        analysis.update(fixType='infrastructure', rootCause='Run unavailable: ' + str(run['errorMessage']))
        analysis['hypotheses'] = ['Execution environment or provider failure; task quality is unmeasured.']
        analysis['proposedFix'] = 'Inspect execution error and restore the environment before replaying the unchanged case.'
    elif analysis['unavailableChecks']:
        analysis['proposedFix'] = 'Recover missing check results before selecting a repair. Missing evidence is not failure.'
    else:
        kinds = {check['kind'] for check in analysis['failedChecks']}
        if 'fileExists' in kinds:
            analysis['hypotheses'] = ['Expected artifact absent at evaluation; inspect path, execution and persistence.']
        elif 'grep' in kinds:
            analysis['hypotheses'] = ['Content assertion failed; file absence, wrong path, or content mismatch remain possible.']
        elif 'transcriptSequence' in kinds:
            analysis['hypotheses'] = ['Recorded sequence did not satisfy the declared rule; inspect that rule and trace.']
        else:
            analysis['hypotheses'] = ['Inspect check evidence and acceptance aggregation before assigning responsibility.']
        analysis['proposedFix'] = ('Inspect the first divergence in the trace and test the hypothesis. '
            'Choose context refresh, interface repair, implementation repair, reuse, composition, or creation from evidence. '
            'Keep the original prompt, grading checks, and threshold fixed during repair; evaluator corrections require a new baseline.')
    analysis['summary'] = (f"Case '{case.get('id')}': {len(analysis['failedChecks'])} failed checks, "
                           f"{len(analysis['unavailableChecks'])} unavailable; cause unestablished.")
    return analysis


def draft_fix(case, run, analysis):
    """Build the markdown fix proposal."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Proposed Fix — {case.get('id', '?')}",
        f"",
        f"**Drafted**: {ts}",
        f"**Fix type**: {analysis['fixType']}",
        f"**Root cause status**: {analysis['rootCause']}",
        f"**Hypotheses**: {json.dumps(analysis['hypotheses'])}",
        f"**Unavailable checks**: {len(analysis['unavailableChecks'])}",
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
        "1. Inspect the cited evidence and distinguish competing hypotheses.",
        "2. Record a scoped intervention with adaptation.py propose and its candidate artifact.",
        "3. Evaluate the frozen original case, regressions, and counterexamples using adaptation.py evaluate.",
        "4. Inspect ready_for_review evidence; activation requires an explicit request naming the candidate digest.",
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
        from adaptation import observe
        episode = observe(case, run, analysis)
        markdown = draft_fix(case, run, analysis) + f"\nCorrection episode: `{episode}`\n"


        fix_path = PROPOSED_FIXES_DIR / f"{episode}.md"
        fix_path.write_text(markdown, encoding="utf-8")
        drafted.append({
            "caseId": cid,
            "episode": episode,
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
    ap.add_argument("--json", action="store_true", help="emit JSON summary; proposal files and episodes are still written")
    args = ap.parse_args()
    return cmd_draft(args.case, args.json)


if __name__ == "__main__":
    sys.exit(main())
