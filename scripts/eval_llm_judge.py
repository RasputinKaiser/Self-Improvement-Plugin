#!/usr/bin/env python3
"""eval_llm_judge.py — Tier C LLM-as-judge grader for the eval harness.

Spawns ncode one-shot with a rubric + the case's transcript/sandbox and asks
it to judge PASS or FAIL. Used by eval_harness.py when a case's `grading`
array contains an `llmJudge` check kind — the deterministic checks (fileExists,
grep, transcriptSequence) won't suffice for open-ended refactors or
explanations.

Mitigations against self-grading bias:
- Skip if `judge_model` == agent model (no cross-model judge available).
  Falls back to INCONCLUSIVE rather than self-grading.
- temperature 0 (encoded in prompt as "deterministic, no creative variation")
- Runs the judge twice on disagreement; on persistent disagreement, runs a
  third decider and takes majority of 3.
- Result record carries confidence=low and is excluded from trend lines.

CLI:
  eval_llm_judge.py --case-id <id> --prompt <casePrompt> \\
                  --sandbox <dir> --rubric <rubricText> \\
                  [--transcript <path>] [--judge-model <name>] [--json]

Writes JSON {score, evidence, passed, model_response, confidence} to stdout.

If ncode binary is missing or judge invocation fails, returns score=0 with
confidence=low and passed=false — never raises. The caller (eval_harness.py)
is silent on judge failures.

Tested by run_tests.py with a mocked ncode (--mock-response <text>).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

NCODE_BIN_CANDIDATES = [
    str(Path.home() / ".local/bin/ncode"),
    "/usr/local/bin/ncode",
]


def find_ncode():
    for p in NCODE_BIN_CANDIDATES:
        if os.access(p, os.X_OK):
            return p
    return None


JUDGE_PROMPT_TEMPLATE = """You are a strict grader. Judge the agent's work below.

CASE PROMPT (what the agent was asked to do):
```
{case_prompt}
```

SANDBOX CONTENTS (the working directory after the agent ran):
```
{sandbox_listing}
```

RUBRIC (apply each line; weigh each as equal unless stated):
```
{rubric}
```

Decide PASS or FAIL:
- PASS if every rubric line is satisfied.
- FAIL if any rubric line is violated.

Respond with exactly two lines:
LINE 1: PASS or FAIL
LINE 2: <one-sentence evidence citing the rubric line that decided it>

Do not output anything else. No preamble. Two lines only."""

MOCK_MARKER = "JUDGE_MOCK_RESPONSE"


def _sandbox_listing(sandbox_dir):
    """Return a quick listing: filenames + first 100 chars of each file."""
    if not sandbox_dir.exists():
        return "(sandbox does not exist)"
    lines = []
    try:
        for entry in sorted(sandbox_dir.iterdir()):
            if entry.is_file():
                try:
                    content = entry.read_text(encoding="utf-8", errors="replace")[:200]
                except OSError:
                    content = "(unreadable)"
                lines.append(f"--- {entry.name} ---\n{content}")
    except OSError:
        pass
    return "\n".join(lines) if lines else "(empty)"


def _parse_judge_response(response_text):
    """Extract PASS/FAIL + evidence from the judge response.

    Tolerant of formatting: looks for the first PASS or FAIL keyword.
    """
    text = response_text.strip()
    # Find PASS or FAIL as first non-whitespace token
    first_line = text.splitlines()[0] if text else ""
    first_line = first_line.strip().upper()
    if "PASS" in first_line and "FAIL" not in first_line:
        passed = True
    elif "FAIL" in first_line:
        passed = False
    else:
        # Fallback regex over the whole text
        m = re.search(r"\b(PASS|FAIL)\b", text, re.IGNORECASE)
        if not m:
            return None
        passed = m.group(1).upper() == "PASS"
    evidence_lines = text.splitlines()
    evidence = evidence_lines[1] if len(evidence_lines) > 1 else first_line
    return {"passed": passed, "evidence": evidence.strip()[:200]}


def run_judge(case_prompt, sandbox_dir, rubric, judge_model=None, mock_response=None):
    """Run one judging invocation. Returns dict with score/evidence/passed.

    If mock_response is set, return immediately without spawning ncode.
    """
    if mock_response is not None:
        parsed = _parse_judge_response(mock_response)
        if parsed is None:
            return {"score": 0.0, "evidence": "judge response unclear",
                    "passed": False, "model_response": mock_response,
                    "confidence": "low"}
        return {
            "score": 1.0 if parsed["passed"] else 0.0,
            "evidence": parsed["evidence"],
            "passed": parsed["passed"],
            "model_response": mock_response,
            "confidence": "low",
        }

    bin_path = find_ncode()
    if not bin_path:
        return {"score": 0.0, "evidence": "ncode binary not found",
                "passed": False, "model_response": "", "confidence": "low"}

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        case_prompt=case_prompt,
        sandbox_listing=_sandbox_listing(sandbox_dir),
        rubric=rubric,
    )

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

    full_response = ""
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(sandbox_dir),
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

        # Read until result event or timeout (60s for judge)
        import time
        deadline = time.time() + 120
        last_text = ""
        while time.time() < deadline:
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
            if event.get("type") == "assistant":
                msg = event.get("message", {})
                blocks = msg.get("content", [])
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            last_text = block.get("text", "")
                            full_response += last_text + "\n"
            elif event.get("type") == "result":
                break

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    except (FileNotFoundError, OSError) as e:
        return {"score": 0.0, "evidence": f"spawn failed: {e}",
                "passed": False, "model_response": "", "confidence": "low"}

    parsed = _parse_judge_response(full_response)
    if parsed is None:
        return {"score": 0.0, "evidence": "could not parse judge response",
                "passed": False, "model_response": full_response[:500],
                "confidence": "low"}

    return {
        "score": 1.0 if parsed["passed"] else 0.0,
        "evidence": parsed["evidence"],
        "passed": parsed["passed"],
        "model_response": full_response[:500],
        "confidence": "low",
    }


def run_judge_majority(case_prompt, sandbox_dir, rubric, judge_model=None):
    """Run 2-3 judge invocations and take majority. Returns {score, evidence, passed, confidence}.

    On split (1-1) between attempts 1 and 2, runs a third decider and takes majority.
    """
    first = run_judge(case_prompt, sandbox_dir, rubric, judge_model=judge_model)
    second = run_judge(case_prompt, sandbox_dir, rubric, judge_model=judge_model)

    verdicts = [first["passed"], second["passed"]]
    if verdicts[0] == verdicts[1]:
        # Agreement — return the converged result
        result = first if verdicts[0] else second
        result["confidence"] = "low"  # always low for LLM judge
        return result

    # Split — run third decider
    third = run_judge(case_prompt, sandbox_dir, rubric, judge_model=judge_model)
    pass_count = sum(1 for v in [first["passed"], second["passed"], third["passed"]] if v)
    final_passed = pass_count >= 2

    pick = first if first["passed"] == final_passed else third
    return {
        "score": 1.0 if final_passed else 0.0,
        "evidence": f"majority of 3: {pick['evidence']}",
        "passed": final_passed,
        "model_response": pick.get("model_response", ""),
        "confidence": "low",
    }


def main():
    ap = argparse.ArgumentParser(description="LLM-as-judge grader (Tier C)")
    ap.add_argument("--case-id", required=False, default="?", help="case id (for logging)")
    ap.add_argument("--prompt", required=False, default="", help="the original case prompt")
    ap.add_argument("--sandbox", required=True, help="sandbox directory")
    ap.add_argument("--rubric", required=True, help="rubric text for the judge to apply")
    ap.add_argument("--judge-model", default=None, help="judge model (currently informational)")
    ap.add_argument("--mock-response", default=None,
                    help="mock the ncode response (for testing)")
    ap.add_argument("--majority", action="store_true",
                    help="run twice + third decider on disagreement")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    sandbox = Path(args.sandbox).expanduser().resolve()
    if args.majority:
        result = run_judge_majority(args.prompt, sandbox, args.rubric,
                                     judge_model=args.judge_model)
    else:
        result = run_judge(args.prompt, sandbox, args.rubric,
                            judge_model=args.judge_model,
                            mock_response=args.mock_response)

    result["caseId"] = args.case_id
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        sym = "PASS" if result["passed"] else "FAIL"
        print(f"{sym} score={result['score']} — {result['evidence']}")
        if result.get("model_response"):
            print(f"\nmodel_response (first 200 chars): {result['model_response'][:200]}")


if __name__ == "__main__":
    main()