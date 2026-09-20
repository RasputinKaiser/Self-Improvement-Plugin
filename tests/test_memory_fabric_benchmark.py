from __future__ import annotations

import memory_fabric_benchmark
import json
import pytest


def test_public_benchmark_wrapper_runs_all_policy_scenarios(tmp_path):
    result = memory_fabric_benchmark.run_benchmark(tmp_path / "memory.jsonl")

    assert result["ok"] is True
    assert result["scenario_count"] == 77
    assert result["passed"] == 77
    assert result["failed"] == 0


@pytest.mark.parametrize("ok", [True, False])
@pytest.mark.parametrize("compact", [False, True])
def test_benchmark_cli_preserves_full_receipt_and_exit_status(
    tmp_path, monkeypatch, capsys, ok, compact
):
    impl = memory_fabric_benchmark.load_impl()
    result = {
        "ok": ok, "scenario_count": 1, "passed": int(ok), "failed": int(not ok),
        "results": [{"name": "scenario", "ok": ok,
                     "details": {"message": "keep  spaces\nand Unicode: λ", "values": [1, None, False]}}],
    }
    monkeypatch.setattr(impl, "run_benchmark", lambda store: result)
    monkeypatch.setattr(memory_fabric_benchmark, "load_impl", lambda: impl)
    receipt = tmp_path / "receipt.json"
    args = ["--output", str(receipt)] + (["--compact"] if compact else [])
    assert memory_fabric_benchmark.main(args) == (0 if ok else 1)
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == result
    pretty = json.dumps(result, indent=2, sort_keys=True) + "\n"
    assert receipt.read_text() == pretty
    if compact:
        assert stdout == json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
        assert len(stdout) < len(pretty)
    else:
        assert stdout == pretty
