from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def export_plugin_eval_jsonl(
    samples: list[dict[str, Any]],
    output: str | Path,
    representative: bool = True,
    allow_nonrepresentative: bool = False,
) -> dict[str, Any]:
    target = Path(output).expanduser().resolve()
    if not samples:
        return {
            "ok": False,
            "status": "skipped_no_observed_samples",
            "output": str(target),
            "sample_count": 0,
            "reason": "Plugin Eval treats provided usage files as measured telemetry; no file was written.",
        }
    if not representative and not allow_nonrepresentative:
        return {
            "ok": False,
            "status": "skipped_nonrepresentative_usage",
            "output": str(target),
            "sample_count": len(samples),
            "representative": False,
            "reason": "Use --allow-nonrepresentative-export only for explicitly labeled gauge runs.",
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for index, sample in enumerate(samples, start=1):
            handle.write(json.dumps(plugin_eval_event(sample, index), sort_keys=True) + "\n")
    return {
        "ok": True,
        "status": "exported",
        "output": str(target),
        "sample_count": len(samples),
        "format": "plugin_eval_response_done_jsonl",
        "representative": representative,
        "nonrepresentative_override": bool(allow_nonrepresentative and not representative),
    }


def plugin_eval_event(sample: dict[str, Any], index: int) -> dict[str, Any]:
    usage = {
        "input_tokens": int(sample.get("input_tokens", 0)),
        "output_tokens": int(sample.get("output_tokens", 0)),
        "total_tokens": int(sample.get("total_tokens", 0)),
    }
    return {
        "type": "response.done",
        "response": {
            "id": f"memory-fabric-usage-{index}",
            "metadata": {"scenario": sample.get("kind", "usage")},
            "usage": usage,
        },
        "metadata": {
            "source": sample.get("source", ""),
            "generated_by": "codex-memory-fabric",
        },
    }
