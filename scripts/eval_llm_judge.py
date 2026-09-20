#!/usr/bin/env python3
"""Optional model-review result parser. No model subprocess is launched.

Mock responses are test-only; live review requires an explicit active-task action.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

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

    If mock_response is set, return immediately without launching a model.
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

    return {"score": None, "evidence": "Explicit active-task model review required; no model launched",
            "passed": False, "status": "unavailable", "model_response": "", "confidence": "low"}


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
                    help="mock a supplied judge response (for testing)")
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