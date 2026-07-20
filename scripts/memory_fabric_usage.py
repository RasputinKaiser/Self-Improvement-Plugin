from __future__ import annotations
from pathlib import Path
from typing import Any

from memory_fabric_usage_extract import collect_samples
from memory_fabric_usage_export import export_plugin_eval_jsonl
from memory_fabric_usage_quality import usage_quality
from memory_fabric_usage_tokens import token_averages, token_totals, token_totals_report


def usage_report(
    paths: list[str | Path] | None = None,
    inline_json: str = "",
    plugin_eval_output: str = "",
    min_samples: int = 5,
    min_scenarios: int = 3,
    allow_nonrepresentative_export: bool = False,
) -> dict[str, Any]:
    samples = collect_samples(paths or [], inline_json)
    totals = token_totals(samples)
    quality = usage_quality(samples, min_samples=min_samples, min_scenarios=min_scenarios)
    report = {
        "ok": True,
        "status": "observed_usage_available" if samples else "no_observed_usage",
        "fabricated": False,
        "sample_count": len(samples),
        "usage_quality": quality,
        "token_totals": token_totals_report(totals),
        "token_averages": token_totals_report(token_averages(totals, len(samples))),
        "sources": sorted({sample["source"] for sample in samples}),
        "samples": samples[:20],
        "claim_boundary": (
            "Only supplied JSON/JSONL token usage is counted. "
            "No samples means no observed usage."
        ),
    }
    if plugin_eval_output:
        report["plugin_eval_export"] = export_plugin_eval_jsonl(
            samples,
            plugin_eval_output,
            representative=quality["representative"],
            allow_nonrepresentative=allow_nonrepresentative_export,
        )
    return report
