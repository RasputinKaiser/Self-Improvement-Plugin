from __future__ import annotations

import memory_fabric_benchmark


def test_public_benchmark_wrapper_runs_all_policy_scenarios(tmp_path):
    result = memory_fabric_benchmark.run_benchmark(tmp_path / "memory.jsonl")

    assert result["ok"] is True
    assert result["scenario_count"] == 77
    assert result["passed"] == 77
    assert result["failed"] == 0
