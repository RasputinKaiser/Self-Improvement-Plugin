from __future__ import annotations
from memory_fabric_usage_tokens import valid_usage


def usage_candidates(payload: dict) -> list[tuple[str, dict, str]]:
    candidates = []
    add_usage(candidates, "usage", payload.get("usage"), metadata_scenario(payload))
    response = payload.get("response")
    if isinstance(response, dict):
        add_usage(candidates, "response.usage", response.get("usage"), scenario_for(response, payload))
    data = payload.get("data")
    if isinstance(data, dict):
        add_usage(candidates, "data.usage", data.get("usage"), scenario_for(data, payload))
        add_nested_response(candidates, data)
    add_codex_token_count(candidates, payload)
    return candidates


def add_nested_response(candidates: list, data: dict) -> None:
    nested = data.get("response")
    if isinstance(nested, dict):
        add_usage(candidates, "data.response.usage", nested.get("usage"), scenario_for(nested, data))


def add_codex_token_count(candidates: list, payload: dict) -> None:
    event_payload = payload.get("payload")
    if payload.get("type") != "event_msg" or not isinstance(event_payload, dict):
        return
    if event_payload.get("type") != "token_count":
        return
    info = event_payload.get("info")
    if isinstance(info, dict):
        add_usage(candidates, "codex.token_count.last", info.get("last_token_usage"), "codex-rollout-token-count")


def add_usage(candidates: list, kind: str, usage, scenario: str = "") -> None:
    if valid_usage(usage):
        candidates.append((kind, usage, scenario))


def scenario_for(primary: dict, fallback: dict) -> str:
    return metadata_scenario(primary) or metadata_scenario(fallback)


def metadata_scenario(payload: dict) -> str:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("scenario") or "").strip()
    return str(payload.get("scenario") or "").strip()
