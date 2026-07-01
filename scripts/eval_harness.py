#!/usr/bin/env python3
"""eval_harness.py — Python mirror of the Swift EvalRunner.

Runs eval cases against the live NCode model config in an isolated sandbox
cwd, captures the ordered tool_use names from the stream-json transcript,
grades each case via deterministic checkers, and appends the result to
~/.ncode/eval/results.jsonl as newline-delimited JSON.

Mirrors the Swift EvalRunner in ~/Code/harness-app/Sources/HarnessApp/Services/EvalRunner.swift.
Two implementations because:
- The macOS app owns the interactive UX (Run button, last-score badges).
- The weekly cron is Python and needs to drive evals unattended (no UI open).

CLI:
  eval_harness.py                       # run all cases in ~/.ncode/eval/cases/
  eval_harness.py --case <id>           # run one case by id
  eval_harness.py --json                # emit summary JSON to stdout (for cron)
  eval_harness.py --total-budget-tokens <n>  # cap total tokens across all cases
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sips_paths import harness_home

NCODE_DIR = harness_home()
CASES_DIR = NCODE_DIR / "eval" / "cases"
RESULTS_PATH = NCODE_DIR / "eval" / "results.jsonl"
SANDOXES_DIR = NCODE_DIR / "eval" / "sandboxes"

NCODE_BIN_CANDIDATES = [
    str(Path.home() / ".local/bin/ncode"),
    "/usr/local/bin/ncode",
]


def find_ncode():
    for p in NCODE_BIN_CANDIDATES:
        if os.access(p, os.X_OK):
            return p
    return None


def load_cases():
    """Discover all JSON case files under CASES_DIR."""
    if not CASES_DIR.is_dir():
        return []
    out = []
    for f in sorted(CASES_DIR.glob("*.json")):
        try:
            with open(f) as fp:
                c = json.load(fp)
            if all(k in c for k in ("id", "prompt", "grading")):
                out.append(c)
        except (json.JSONDecodeError, OSError):
            continue
    return out


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
    """Invoke eval_llm_judge.py with rubric. Returns confidence=low result.

    Skips (returns score=0, confidence='low') if the judge script is missing
    — Tier C is degraded gracefully rather than blocking the case.
    """
    from pathlib import Path
    rubric = args.get("rubric", "")
    if not rubric:
        return {"score": 0.0, "evidence": "llmJudge missing 'rubric' argument", "passed": False}
    judge_script = Path(__file__).parent / "eval_llm_judge.py"
    if not judge_script.exists():
        return {"score": 0.0, "evidence": "eval_llm_judge.py not found", "passed": False}
    try:
        r = subprocess.run(
            ["python3", str(judge_script),
             "--sandbox", str(sandbox),
             "--rubric", rubric,
             "--majority",
             "--json"],
            capture_output=True, text=True, timeout=400,  # 3 judge calls × ~120s each
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"score": 0.0, "evidence": f"judge spawn failed: {e}", "passed": False}
    if r.returncode != 0:
        return {"score": 0.0, "evidence": f"judge exit {r.returncode}: {r.stderr[:200]}", "passed": False}
    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"score": 0.0, "evidence": f"judge output unparseable: {e}", "passed": False}
    return {
        "score": float(result.get("score", 0.0)),
        "evidence": f"llmJudge — {result.get('evidence', '?')}",
        "passed": bool(result.get("passed", False)),
        "confidence": "low",
    }


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


def run_case(eval_case, timeout_seconds=None):
    """Mirror of EvalRunner.run(case:). Spawns ncode one-shot per case in sandbox."""
    case_id = eval_case["id"]
    case_version = eval_case.get("version", 1)
    timeout = timeout_seconds or int(eval_case.get("timeoutSeconds", 60))
    prompt = eval_case["prompt"]

    SANDOXES_DIR.mkdir(parents=True, exist_ok=True)
    sandbox = SANDOXES_DIR / uuid.uuid4().hex[:8]
    sandbox.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    bin_path = find_ncode()
    if not bin_path:
        run = {
            "id": str(uuid.uuid4()),
            "caseId": case_id, "caseVersion": case_version,
            "startedAtISO": started_at, "finishedAtISO": started_at,
            "score": 0.0, "passed": False,
            "sandboxURL": str(sandbox),
            "checkResults": [],
            "toolCount": 0,
            "model": None,
            "errorMessage": "ncode binary not found",
        }
        persist(run)
        return run

    args = [
        bin_path,
        "--print",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--session-id", uuid.uuid4().hex,
        "--permission-mode", "bypassPermissions",
    ]
    payload = json.dumps({
        "type": "user",
        "message": {"role": "user", "content": prompt},
    }) + "\n"

    tool_sequence = []
    result_seen = False
    error_msg = None
    run_tokens = 0

    try:
        proc = subprocess.Popen(
            args,
            cwd=sandbox,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                proc.terminate()
                error_msg = "timeout"
                break
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = event.get("type", "")
            if etype == "assistant":
                msg = event.get("message", {})
                blocks = msg.get("content", [])
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "?")
                            tool_sequence.append(name)
            elif etype == "result":
                result_seen = True
                # Extract token usage from the result event for budget tracking
                usage = event.get("usage", {})
                run_tokens = (usage.get("input_tokens", 0)
                               + usage.get("output_tokens", 0)
                               + usage.get("cache_read_input_tokens", 0)
                               + usage.get("cache_creation_input_tokens", 0))
                break
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    except (FileNotFoundError, OSError) as e:
        error_msg = str(e)

    finished_at = datetime.now(timezone.utc).isoformat()
    if error_msg:
        run = {
            "id": str(uuid.uuid4()),
            "caseId": case_id, "caseVersion": case_version,
            "startedAtISO": started_at, "finishedAtISO": finished_at,
            "score": 0.0, "passed": False,
            "sandboxURL": str(sandbox),
            "checkResults": [],
            "toolCount": len(tool_sequence),
            "model": None,
            "errorMessage": error_msg,
        }
        persist(run)
        return run

    checks = eval_case.get("grading", [])
    check_results, score = grade(checks, sandbox, tool_sequence)
    threshold = float(eval_case.get("passThreshold", 1.0))
    passed = score >= threshold

    run = {
        "id": str(uuid.uuid4()),
        "caseId": case_id, "caseVersion": case_version,
        "startedAtISO": started_at, "finishedAtISO": finished_at,
        "score": score, "passed": passed,
        "sandboxURL": str(sandbox),
        "checkResults": check_results,
        "toolCount": len(tool_sequence),
        "totalTokens": run_tokens,
        "model": None,
        "errorMessage": None,
    }
    persist(run)
    return run


def persist(run):
    """Append a run record to ~/.ncode/eval/results.jsonl as newline-delimited JSON."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(run) + "\n"
    with open(RESULTS_PATH, "a", encoding="utf-8") as fp:
        fp.write(line)


def main():
    ap = argparse.ArgumentParser(description="Run eval cases against the live NCode model")
    ap.add_argument("--case", help="run one case by id")
    ap.add_argument("--json", action="store_true", help="emit summary JSON")
    ap.add_argument("--total-budget-tokens", type=int, default=0,
                    help="cap total tokens across all cases; abort remaining when exceeded")
    args = ap.parse_args()

    cases = load_cases()
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"case not found: {args.case}", file=sys.stderr)
            return 2

    budget = args.total_budget_tokens
    cumulative_tokens = 0
    budget_exceeded = False
    skipped = 0

    summary = {"ran": 0, "passed": 0, "failed": 0, "errors": 0,
               "skipped": 0, "cases": [], "total_tokens": 0,
               "budget_tokens": budget}
    for c in cases:
        if budget > 0 and cumulative_tokens >= budget:
            budget_exceeded = True
            skipped += 1
            summary["skipped"] = skipped
            continue
        r = run_case(c)
        case_tokens = r.get("totalTokens", 0)
        cumulative_tokens += case_tokens
        summary["total_tokens"] = cumulative_tokens
        summary["ran"] += 1
        if r.get("errorMessage"):
            summary["errors"] += 1
        elif r.get("passed"):
            summary["passed"] += 1
        else:
            summary["failed"] += 1
        summary["cases"].append({
            "id": c["id"], "passed": r.get("passed"), "score": r.get("score"),
            "errorMessage": r.get("errorMessage"), "toolCount": r.get("toolCount"),
            "tokens": case_tokens,
        })

    if budget_exceeded:
        summary["budget_exceeded"] = True

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for c in summary["cases"]:
            sym = "" if c["passed"] else ""
            print(f"  {sym}  {c['id']}  score={c['score']}  tools={c['toolCount']}")
        print(f"\nran: {summary['ran']}  passed: {summary['passed']}  "
              f"failed: {summary['failed']}  errors: {summary['errors']}")

    return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
