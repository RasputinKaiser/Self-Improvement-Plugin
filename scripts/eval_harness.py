#!/usr/bin/env python3
"""Host-independent local evaluator. No agent/model subprocess is launched."""
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from sips_paths import harness_home
from sips_runtime.evaluation import evaluate

CASES_DIR = harness_home() / 'eval' / 'cases'
RESULTS_PATH = harness_home() / 'eval' / 'results.jsonl'


def load_cases():
    result = []
    for path in sorted(CASES_DIR.glob('*.json')):
        try:
            case = json.loads(path.read_text())
            if isinstance(case, dict) and 'id' in case: result.append(case)
        except (OSError, ValueError): pass
    return result


def grade(checks, sandbox, tool_sequence):
    """Python mirror of EvalGrader.grade(_:sandboxURL:toolSequence:).

    Returns (results, score) where results is a list of {score, evidence, passed}
    dicts and score is the weighted pass fraction.
    """
    results = []
    weighted = 0.0
    total = 0.0
    for check in checks:
        weight = float(check.get("weight", 1.0))
        kind = check.get("kind", "")
        args = check.get("arguments", {})
        r = _apply_check(kind, args, sandbox, tool_sequence)
        results.append(r)
        weighted += r["score"] * weight
        total += weight
    score = weighted / total if total > 0 else 0.0
    return results, score


def _apply_check(kind, args, sandbox, tool_sequence):
    if kind == "fileExists":
        return _check_file_exists(args, sandbox, expect_present=True)
    if kind == "fileMissing":
        return _check_file_exists(args, sandbox, expect_present=False)
    if kind == "grep":
        return _check_grep(args, sandbox)
    if kind == "transcriptSequence":
        return _check_transcript_sequence(args, tool_sequence)
    if kind == "llmJudge":
        return _check_llm_judge(args, sandbox)
    return {"score": 0.0, "evidence": f"unknown check kind: {kind}", "passed": False}


def _check_llm_judge(args, sandbox):
    return {"score": 0.0, "passed": False, "status": "unavailable",
            "evidence": "Explicit active-task model review required; no model launched"}


def _check_file_exists(args, sandbox, expect_present):
    rel = args.get("path", "")
    if not rel:
        return {"score": 0.0, "evidence": "missing 'path' argument", "passed": False}
    target = sandbox / rel
    present = target.exists()
    if expect_present:
        ok = present
        evidence = f"{rel} {'exists' if present else 'missing'}"
    else:
        ok = not present
        evidence = f"{rel} {'absent (correct)' if not present else 'present (wrong)'}"
    return {"score": 1.0 if ok else 0.0, "evidence": evidence, "passed": ok}


def _check_grep(args, sandbox):
    rel = args.get("path", "")
    pattern = args.get("pattern", "")
    if not rel or not pattern:
        return {"score": 0.0, "evidence": "missing 'path' or 'pattern'", "passed": False}
    target = sandbox / rel
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"score": 0.0, "evidence": f"could not read {rel}", "passed": False}
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"score": 0.0, "evidence": f"invalid regex: {e}", "passed": False}
    matched = regex.search(content) is not None
    return {
        "score": 1.0 if matched else 0.0,
        "evidence": f"pattern {pattern} {'matched' if matched else 'not found'} in {rel}",
        "passed": matched,
    }


def _check_transcript_sequence(args, tool_sequence):
    before = args.get("before", "")
    first = args.get("first", "")
    if not before:
        return {"score": 0.0, "evidence": "missing 'before' argument", "passed": False}
    try:
        first_re = re.compile(first) if first else None
        before_re = re.compile(before)
    except re.error as e:
        return {"score": 0.0, "evidence": f"invalid regex: {e}", "passed": False}
    first_idx = None
    before_idx = None
    for i, tool in enumerate(tool_sequence):
        if first_idx is None and first_re and first_re.search(tool):
            first_idx = i
        if before_idx is None and before_re.search(tool):
            before_idx = i
    if before_idx is not None:
        if first_idx is not None:
            ok = first_idx < before_idx
            return {"score": 1.0 if ok else 0.0,
                    "evidence": f"first({first}) at {first_idx}, before({before}) at {before_idx}",
                    "passed": ok}
        return {"score": 0.0,
                "evidence": f"before-pattern matched at {before_idx} but first({first}) never appeared",
                "passed": False}
    return {"score": 1.0,
            "evidence": f"before-pattern ({before}) never matched; sequence ok",
            "passed": True}


def run_case(eval_case, timeout_seconds=None, workspace=None):
    suite = eval_case.get('suite')
    if not isinstance(suite, dict) or workspace is None:
        receipt = {'status': 'unavailable', 'error': 'local suite and explicit workspace required', 'checks_run': 0}
    else:
        receipt = evaluate(suite, Path(workspace).resolve(), Path(workspace).resolve(),
                           command_timeout=timeout_seconds or 120)
    return {'caseId': eval_case['id'], 'caseVersion': eval_case.get('version', 1),
            'finishedAtISO': datetime.now(timezone.utc).isoformat(),
            'passed': receipt['status'] == 'passed',
            'score': None if receipt['status'] == 'unavailable' else float(receipt['status'] == 'passed'),
            'errorMessage': receipt.get('error') or ('evaluation unavailable' if receipt['status'] == 'unavailable' else None),
            'receipt': receipt, 'checkResults': [], 'model': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case'); parser.add_argument('--json', action='store_true')
    parser.add_argument('--workspace'); parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--total-budget-tokens', type=int, help='Compatibility only; this evaluator makes no model calls')
    args = parser.parse_args()
    cases = [c for c in load_cases() if not args.case or c['id'] == args.case]
    runs = [run_case(c, args.timeout, args.workspace) for c in cases]
    if runs:
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RESULTS_PATH.open('a') as handle:
            for run in runs: handle.write(json.dumps(run) + '\n')
    summary = {'ran': len(runs), 'passed': sum(r['passed'] for r in runs),
               'errors': sum(bool(r['errorMessage']) for r in runs), 'results': runs,
               'status': 'unavailable' if not runs else 'passed' if all(r['passed'] for r in runs) else 'failed'}
    print(json.dumps(summary, indent=2))
    return 0 if summary['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
