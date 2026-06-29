#!/usr/bin/env python3
"""eval_grader_parity.py — golden vectors proving Python grader == Swift grader.

Loads golden test cases and asserts the Python grader's output matches the
expected (score, passed) computed from the Swift EvalGrader's documented
behavior. If this test fails, the two implementations have drifted and the
weekly sweep's eval results are unreliable.

The golden vectors live in references/eval_grader_golden.json. Each vector:
{
  "id": "vector-1",
  "check": {"kind": "fileExists", "arguments": {"path": "hello.txt"}, "weight": 1.0},
  "sandboxFiles": {"hello.txt": "hello world"},
  "toolSequence": ["Read", "Write"],
  "expected": {"score": 1.0, "passed": true, "evidence_contains": "exists"}
}

Run via run_tests.py — eval_parity suite.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
# Golden vectors live in the plugin source tree at references/eval_grader_golden.json.
# This script may run from ~/.ncode/scripts/ (installed) or from the source repo.
# Try both: the plugin install root, then the source repo root.
GOLDEN_PATHS = [
    SCRIPTS_DIR.parent / "references" / "eval_grader_golden.json",       # source repo
    Path.home() / ".ncode/plugins/marketplaces/harness-local/references/eval_grader_golden.json",  # installed
]


def _find_golden_path():
    for p in GOLDEN_PATHS:
        if p.exists():
            return p
    return None


def load_golden_vectors():
    """Load the golden test vectors. Returns list of dicts."""
    path = _find_golden_path()
    if path is None:
        return []
    return json.loads(path.read_text())


def run_parity_test():
    """Run each golden vector through the Python grader and assert parity.

    Returns (passed_count, failed_vectors). Caller asserts all pass.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    # Import the grader from eval_harness.py (the Python mirror)
    import eval_harness as eh

    vectors = load_golden_vectors()
    if not vectors:
        print("SKIP: no golden vectors found at", GOLDEN_PATH)
        return 0, []

    passed = 0
    failed = []
    for v in vectors:
        with tempfile.TemporaryDirectory() as sandbox:
            sandbox_path = Path(sandbox)
            # Seed sandbox files
            for filename, content in v.get("sandboxFiles", {}).items():
                (sandbox_path / filename).write_text(content)

            check = v["check"]
            tool_sequence = v.get("toolSequence", [])
            results, score = eh.grade([check], sandbox_path, tool_sequence)
            result = results[0] if results else {"score": 0, "passed": False, "evidence": "(no result)"}

            expected = v["expected"]
            ok = (
                abs(result["score"] - expected["score"]) < 0.001
                and result["passed"] == expected["passed"]
            )
            if expected.get("evidence_contains"):
                ok = ok and expected["evidence_contains"] in result["evidence"]

            if ok:
                passed += 1
            else:
                failed.append({
                    "id": v["id"],
                    "expected": expected,
                    "actual": {"score": result["score"], "passed": result["passed"],
                               "evidence": result["evidence"]},
                })

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_parity_test()
    total = passed + len(failed)
    print(f"Parity: {passed}/{total} vectors pass")
    for f in failed:
        print(f"  FAIL {f['id']}: expected={f['expected']}, actual={f['actual']}")
    sys.exit(0 if not failed else 1)