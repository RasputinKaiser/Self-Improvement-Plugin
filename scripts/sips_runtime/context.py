"""Bounded, trust-aware context packet construction for graph runs.

The runtime deliberately treats context as a projection.  Records that are
not trustworthy are retained in the omission ledger, never silently promoted
to evidence.  The returned mapping is intentionally JSON serialisable so it
can be included in a handoff or a receipt without a second conversion pass.
"""
from __future__ import annotations

import json
import hashlib
import itertools
import re
from typing import Any, Iterable, Mapping, Sequence

from memory_fabric_graph_index import scope_contains


DEFAULT_MAX_RECORDS = 8
DEFAULT_MAX_TOKENS = 4_000
MAX_CONTEXT_CANDIDATES = 256
MAX_CONTEXT_ID_CHARS = 256
MAX_CONTEXT_SCOPE_CHARS = 512
MAX_CONTEXT_QUERY_CHARS = 2_048
MAX_CONTEXT_QUERY_TERMS = 64
MAX_CONTEXT_REQUIRED_SOURCES = 64
MAX_CONTEXT_OMISSIONS = 32
MAX_LEDGER_VALUE_CHARS = 256
MAX_PROVENANCE_CHARS = 1_024
MAX_TASK_TEXT_CHARS = 8_192
MAX_TASK_LIST_ITEMS = 64
MAX_ACCEPTANCE_ITEMS = 32
MAX_ACCEPTANCE_ITEM_CHARS = 2_048
_TRUST_EXCLUDED = {
    "untrusted",
    "rejected",
    "invalid",
    "context_only",
    "context-only",
    "stale",
    "superseded",
    "revoked",
    "verify",
    "verify_before_use",
    "screen_observation",
    "openchronicle",
    "live_ui",
    "cache_state",
}


def _bounded_text(value: Any, limit: int) -> tuple[str, dict[str, Any] | None]:
    text = str(value or "")
    if len(text) <= limit:
        return text, None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    suffix = f"…#{digest[:16]}"
    return text[: max(0, limit - len(suffix))] + suffix, {
        "original_length": len(text),
        "sha256": digest,
        "truncated": True,
    }


def _bounded_provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    provenance = dict(value or {})
    try:
        encoded = json.dumps(
            provenance,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        encoded = repr(provenance)
    if len(encoded) <= MAX_PROVENANCE_CHARS:
        return provenance
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    preview, _ = _bounded_text(encoded, MAX_LEDGER_VALUE_CHARS)
    return {
        "preview": preview,
        "original_length": len(encoded),
        "sha256": digest,
        "truncated": True,
    }


def _bounded_json_value(value: Any, limit: int) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        encoded = repr(value)
    if len(encoded) <= limit:
        return value
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    preview, _ = _bounded_text(encoded, min(limit, MAX_LEDGER_VALUE_CHARS))
    return {
        "preview": preview,
        "original_length": len(encoded),
        "sha256": digest,
        "truncated": True,
    }


def _task_context_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    """Project only task fields needed by a worker context packet."""

    output: dict[str, Any] = {}
    truncation: dict[str, Any] = {}
    for field in ("id", "task_id", "objective", "description"):
        if field not in task:
            continue
        maximum = MAX_CONTEXT_ID_CHARS if field in {"id", "task_id"} else MAX_TASK_TEXT_CHARS
        output[field], detail = _bounded_text(task.get(field, ""), maximum)
        if detail is not None:
            truncation[field] = detail
    for field in ("read_set", "write_set", "risk_tags", "required_sources"):
        raw = task.get(field, ())
        if not isinstance(raw, (list, tuple)):
            raw = (raw,)
        values = []
        for item in raw[:MAX_TASK_LIST_ITEMS]:
            compact, _ = _bounded_text(item, MAX_LEDGER_VALUE_CHARS)
            values.append(compact)
        if values:
            output[field] = values
        if len(raw) > MAX_TASK_LIST_ITEMS:
            truncation[field] = {
                "original_count": len(raw),
                "emitted_count": MAX_TASK_LIST_ITEMS,
                "truncated": True,
            }
    if truncation:
        output["field_truncation"] = truncation
    return output


def _response_token_accounting(packet: dict[str, Any]) -> dict[str, Any]:
    packet["metadata_token_estimate"] = 0
    packet["response_token_estimate"] = 0
    for _ in range(8):
        encoded = json.dumps(
            packet,
            sort_keys=True,
            # Charge the conservative transport form used by default JSON
            # encoders; canonical UTF-8 output can only be smaller.
            ensure_ascii=True,
            separators=(",", ":"),
        )
        total = max(1, (len(encoded) + 3) // 4)
        metadata = max(0, total - int(packet.get("estimated_tokens", 0)))
        if (
            total == packet["response_token_estimate"]
            and metadata == packet["metadata_token_estimate"]
        ):
            break
        packet["response_token_estimate"] = total
        packet["metadata_token_estimate"] = metadata
    return packet


def _as_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "to_dict"):
        value = record.to_dict()
        return dict(value) if isinstance(value, Mapping) else {"value": value}
    if hasattr(record, "model_dump"):
        value = record.model_dump()
        return dict(value) if isinstance(value, Mapping) else {"value": value}
    if hasattr(record, "__dict__"):
        return dict(vars(record))
    return {"value": record}


def _record_id(record: Mapping[str, Any], index: int) -> str:
    for key in ("id", "record_id", "source_id", "artifact_id", "key"):
        value = record.get(key)
        if value is not None and str(value):
            return str(value)
    return f"record-{index + 1}"


def _scope_value(record: Mapping[str, Any]) -> str:
    scope = record.get("scope", record.get("scopes", ""))
    if isinstance(scope, (list, tuple, set)):
        return " ".join(map(str, scope))
    return str(scope or "")


def _trust_value(record: Mapping[str, Any]) -> str:
    trust = record.get("trust", record.get("trust_status", ""))
    if isinstance(trust, Mapping):
        trust = trust.get("status", trust.get("level", ""))
    status = str(record.get("status", "")).strip().lower()
    if status in _TRUST_EXCLUDED:
        return status
    provenance = record.get("provenance", {})
    if isinstance(provenance, Mapping):
        provenance = provenance.get("type", provenance.get("status", ""))
    provenance_label = str(provenance or "").strip().lower()
    if provenance_label in _TRUST_EXCLUDED:
        return provenance_label
    if trust:
        return str(trust).strip().lower()
    return provenance_label or "untrusted"


def _trust_ready(record: Mapping[str, Any]) -> bool:
    """Require active, non-superseded, usable records by default."""
    if not _provenance(record):
        return False
    status = str(record.get("status", "active")).strip().lower()
    if status not in {"active", "ready", "usable", "trusted"}:
        return False
    if record.get("superseded", False) is not False or record.get("superseded_by"):
        return False
    if record.get("verify_before_use", False) is not False:
        return False
    confidence = str(record.get("confidence", "")).strip().lower()
    if confidence and confidence not in {"high", "medium", "ready", "usable", "verified"}:
        return False
    trust = record.get("trust", record.get("trust_status", ""))
    if isinstance(trust, Mapping):
        trust = trust.get("status", trust.get("level", ""))
    if trust and str(trust).strip().lower() not in {"active", "ready", "usable", "trusted", "verified", "strong"}:
        return False
    return True


def _provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    value = record.get("provenance", record.get("source", {}))
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": value} if value else {}


def _required(record: Mapping[str, Any], required: set[str]) -> bool:
    rid = str(record.get("id", record.get("record_id", record.get("source_id", ""))))
    return bool(record.get("required", False) or record.get("is_required", False) or rid in required)


def _matches_query(record: Mapping[str, Any], query: str) -> bool:
    if not query.strip():
        return True
    haystack = " ".join(
        str(record.get(key, ""))
        for key in ("id", "title", "name", "text", "body", "summary", "scope", "tags", "claim")
    ).lower()
    # Scoped queries may contain a simple ``scope:foo terms`` prefix.  The
    # scope itself is handled by build_context_packet; only match terms here.
    terms = [term for term in re.findall(r"[\w.-]+", query.lower()) if not term.startswith("scope:")]
    return all(term in haystack for term in terms)


def _matches_scope(record: Mapping[str, Any], scope: str) -> bool:
    if not scope.strip():
        return True
    raw_scope = record.get("scope", record.get("scopes", ""))
    return scope_contains(raw_scope, scope)


def _estimate_tokens(value: Any) -> int:
    # A stable conservative estimate; no tokenizer dependency belongs in the
    # runtime.  Four UTF-8-ish characters per token tracks normal prose well.
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return max(1, (len(encoded) + 3) // 4)


def _compact(record: Mapping[str, Any], index: int) -> dict[str, Any]:
    result = dict(record)
    result.setdefault("id", _record_id(record, index))
    result.setdefault("provenance", _provenance(record))
    result.setdefault("trust", _trust_value(record))
    return result


def _text_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = (value,)
    return tuple(
        sorted(
            {
                str(item).strip().lower()
                for item in values
                if str(item).strip()
            }
        )
    )


def _diversity_facets(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Return stable, non-identity facets for deterministic context diversity."""
    facets: set[str] = set()
    for value in re.split(r"[,/\s]+", _scope_value(record)):
        if value.strip():
            compact, _ = _bounded_text(value.strip().lower(), MAX_LEDGER_VALUE_CHARS)
            facets.add(f"scope:{compact}")
    for value in _text_values(record.get("tags")):
        compact, _ = _bounded_text(value, MAX_LEDGER_VALUE_CHARS)
        facets.add(f"tag:{compact}")
    provenance = _provenance(record)
    for key in ("type", "kind", "source", "origin", "system"):
        for value in _text_values(provenance.get(key)):
            compact, _ = _bounded_text(value, MAX_LEDGER_VALUE_CHARS)
            facets.add(f"provenance:{key}:{compact}")
    for key in ("evidence_path", "evidence_paths"):
        for value in _text_values(record.get(key)):
            compact, _ = _bounded_text(value, MAX_LEDGER_VALUE_CHARS)
            facets.add(f"evidence:{compact}")
    return tuple(sorted(facets))


def build_context_packet(
    records: Iterable[Any] = (),
    *,
    task: Any = None,
    task_scope: str = "",
    acceptance_criteria: Sequence[Any] | None = None,
    required_sources: Sequence[str] | None = None,
    required: Sequence[str] | None = None,
    scope: str = "",
    query: str = "",
    max_records: int = DEFAULT_MAX_RECORDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    excluded_trust: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, bounded context packet.

    ``required_sources`` and ``required`` are accepted as aliases for callers
    migrating from the graph design notes.  Required records are ordered before
    optional records, but are subject to the same trust, record and token caps.
    Every skipped record receives an explicit reason and provenance summary.
    """
    for name, value in (
        ("task_scope", task_scope),
        ("scope", scope),
        ("query", query),
    ):
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
    if type(max_records) is not int or type(max_tokens) is not int:
        raise TypeError("max_records and max_tokens must be integers")
    max_records = min(DEFAULT_MAX_RECORDS, max(0, max_records))
    max_tokens = min(DEFAULT_MAX_TOKENS, max(0, max_tokens))
    candidate_records = list(
        itertools.islice(iter(records), MAX_CONTEXT_CANDIDATES + 1)
    )
    candidate_input_truncated = len(candidate_records) > MAX_CONTEXT_CANDIDATES
    records = candidate_records[:MAX_CONTEXT_CANDIDATES]
    task_data = _as_dict(task) if task is not None else {}
    if task_data:
        task_metadata = task_data.get("metadata", {})
        if not isinstance(task_metadata, Mapping):
            task_metadata = {}
        scope = scope or task_scope or str(
            task_data.get(
                "scope",
                task_data.get("task_scope", task_metadata.get("scope", "")),
            )
        )
        query = query or str(task_data.get("context_query", "") or "")
        task_required = task_data.get("required_sources", ())
    elif task_scope:
        scope = task_scope
    else:
        task_required = ()
    required_values = tuple(required_sources or required or task_required or ())
    if len(required_values) > MAX_CONTEXT_REQUIRED_SOURCES:
        raise ValueError(
            f"required sources exceed {MAX_CONTEXT_REQUIRED_SOURCES} items"
        )
    required_ids = {
        str(value.get("id", value) if isinstance(value, Mapping) else value)
        for value in required_values
    }
    if any(not item or len(item) > MAX_CONTEXT_ID_CHARS for item in required_ids):
        raise ValueError(
            f"required source IDs must be 1-{MAX_CONTEXT_ID_CHARS} characters"
        )
    excluded = {str(value).strip().lower() for value in (excluded_trust or _TRUST_EXCLUDED)}

    # ``scope:foo`` is a query prefix in the CLI/API.  Parse it once so the
    # scope filter and provenance remain explicit in the returned packet.
    query_scope_match = re.search(r"(?:^|\s)scope:([^\s]+)", query, flags=re.IGNORECASE)
    if query_scope_match:
        scope = scope or query_scope_match.group(1)
        query = re.sub(r"(?:^|\s)scope:[^\s]+", " ", query, flags=re.IGNORECASE).strip()
    if len(scope) > MAX_CONTEXT_SCOPE_CHARS:
        raise ValueError(f"scope exceeds {MAX_CONTEXT_SCOPE_CHARS} characters")
    if len(query) > MAX_CONTEXT_QUERY_CHARS:
        raise ValueError(f"query exceeds {MAX_CONTEXT_QUERY_CHARS} characters")
    if len(set(re.findall(r"[\w.-]+", query.lower()))) > MAX_CONTEXT_QUERY_TERMS:
        raise ValueError(f"query exceeds {MAX_CONTEXT_QUERY_TERMS} unique terms")
    if query.strip() and not scope.strip():
        return _response_token_accounting({
            "ok": False,
            "error": "scope_required_for_query",
            "scope": None,
            "query": query,
            "limits": {"max_records": max_records, "max_tokens": max_tokens},
            "envelope_limits": {
                "candidate_records": MAX_CONTEXT_CANDIDATES,
                "scope_chars": MAX_CONTEXT_SCOPE_CHARS,
                "query_chars": MAX_CONTEXT_QUERY_CHARS,
                "query_terms": MAX_CONTEXT_QUERY_TERMS,
                "omission_items": MAX_CONTEXT_OMISSIONS,
            },
            "records": [], "selected": [], "selected_ids": [],
            "omitted": [], "omitted_ids": [], "selected_provenance": [], "omitted_provenance": [],
            "diversity": {"strategy": "greedy_new_facets_v1", "selected_facets": []},
            "estimated_tokens": 0, "record_count": 0, "omitted_count": 0,
            "input_truncated": candidate_input_truncated,
        })
    # Broad scans are unsafe context selection.  An explicit required-source
    # list is the only no-query exception, and it selects those ids exclusively.
    if not query.strip() and not scope.strip() and not required_ids and records:
        return _response_token_accounting({
            "ok": False,
            "error": "query_or_required_sources_required",
            "scope": None,
            "query": None,
            "limits": {"max_records": max_records, "max_tokens": max_tokens},
            "envelope_limits": {
                "candidate_records": MAX_CONTEXT_CANDIDATES,
                "scope_chars": MAX_CONTEXT_SCOPE_CHARS,
                "query_chars": MAX_CONTEXT_QUERY_CHARS,
                "query_terms": MAX_CONTEXT_QUERY_TERMS,
                "omission_items": MAX_CONTEXT_OMISSIONS,
            },
            "records": [], "selected": [], "selected_ids": [],
            "omitted": [], "omitted_ids": [], "selected_provenance": [], "omitted_provenance": [],
            "diversity": {"strategy": "greedy_new_facets_v1", "selected_facets": []},
            "estimated_tokens": 0, "record_count": 0, "omitted_count": 0,
            "input_truncated": candidate_input_truncated,
        })

    normalized: list[tuple[int, dict[str, Any]]] = []
    omissions: list[dict[str, Any]] = []
    omission_reason_counts: dict[str, int] = {}
    omission_total = 0

    def omit(record_id: Any, reason: str, provenance: Mapping[str, Any] | None = None) -> None:
        nonlocal omission_total
        omission_total += 1
        omission_reason_counts[reason] = omission_reason_counts.get(reason, 0) + 1
        if len(omissions) >= MAX_CONTEXT_OMISSIONS:
            return
        compact_id, id_truncation = _bounded_text(
            record_id, MAX_LEDGER_VALUE_CHARS
        )
        item: dict[str, Any] = {
            "id": compact_id,
            "reason": reason,
            "provenance": _bounded_provenance(provenance),
        }
        if id_truncation is not None:
            item["id_truncation"] = id_truncation
        omissions.append(item)

    if candidate_input_truncated:
        omit("candidate-overflow", "candidate_cap", {})
    seen_ids: set[str] = set()
    for index, raw in enumerate(records):
        record = _compact(_as_dict(raw), index)
        rid = str(record["id"])
        provenance = _provenance(record)
        if not rid or len(rid) > MAX_CONTEXT_ID_CHARS:
            omit(rid, "identifier_invalid", provenance)
            continue
        if rid in seen_ids:
            omit(rid, "duplicate", provenance)
            continue
        seen_ids.add(rid)
        if required_ids and not query.strip() and not scope.strip() and rid not in required_ids:
            omit(rid, "not_required_source", provenance)
            continue
        if _trust_value(record) in excluded:
            omit(rid, "trust_excluded", provenance)
            continue
        if not _trust_ready(record):
            omit(rid, "trust_not_ready", provenance)
            continue
        if not _matches_scope(record, scope):
            omit(rid, "scope_mismatch", provenance)
            continue
        if not _required(record, required_ids) and not _matches_query(record, query):
            omit(rid, "query_mismatch", provenance)
            continue
        normalized.append((index, record))

    available_ids = {str(record["id"]) for _, record in normalized}
    for missing_id in sorted(required_ids - available_ids):
        if not any(item.get("id") == missing_id for item in omissions):
            omit(missing_id, "required_source_missing", {})

    # Required sources are considered first. Optional records are then chosen
    # greedily by how many new scope/tag/provenance/evidence facets they add.
    # Stable ids make the packet invariant to input arrival order.
    required_items = sorted(
        (item for item in normalized if _required(item[1], required_ids)),
        key=lambda item: (str(item[1]["id"]), item[0]),
    )
    optional_items = [item for item in normalized if not _required(item[1], required_ids)]
    selected: list[dict[str, Any]] = []
    selected_tokens = 0
    selected_facets: set[str] = set()

    def consider(record: dict[str, Any]) -> None:
        nonlocal selected_tokens
        rid = str(record["id"])
        if len(selected) >= max_records:
            omit(rid, "record_cap", _provenance(record))
            return
        cost = _estimate_tokens(record)
        if selected_tokens + cost > max_tokens:
            omit(rid, "token_cap", _provenance(record))
            return
        selected.append(record)
        selected_tokens += cost
        selected_facets.update(_diversity_facets(record))

    for _, record in required_items:
        consider(record)

    while optional_items:
        optional_items.sort(
            key=lambda item: (
                -len(set(_diversity_facets(item[1])) - selected_facets),
                str(item[1]["id"]),
                item[0],
            )
        )
        _, record = optional_items.pop(0)
        consider(record)

    raw_acceptance: Any = (
        acceptance_criteria
        if acceptance_criteria is not None
        else task_data.get("acceptance", ())
    )
    if isinstance(raw_acceptance, (str, bytes)):
        raw_acceptance = (raw_acceptance,)
    else:
        raw_acceptance = tuple(raw_acceptance or ())
    projected_acceptance = [
        _bounded_json_value(item, MAX_ACCEPTANCE_ITEM_CHARS)
        for item in raw_acceptance[:MAX_ACCEPTANCE_ITEMS]
    ]
    packet = {
        "ok": True,
        "error": None,
        "required_sources_unavailable": [],
        "scope": scope or None,
        "query": query or None,
        "task": _task_context_projection(task_data),
        "acceptance_criteria": projected_acceptance,
        "acceptance_truncation": {
            "original_count": len(raw_acceptance),
            "emitted_count": len(projected_acceptance),
            "truncated": len(raw_acceptance) > len(projected_acceptance),
        },
        "limits": {"max_records": max_records, "max_tokens": max_tokens},
        "envelope_limits": {
            "candidate_records": MAX_CONTEXT_CANDIDATES,
            "record_id_chars": MAX_CONTEXT_ID_CHARS,
            "scope_chars": MAX_CONTEXT_SCOPE_CHARS,
            "query_chars": MAX_CONTEXT_QUERY_CHARS,
            "query_terms": MAX_CONTEXT_QUERY_TERMS,
            "required_sources": MAX_CONTEXT_REQUIRED_SOURCES,
            "omission_items": MAX_CONTEXT_OMISSIONS,
            "task_text_chars": MAX_TASK_TEXT_CHARS,
            "acceptance_items": MAX_ACCEPTANCE_ITEMS,
            "acceptance_item_chars": MAX_ACCEPTANCE_ITEM_CHARS,
        },
        "records": selected,
        # Compatibility identity projection without duplicating every record
        # body in the serialized worker handoff.
        "selected": [],
        "selected_ids": [],
        "omitted": omissions,
        "omitted_ids": [],
        "selected_provenance": [],
        "omitted_provenance": [],
        "omission_summary": {},
        "diversity": {
            "strategy": "greedy_new_facets_v1",
            "selected_facets": sorted(selected_facets),
        },
        "estimated_tokens": 0,
        "record_count": 0,
        "omitted_count": 0,
        "input_truncated": candidate_input_truncated,
    }

    def refresh_packet() -> None:
        nonlocal selected_tokens, selected_facets
        selected_tokens = sum(_estimate_tokens(record) for record in selected)
        selected_facets = {
            facet for record in selected for facet in _diversity_facets(record)
        }
        selected_ids = {str(record["id"]) for record in selected}
        unavailable_required = sorted(required_ids - selected_ids)
        omissions.sort(key=lambda item: (str(item.get("id", "")), str(item.get("reason", ""))))
        packet.update(
            {
                "ok": not unavailable_required,
                "error": (
                    "required_sources_unavailable"
                    if unavailable_required
                    else None
                ),
                "required_sources_unavailable": unavailable_required,
                "records": selected,
                "selected": sorted(selected_ids),
                "selected_ids": sorted(selected_ids),
                "omitted": omissions,
                "omitted_ids": sorted(
                    {str(item["id"]) for item in omissions}
                ),
                "selected_provenance": [
                    {
                        "id": str(record["id"]),
                        "provenance": _bounded_provenance(_provenance(record)),
                    }
                    for record in selected
                ],
                # Provenance is already attached to each omission.  Keep this
                # compatibility projection identity-only to avoid duplicating
                # arbitrarily large source metadata.
                "omitted_provenance": [
                    {"id": str(item["id"])} for item in omissions
                ],
                "omission_summary": {
                    "total": omission_total,
                    "emitted": len(omissions),
                    "suppressed": max(0, omission_total - len(omissions)),
                    "by_reason": dict(sorted(omission_reason_counts.items())),
                },
                "diversity": {
                    "strategy": "greedy_new_facets_v1",
                    "selected_facets": sorted(selected_facets),
                },
                "estimated_tokens": selected_tokens,
                "record_count": len(selected),
                "omitted_count": omission_total,
            }
        )
        _response_token_accounting(packet)

    refresh_packet()
    # The enforceable retrieval reservation covers the exact serialized worker
    # context, not just source record bodies.  Shed optional records first,
    # then representative omission details; required records removed by this
    # cap make the packet fail closed.
    while packet["response_token_estimate"] > max_tokens and selected:
        removed = selected.pop()
        omit(str(removed["id"]), "packet_token_cap", _provenance(removed))
        refresh_packet()
    while packet["response_token_estimate"] > max_tokens and omissions:
        omissions.pop()
        refresh_packet()
    if packet["response_token_estimate"] > max_tokens:
        packet["ok"] = False
        packet["error"] = "context_packet_exceeds_token_limit"
        _response_token_accounting(packet)
    return packet


# Short aliases used by integrations and the CLI.
context_packet = build_context_packet
select_context = build_context_packet


def account_context_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Refresh serialized envelope accounting after a controller projection."""

    return _response_token_accounting(packet)


__all__ = [
    "ContextPacket",
    "account_context_packet",
    "build_context_packet",
    "context_packet",
    "select_context",
]


class ContextPacket(dict):
    """Typed convenience wrapper; ``build_context_packet`` returns a mapping."""

    @classmethod
    def from_records(cls, records: Iterable[Any], **kwargs: Any) -> "ContextPacket":
        return cls(build_context_packet(records, **kwargs))
