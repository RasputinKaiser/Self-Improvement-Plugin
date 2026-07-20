from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from memory_fabric_usage_candidates import usage_candidates
from memory_fabric_usage_tokens import sample_from_usage


def collect_samples(paths: list[str | Path], inline_json: str = "") -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if inline_json.strip():
        samples.extend(samples_from_payload(json.loads(inline_json), "inline_json"))
    for raw_path in filter(None, map(str, paths)):
        samples.extend(samples_from_path(Path(raw_path).expanduser()))
    return samples


def samples_from_path(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return samples_from_jsonl(text, str(path))
    try:
        return samples_from_payload(json.loads(text), str(path))
    except json.JSONDecodeError:
        return samples_from_jsonl(text, str(path))


def samples_from_jsonl(text: str, source: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        samples.extend(samples_from_payload(payload, f"{source}:{line_no}"))
    return samples


def samples_from_payload(payload: Any, source: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        samples: list[dict[str, Any]] = []
        for index, item in enumerate(payload):
            samples.extend(samples_from_payload(item, f"{source}[{index}]"))
        return samples
    if not isinstance(payload, dict):
        return []
    candidates = usage_candidates(payload)
    samples = []
    for kind, usage, scenario in candidates:
        sample = sample_from_usage(usage, source, kind)
        if scenario:
            sample["scenario"] = scenario
        add_sample_metadata(sample, payload)
        samples.append(sample)
    return samples


def add_sample_metadata(sample: dict[str, Any], payload: dict[str, Any]) -> None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return
    for key in ["plugin", "tool", "isolation", "plugin_isolated"]:
        if key in metadata:
            sample[key] = metadata[key]
