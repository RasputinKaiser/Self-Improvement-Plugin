"""Bounded, indexed Memory Fabric graph retrieval.

The frontier deliberately reads records and relationships from the SQLite
projection only.  ``memory_fabric_graph_index.open_index_with_receipt`` is the
sole query path that refreshes from the append-only JSONL source and binds the
returned rows to one SQLite snapshot receipt.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from memory_fabric_graph_index import (
    edge_digest,
    open_index_with_receipt,
    scope_sql,
)
from memory_fabric_search_filters import record_confidence
from memory_fabric_schema import (
    normalize_confidence,
    normalize_provenance_type,
)


FRONTIER_SCHEMA = "memory.frontier.v1"
CLAIM_BOUNDARY = (
    "Indexed frontier links are deterministic retrieval context. They do not prove the claims "
    "in a memory record; verify source evidence before making strong claims."
)

_TERM_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_STRONG_PROVENANCE = {
    "repo_receipt",
    "source_backed_agent_run",
    "source_document",
    "source_file",
    "source_url",
    "user_instruction",
    "verified_command",
}
_EDGE_PRIORITY = {
    "alternative_to": 0,
    "blocked_by": 0,
    "caused_by": 0,
    "chosen_over": 0,
    "contradicts": 0,
    "decision_for": 0,
    "depends_on": 0,
    "evidence_for": 0,
    "fixes": 0,
    "proved_by": 0,
    "rejected_for": 0,
    "same_pattern_as": 0,
    "supersedes": 0,
    "tradeoff_with": 0,
    "shares_evidence": 1,
    "shares_tag": 2,
    "same_scope": 3,
}
_EXPLICIT_REASON = "explicit_marker"
_NODE_TOKEN_FIELDS = ("title", "body", "scope")
_NODE_TRUNCATION_PRIORITY = ("title", "scope", "body")
_RECORD_FIELDS = (
    "id",
    "tier",
    "title",
    "body",
    "scope",
    "tags",
    "status",
    "confidence",
    "verify_before_use",
    "provenance",
    "created_at",
)
MAX_SCOPE_CHARS = 512
MAX_QUERY_CHARS = 2_048
MAX_QUERY_TERMS = 64
MAX_RECORD_ID_CHARS = 256
MAX_PROVENANCE_TYPE_CHARS = 128
MAX_LEDGER_VALUE_CHARS = 256
MAX_EDGE_EVIDENCE_CHARS = 256
MAX_OMISSION_ITEMS = 32


def _bounded_text(value: Any, limit: int) -> tuple[str, dict[str, Any] | None]:
    """Return a collision-resistant compact representation of external text."""

    text = str(value or "")
    if len(text) <= limit:
        return text, None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    suffix = f"…#{digest[:16]}"
    compact = text[: max(0, limit - len(suffix))] + suffix
    return compact, {
        "original_length": len(text),
        "sha256": digest,
        "truncated": True,
    }


def _bounded_omission(
    record_id: Any,
    reason: str,
    *,
    provenance_type: Any = "",
    evidence_path: Any = "",
    token_estimate: int | None = None,
) -> dict[str, Any]:
    compact_id, id_truncation = _bounded_text(record_id, MAX_LEDGER_VALUE_CHARS)
    compact_type, type_truncation = _bounded_text(
        provenance_type, MAX_PROVENANCE_TYPE_CHARS
    )
    compact_path, path_truncation = _bounded_text(
        evidence_path, MAX_LEDGER_VALUE_CHARS
    )
    item: dict[str, Any] = {
        "id": compact_id,
        "reason": str(reason),
        "provenance": {
            "type": compact_type,
            "evidence_path": compact_path,
        },
    }
    truncation = {
        key: value
        for key, value in (
            ("id", id_truncation),
            ("provenance_type", type_truncation),
            ("evidence_path", path_truncation),
        )
        if value is not None
    }
    if truncation:
        item["field_truncation"] = truncation
    if token_estimate is not None:
        item["token_estimate"] = int(token_estimate)
    return item


def _terms(value: str) -> list[str]:
    return sorted({term.lower() for term in _TERM_RE.findall(str(value or "").lower()) if term})


def _base_eligible_clause(alias: str, include_untrusted: bool) -> str:
    current = (
        f"{alias}.status = 'active'"
        f" AND length({alias}.id) BETWEEN 1 AND {MAX_RECORD_ID_CHARS}"
        f" AND length({alias}.provenance_type) <= {MAX_PROVENANCE_TYPE_CHARS}"
    )
    if include_untrusted:
        return current
    return (
        current
        + f" AND {alias}.verify_before_use = 0"
        + f" AND {alias}.provenance_type IN ({','.join(repr(item) for item in sorted(_STRONG_PROVENANCE))})"
        + f" AND {alias}.confidence IN ('high', 'medium')"
    )


def _eligible_clause(alias: str = "r", include_untrusted: bool = False) -> str:
    current = _base_eligible_clause(alias, include_untrusted)
    superseder = _base_eligible_clause("superseder", include_untrusted)
    return (
        current
        + " AND NOT EXISTS ("
        "SELECT 1 FROM explicit_refs sx "
        "JOIN records superseder ON superseder.id = sx.source_id "
        f"WHERE sx.target_id = {alias}.id AND sx.edge_type = 'supersedes' "
        f"AND {superseder}"
        ")"
    )


def _filtered_eligible_clause(
    alias: str,
    include_untrusted: bool,
    record_filters: dict[str, Any] | None,
) -> tuple[str, list[Any]]:
    """Eligibility SQL with compatibility predicates applied before caps."""

    filters = dict(record_filters or {})

    def filter_clause(target: str) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if filters.get("confidence") is not None:
            clauses.append(f"lower({target}.confidence) = ?")
            params.append(filters["confidence"])
        if filters.get("provenance_type") is not None:
            clauses.append(f"lower({target}.provenance_type) = ?")
            params.append(filters["provenance_type"])
        if filters.get("verify_before_use") is not None:
            clauses.append(f"{target}.verify_before_use = ?")
            params.append(1 if filters["verify_before_use"] is True else 0)
        return (" AND " + " AND ".join(clauses) if clauses else "", params)

    current_filter, current_params = filter_clause(alias)
    current = _base_eligible_clause(alias, include_untrusted) + current_filter
    # Supersession is an authority relation, not a caller-visible record
    # filter.  A current high-confidence superseder must still hide a matching
    # low-confidence candidate, and vice versa.
    superseder = _base_eligible_clause("superseder", include_untrusted)
    return (
        current
        + " AND NOT EXISTS ("
        "SELECT 1 FROM explicit_refs sx "
        "JOIN records superseder ON superseder.id = sx.source_id "
        f"WHERE sx.target_id = {alias}.id AND sx.edge_type = 'supersedes' "
        f"AND {superseder}"
        ")",
        current_params,
    )


def _row_record(row: sqlite3.Row) -> dict[str, Any]:
    try:
        value = json.loads(str(row["raw"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    # The JSONL remains authoritative, but retrieval exposes only this compact
    # record contract. Unknown source fields cannot bypass the token bound.
    value = {key: value[key] for key in _RECORD_FIELDS if key in value}
    value["id"] = str(row["id"])
    value["tier"] = str(row["tier"])
    value["title"] = str(row["title"])
    value["body"] = str(row["body"])
    value["scope"] = str(row["scope"])
    value["status"] = str(row["status"])
    value["confidence"] = str(row["confidence"])
    value["verify_before_use"] = bool(row["verify_before_use"])
    value["created_at"] = str(row["created_at"])
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
        value["provenance"] = provenance
    provenance.setdefault("type", str(row["provenance_type"]))
    provenance.setdefault("evidence_path", str(row["evidence_path"]))
    return value


def _trust(record: dict[str, Any]) -> dict[str, Any]:
    provenance = str(record.get("provenance", {}).get("type", "")).strip().lower()
    confidence = str(record.get("confidence", "")).strip().lower()
    if str(record.get("status", "")).lower() != "active":
        return {"status": "not_current", "reasons": [f"status:{record.get('status', '')}"]}
    if bool(record.get("verify_before_use")):
        return {"status": "verify_before_use", "reasons": ["verify_before_use:true"]}
    if provenance in _STRONG_PROVENANCE and confidence == "high":
        return {"status": "ready", "reasons": ["strong_provenance", "confidence:high"]}
    if provenance in _STRONG_PROVENANCE and confidence == "medium":
        return {"status": "usable", "reasons": ["strong_provenance", "confidence:medium"]}
    return {"status": "context_only", "reasons": [f"provenance:{provenance or 'unknown'}"]}


def _node(row: sqlite3.Row, score: int = 0) -> dict[str, Any]:
    record = _row_record(row)
    trust = _trust(record)
    return {
        "id": str(row["id"]),
        "tier": str(row["tier"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "scope": str(row["scope"]),
        "tags": list(record.get("tags", [])) if isinstance(record.get("tags", []), list) else [],
        "status": str(row["status"]),
        "confidence": str(row["confidence"]),
        "provenance_type": str(row["provenance_type"]),
        "evidence_path": str(row["evidence_path"]),
        "verify_before_use": bool(row["verify_before_use"]),
        "created_at": str(row["created_at"]),
        "trust": trust,
        "score": int(score),
        "record": record,
    }


def _context_record(node: dict[str, Any]) -> dict[str, Any]:
    """Project a frontier node into the trust-bearing context contract."""
    record = dict(node.get("record", {}))
    record["trust"] = dict(node.get("trust", {}))
    provenance = (
        dict(record.get("provenance", {}))
        if isinstance(record.get("provenance"), dict)
        else {}
    )
    provenance.setdefault("type", str(node.get("provenance_type", "")))
    provenance.setdefault("evidence_path", str(node.get("evidence_path", "")))
    record["provenance"] = provenance
    return record


def _public_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return topology metadata without duplicating retrieved record text."""
    hidden = {"record", "title", "body", "scope", "tags", "evidence_path"}
    return {key: value for key, value in node.items() if key not in hidden}


def _node_tokens(node: dict[str, Any]) -> int:
    # Charge every byte-bearing field exposed in the retrieved record. Four
    # canonical-JSON characters per token is deterministic and provider-free.
    content = json.dumps(
        _context_record(node),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return max(1, math.ceil(len(content) / 4))


def _truncate_node_to_token_budget(node: dict[str, Any], token_budget: int) -> int:
    """Bound every field counted by ``_node_tokens`` and return its real estimate."""
    record = node.get("record")
    if not isinstance(record, dict):
        return _node_tokens(node)
    # Remove optional metadata before shortening source text. Identity, trust,
    # status, confidence, and provenance type remain explicit.
    for key in ("tags", "created_at", "tier"):
        record.pop(key, None)
    provenance = record.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("evidence_path", None)
    original = {field: str(node.get(field, "")) for field in _NODE_TOKEN_FIELDS}

    def apply_content(character_budget: int) -> None:
        allocations = {field: 0 for field in _NODE_TOKEN_FIELDS}
        active = [field for field in _NODE_TRUNCATION_PRIORITY if original[field]]
        remaining = max(0, character_budget)
        while active and remaining:
            share = max(1, remaining // len(active))
            for field in list(active):
                if not remaining:
                    break
                needed = len(original[field]) - allocations[field]
                granted = min(needed, share, remaining)
                allocations[field] += granted
                remaining -= granted
            active = [
                field
                for field in active
                if allocations[field] < len(original[field])
            ]
        for field in _NODE_TOKEN_FIELDS:
            bounded = original[field][: allocations[field]]
            node[field] = bounded
            record[field] = bounded

    low, high = 0, sum(len(value) for value in original.values())
    apply_content(0)
    if _node_tokens(node) > int(token_budget):
        return _node_tokens(node)
    while low < high:
        middle = (low + high + 1) // 2
        apply_content(middle)
        if _node_tokens(node) <= int(token_budget):
            low = middle
        else:
            high = middle - 1
    apply_content(low)
    truncated_fields: list[str] = []
    for field in _NODE_TOKEN_FIELDS:
        if str(node.get(field, "")) != original[field]:
            node[f"{field}_truncated"] = True
            truncated_fields.append(field)
    node["content_truncated"] = bool(truncated_fields)
    node["truncated_fields"] = truncated_fields
    return _node_tokens(node)


def _scope_sql(scope: str, alias: str = "r") -> tuple[str, tuple[str, ...]]:
    """Return the shared exact-or-nested scope predicate for indexed rows."""

    return scope_sql(scope, alias)


def _seed_rows(
    connection: sqlite3.Connection,
    *,
    scope: str,
    query: str,
    limit: int,
    include_untrusted: bool,
    record_filters: dict[str, Any] | None = None,
) -> list[sqlite3.Row]:
    terms = _terms(query)
    if not terms:
        return []
    placeholders = ",".join("?" for _ in terms)
    scope_sql, scope_params = _scope_sql(scope)
    eligible, eligible_params = _filtered_eligible_clause(
        "r", include_untrusted, record_filters
    )
    params: list[Any] = [
        *scope_params,
        *terms,
        *eligible_params,
        max(1, int(limit)),
    ]
    rows = connection.execute(
        f"""
        SELECT r.*, SUM(w.weight) AS score
        FROM records r
        JOIN weighted_terms w ON w.record_id = r.id
        WHERE {scope_sql}
          AND w.term IN ({placeholders})
          AND {eligible}
        GROUP BY r.id
        HAVING SUM(w.weight) > 0
        ORDER BY score DESC, r.created_at DESC, r.id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return list(rows)


def _eligible_neighbor(
    connection: sqlite3.Connection,
    *,
    current_id: str,
    include_untrusted: bool,
    mode: str,
    record_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    eligible, eligible_params = _filtered_eligible_clause(
        "r", include_untrusted, record_filters
    )
    rows: list[dict[str, Any]] = []
    if mode == "explicit":
        rows.extend(
            {
                "source": str(row["source_id"]),
                "target": str(row["target_id"]),
                "type": str(row["edge_type"]),
                "category": "explicit",
                "weight": 10,
                "reason": _EXPLICIT_REASON,
                "evidence": "",
            }
            for row in connection.execute(
                f"""
                SELECT x.source_id, x.target_id, x.edge_type
                FROM explicit_refs x JOIN records r ON r.id = x.target_id
                WHERE x.source_id = ? AND {eligible}
                UNION ALL
                SELECT x.source_id, x.target_id, x.edge_type
                FROM explicit_refs x JOIN records r ON r.id = x.source_id
                WHERE x.target_id = ? AND {eligible}
                ORDER BY edge_type, source_id, target_id
                """,
                (current_id, *eligible_params, current_id, *eligible_params),
            )
        )
    elif mode == "evidence":
        rows.extend(
            {
                "source": min(current_id, str(row["id"])),
                "target": max(current_id, str(row["id"])),
                "type": "shares_evidence",
                "edge_type": "",
                "weight": 4,
                "reason": "same_evidence_path",
                "evidence": str(row["path"]),
            }
            for row in connection.execute(
                f"""
                SELECT r.id, ep.path
                FROM evidence_paths mine
                JOIN evidence_paths ep ON ep.path = mine.path AND ep.record_id != mine.record_id
                JOIN records r ON r.id = ep.record_id
                WHERE mine.record_id = ? AND {eligible}
                ORDER BY r.id, ep.path
                """,
                (current_id, *eligible_params),
            )
        )
    elif mode == "tag":
        rows.extend(
            {
                "source": min(current_id, str(row["id"])),
                "target": max(current_id, str(row["id"])),
                "type": "shares_tag",
                "edge_type": "",
                "weight": 1 + int(row["shared_count"]),
                "reason": "shared_tags",
                "evidence": str(row["shared_tags"]),
            }
            for row in connection.execute(
                f"""
                SELECT r.id, COUNT(DISTINCT other.tag) AS shared_count,
                       GROUP_CONCAT(DISTINCT other.tag) AS shared_tags
                FROM tags mine
                JOIN tags other ON other.tag = mine.tag AND other.record_id != mine.record_id
                JOIN records r ON r.id = other.record_id
                WHERE mine.record_id = ? AND {eligible}
                GROUP BY r.id
                ORDER BY r.id
                """,
                (current_id, *eligible_params),
            )
        )
    elif mode == "scope":
        rows.extend(
            {
                "source": min(current_id, str(row["id"])),
                "target": max(current_id, str(row["id"])),
                "type": "same_scope",
                "edge_type": "",
                "weight": 2,
                "reason": "same_scope",
                "evidence": str(row["scope"]),
            }
            for row in connection.execute(
                f"""
                SELECT r.id, r.scope
                FROM records mine JOIN records r ON r.scope = mine.scope AND r.id != mine.id
                WHERE mine.id = ? AND mine.scope != '' AND mine.scope != 'global' AND {eligible}
                ORDER BY r.id
                """,
                (current_id, *eligible_params),
            )
        )
    return rows


def _neighbors(
    connection: sqlite3.Connection,
    current_id: str,
    include_untrusted: bool,
    record_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for mode in ("explicit", "evidence", "tag", "scope"):
        for candidate in _eligible_neighbor(
            connection,
            current_id=current_id,
            include_untrusted=include_untrusted,
            mode=mode,
            record_filters=record_filters,
        ):
            if candidate["source"] == candidate["target"]:
                continue
            key = (
                str(candidate["source"]),
                str(candidate["target"]),
                str(candidate["type"]),
                str(candidate.get("edge_type", "")),
            )
            old = candidates.get(key)
            if old is None or int(candidate["weight"]) > int(old["weight"]):
                candidates[key] = candidate
    result = list(candidates.values())
    for candidate in result:
        candidate["digest"] = edge_digest(
            candidate["source"],
            candidate["target"],
            candidate["type"],
            candidate.get("evidence", ""),
            candidate["weight"],
        )
    result.sort(key=_edge_sort_key)
    return result


def _edge_sort_key(edge: dict[str, Any]) -> tuple[int, int, str, str, str, str]:
    return (
        _EDGE_PRIORITY.get(str(edge.get("type", "")), 9),
        -int(edge.get("weight", 0)),
        str(edge.get("type", "")),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
        str(edge.get("digest", "")),
    )


def _public_edge(edge: dict[str, Any]) -> dict[str, Any]:
    evidence, evidence_truncation = _bounded_text(
        edge.get("evidence", ""), MAX_EDGE_EVIDENCE_CHARS
    )
    output = {
        "source": str(edge["source"]),
        "target": str(edge["target"]),
        "type": str(edge["type"]),
        "weight": int(edge["weight"]),
        "reason": str(edge.get("reason", "")),
        "evidence": evidence,
        "digest": str(edge["digest"]),
    }
    if evidence_truncation is not None:
        output["evidence_truncation"] = evidence_truncation
    if edge.get("category") == "explicit":
        output["category"] = "explicit"
    return output


def _response_token_accounting(response: dict[str, Any]) -> dict[str, Any]:
    """Attach exact, fixed-point accounting for the serialized envelope."""

    response["metadata_token_estimate"] = 0
    response["response_token_estimate"] = 0
    for _ in range(8):
        encoded = json.dumps(
            response,
            sort_keys=True,
            separators=(",", ":"),
            # Count the conservative JSON transport form.  UTF-8 canonical
            # writers may emit fewer bytes, while default JSON encoders escape
            # non-ASCII text such as truncation markers.
            ensure_ascii=True,
        )
        total = max(1, math.ceil(len(encoded) / 4))
        metadata = max(0, total - int(response.get("token_estimate", 0)))
        if (
            total == response["response_token_estimate"]
            and metadata == response["metadata_token_estimate"]
        ):
            break
        response["response_token_estimate"] = total
        response["metadata_token_estimate"] = metadata
    return response


def _empty_frontier(scope: str, query: str, store: Path, metadata: dict[str, Any], limits: dict[str, int]) -> dict[str, Any]:
    return _response_token_accounting({
        "ok": True,
        "schema": FRONTIER_SCHEMA,
        "status": "empty",
        "scope": scope,
        "query": query,
        "store": str(store),
        "source_of_truth": "append-only memory fabric JSONL store",
        "index": metadata.get("index", ""),
        "index_metadata": metadata,
        "claim_boundary": CLAIM_BOUNDARY,
        "limits": limits,
        "envelope_limits": {
            "scope_chars": MAX_SCOPE_CHARS,
            "query_chars": MAX_QUERY_CHARS,
            "query_terms": MAX_QUERY_TERMS,
            "record_id_chars": MAX_RECORD_ID_CHARS,
            "omission_items": MAX_OMISSION_ITEMS,
            "ledger_value_chars": MAX_LEDGER_VALUE_CHARS,
            "edge_evidence_chars": MAX_EDGE_EVIDENCE_CHARS,
        },
        "selected": {"seed_ids": [], "node_ids": [], "edge_digests": [], "path_count": 0},
        "selected_ids": [],
        "omitted": [],
        "omitted_ids": [],
        "omitted_reasons": {},
        "omission_summary": {"total": 0, "emitted": 0, "suppressed": 0, "by_reason": {}},
        "nodes": [],
        "records": [],
        "edges": [],
        "paths": [],
        "truncated": False,
        "truncation": {},
        "token_estimate": 0,
        "token_budget": limits["token_budget"],
        "node_count": 0,
        "edge_count": 0,
        "path_count": 0,
    })


def query_frontier(
    *,
    scope: str,
    query: str,
    store: str | Path | None = None,
    include_untrusted: bool = False,
    seed_limit: int = 8,
    fanout: int = 4,
    max_depth: int = 2,
    max_nodes: int = 24,
    max_edges: int = 80,
    max_paths: int = 8,
    token_budget: int = 4000,
    _record_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic bounded graph frontier from indexed joins."""

    if not isinstance(scope, str) or not isinstance(query, str):
        raise TypeError("scope and query must be strings")
    if type(include_untrusted) is not bool:
        raise TypeError("include_untrusted must be a boolean")
    if _record_filters is not None and not isinstance(_record_filters, dict):
        raise TypeError("_record_filters must be an object")
    record_filters = dict(_record_filters or {})
    unknown_filters = sorted(
        set(record_filters)
        - {"confidence", "provenance_type", "verify_before_use"}
    )
    if unknown_filters:
        raise ValueError("unknown record filters: " + ", ".join(unknown_filters))
    numeric = {
        "seed_limit": seed_limit,
        "fanout": fanout,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "max_edges": max_edges,
        "max_paths": max_paths,
        "token_budget": token_budget,
    }
    for name, value in numeric.items():
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer")
        minimum = 0 if name == "max_depth" else 1
        if value < minimum:
            raise ValueError(f"{name} must be at least {minimum}")
    # Preserve caller-facing spelling; matching canonicalizes independently.
    clean_scope, clean_query = scope.strip(), query.strip()
    if not clean_scope:
        raise ValueError("scope is required for a bounded memory frontier query")
    if not clean_query:
        raise ValueError("query is required for a bounded memory frontier query")
    if len(clean_scope) > MAX_SCOPE_CHARS:
        raise ValueError(f"scope exceeds {MAX_SCOPE_CHARS} characters")
    if len(clean_query) > MAX_QUERY_CHARS:
        raise ValueError(f"query exceeds {MAX_QUERY_CHARS} characters")
    if len(_terms(clean_query)) > MAX_QUERY_TERMS:
        raise ValueError(f"query exceeds {MAX_QUERY_TERMS} unique terms")
    limits = {
        "seed_limit": min(8, seed_limit),
        "fanout": min(4, fanout),
        "max_depth": min(2, max_depth),
        "max_nodes": min(24, max_nodes),
        "max_edges": min(80, max_edges),
        "max_paths": min(8, max_paths),
        "token_budget": min(4_000, token_budget),
    }
    source = Path(store or (Path.home() / ".codex" / "memory-fabric" / "memory.jsonl")).expanduser().resolve()
    # Rows and receipt must come from one SQLite read snapshot.  A second
    # ensure/open pair can otherwise advance the index between calls and make
    # the selected evidence newer than the advertised source offset.
    connection, metadata = open_index_with_receipt(source)
    try:
        seeds = _seed_rows(
            connection,
            scope=clean_scope,
            query=clean_query,
            limit=limits["seed_limit"],
            include_untrusted=bool(include_untrusted),
            record_filters=record_filters,
        )
        if not seeds:
            return _empty_frontier(clean_scope, clean_query, source, metadata, limits)

        selected: dict[str, dict[str, Any]] = {}
        seed_ids: list[str] = []
        omitted: list[dict[str, Any]] = []
        omission_reason_counts: dict[str, int] = defaultdict(int)
        omission_total = 0
        used_tokens = 0

        def add_row(row: sqlite3.Row, score: int = 0, *, seed: bool = False) -> bool:
            nonlocal omission_total, used_tokens
            record_id = str(row["id"])
            def omit(reason: str, estimate: int | None = None) -> None:
                nonlocal omission_total
                omission_total += 1
                omission_reason_counts[reason] += 1
                if len(omitted) >= MAX_OMISSION_ITEMS:
                    return
                omitted.append(
                    _bounded_omission(
                        record_id,
                        reason,
                        provenance_type=row["provenance_type"],
                        evidence_path=row["evidence_path"],
                        token_estimate=estimate,
                    )
                )
            if record_id in selected:
                return True
            if len(selected) >= limits["max_nodes"]:
                omit("max_nodes")
                return False
            node = _node(row, score)
            estimate = _node_tokens(node)
            if used_tokens + estimate > limits["token_budget"]:
                # Keep a bounded first-seed stub while charging the actual
                # estimate of every field counted by the retrieval budget.
                if seed and not selected:
                    estimate = _truncate_node_to_token_budget(node, limits["token_budget"])
                    if estimate > limits["token_budget"]:
                        omit("token_budget", estimate)
                        return False
                else:
                    omit("token_budget", estimate)
                    return False
            node["token_estimate"] = int(estimate)
            selected[record_id] = node
            used_tokens += int(estimate)
            if seed:
                seed_ids.append(record_id)
            return True

        for row in seeds:
            add_row(row, int(row["score"]), seed=True)

        edges_by_digest: dict[str, dict[str, Any]] = {}
        fanout_limited = False
        depth_limited = False
        edge_limited = False
        parent_path: dict[str, tuple[list[str], list[str]]] = {
            item: ([item], []) for item in seed_ids
        }
        discovery_path: dict[str, tuple[list[str], list[str]]] = {}
        queue: deque[tuple[str, int]] = deque((item, 0) for item in seed_ids)
        while queue and len(edges_by_digest) < limits["max_edges"]:
            current_id, depth = queue.popleft()
            if depth >= limits["max_depth"]:
                depth_limited = True
                continue
            candidates = _neighbors(
                connection,
                current_id,
                bool(include_untrusted),
                record_filters,
            )
            if len(candidates) > limits["fanout"]:
                fanout_limited = True
            for candidate in candidates[: limits["fanout"]]:
                if len(edges_by_digest) >= limits["max_edges"]:
                    edge_limited = True
                    break
                neighbor = (
                    str(candidate["target"])
                    if str(candidate["source"]) == current_id
                    else str(candidate["source"])
                )
                # The node row is indexed; no source-store read occurs here.
                row = connection.execute("SELECT * FROM records WHERE id = ?", (neighbor,)).fetchone()
                if row is None:
                    continue
                digest = str(candidate["digest"])
                if neighbor not in selected:
                    if not add_row(row, 0):
                        continue
                    queue.append((neighbor, depth + 1))
                    base_path = parent_path.get(current_id, ([current_id], []))
                    # Keep the complete deterministic path to each newly
                    # discovered node.  Omitting the parent edge here makes
                    # multi-hop paths under-report their edge digests.
                    parent_path[neighbor] = (
                        base_path[0] + [neighbor],
                        base_path[1] + [digest],
                    )
                    discovery_path[digest] = parent_path[neighbor]
                if digest not in edges_by_digest:
                    edges_by_digest[digest] = candidate
        public_edges = [_public_edge(item) for item in sorted(edges_by_digest.values(), key=_edge_sort_key)]

        paths: list[dict[str, Any]] = []
        for edge in public_edges:
            source_id, target_id = edge["source"], edge["target"]
            discovered = discovery_path.get(str(edge["digest"]))
            if discovered is not None:
                path_nodes, path_edges = discovered
            elif source_id in parent_path:
                path_nodes, path_edges = parent_path[source_id]
                path_nodes = path_nodes + ([target_id] if target_id != path_nodes[-1] else [])
                path_edges = [*path_edges, edge["digest"]]
            elif target_id in parent_path:
                path_nodes, path_edges = parent_path[target_id]
                path_nodes = path_nodes + ([source_id] if source_id != path_nodes[-1] else [])
                path_edges = [*path_edges, edge["digest"]]
            else:
                path_nodes, path_edges = [source_id, target_id], [edge["digest"]]
            paths.append(
                {
                    "nodes": path_nodes,
                    "edges": path_edges,
                    "score": int(edge["weight"]),
                    "edge_type": edge["type"],
                }
            )
        paths.sort(key=lambda item: (-int(item["score"]), len(item["nodes"]), tuple(item["nodes"]), tuple(item["edges"])))
        paths = paths[: limits["max_paths"]]
        omitted_ids = sorted({item["id"] for item in omitted})
        omitted_reasons = {item: sorted({entry["reason"] for entry in omitted if entry["id"] == item}) for item in omitted_ids}
        admitted_content_truncated = any(
            node.get("content_truncated") is True for node in selected.values()
        )
        truncation = {
            "nodes": omission_reason_counts.get("max_nodes", 0) > 0,
            "tokens": admitted_content_truncated
            or omission_reason_counts.get("token_budget", 0) > 0,
            "edges": edge_limited,
            "paths": len(public_edges) > limits["max_paths"],
            "depth": depth_limited or bool(queue),
            "fanout": fanout_limited,
            "edge_budget": edge_limited,
        }
        nodes = [selected[item] for item in [*seed_ids, *selected.keys()] if item in selected]
        # Preserve first-seen deterministic order while removing duplicate seeds.
        seen_nodes: set[str] = set()
        nodes = [node for node in nodes if not (node["id"] in seen_nodes or seen_nodes.add(node["id"]))]
        return _response_token_accounting({
            "ok": True,
            "schema": FRONTIER_SCHEMA,
            "status": "ready" if nodes else "empty",
            "scope": clean_scope,
            "query": clean_query,
            "store": str(source),
            "source_of_truth": "append-only memory fabric JSONL store",
            "index": metadata.get("index", ""),
            "index_metadata": metadata,
            "claim_boundary": CLAIM_BOUNDARY,
            "limits": limits,
            "envelope_limits": {
                "scope_chars": MAX_SCOPE_CHARS,
                "query_chars": MAX_QUERY_CHARS,
                "query_terms": MAX_QUERY_TERMS,
                "record_id_chars": MAX_RECORD_ID_CHARS,
                "omission_items": MAX_OMISSION_ITEMS,
                "ledger_value_chars": MAX_LEDGER_VALUE_CHARS,
                "edge_evidence_chars": MAX_EDGE_EVIDENCE_CHARS,
            },
            "selected": {
                "seed_ids": seed_ids,
                "node_ids": [node["id"] for node in nodes],
                "edge_digests": [edge["digest"] for edge in public_edges],
                "path_count": len(paths),
            },
            "selected_ids": [node["id"] for node in nodes],
            "omitted": omitted,
            "omitted_ids": omitted_ids,
            "omitted_reasons": omitted_reasons,
            "omission_summary": {
                "total": omission_total,
                "emitted": len(omitted),
                "suppressed": max(0, omission_total - len(omitted)),
                "by_reason": dict(sorted(omission_reason_counts.items())),
            },
            "nodes": [_public_node(node) for node in nodes],
            "records": [_context_record(node) for node in nodes],
            "edges": public_edges,
            "paths": paths,
            "truncated": any(truncation.values()),
            "truncation": truncation,
            "token_estimate": int(used_tokens),
            "token_budget": limits["token_budget"],
            "node_count": len(nodes),
            "edge_count": len(public_edges),
            "path_count": len(paths),
        })
    finally:
        connection.close()


def compatibility_graph(
    scope: str = "",
    query: str = "",
    status: str = "active",
    confidence: str = "",
    provenance_type: str = "",
    verify_before_use: str = "",
    max_nodes: int = 24,
    max_edges: int = 80,
    path: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Adapter shaped like ``memory_fabric_graph.memory_graph``.

    It intentionally preserves the old empty-input behavior (a structured
    attention response) while valid calls use the indexed frontier.  Existing
    graph modules can wire this adapter later without changing their imports.
    """

    # The indexed frontier deliberately supports only the active view.  Do
    # not coerce an unsupported status and silently return a different graph.
    requested_status = _compatibility_status(status)
    requested_confidence = _compatibility_confidence(confidence)
    requested_provenance = _compatibility_provenance(provenance_type)
    requested_verify = _compatibility_verify(verify_before_use)

    if not str(scope or "").strip() or not str(query or "").strip():
        return {
            "ok": False,
            "schema": FRONTIER_SCHEMA,
            "status": "scope_and_query_required",
            "scope": scope or None,
            "query": query or None,
            "nodes": [],
            "edges": [],
            "paths": [],
            "claim_boundary": CLAIM_BOUNDARY,
            "compatibility": {
                "status": requested_status,
                "confidence": confidence,
                "provenance_type": provenance_type,
                "verify_before_use": verify_before_use,
                "applied_filters": _compatibility_filter_metadata(
                    requested_status,
                    requested_confidence,
                    requested_provenance,
                    requested_verify,
                ),
            },
        }

    requested_include_untrusted = kwargs.get("include_untrusted", False)
    if type(requested_include_untrusted) is not bool:
        raise TypeError("include_untrusted must be a boolean")
    # Explicit filters may intentionally select records outside the default
    # trusted subset.  Retrieve the active superset and apply every requested
    # filter below, rather than coercing a filter into a retrieval hint.
    has_explicit_filter = any(
        value is not None
        for value in (requested_confidence, requested_provenance, requested_verify)
    )
    include_untrusted = bool(requested_include_untrusted or has_explicit_filter)
    result = query_frontier(
        scope=str(scope),
        query=str(query),
        store=path,
        include_untrusted=include_untrusted,
        seed_limit=int(kwargs.get("seed_limit", 8)),
        fanout=int(kwargs.get("fanout", 4)),
        max_depth=int(kwargs.get("max_depth", 2)),
        max_nodes=int(max_nodes),
        max_edges=int(max_edges),
        max_paths=int(kwargs.get("max_paths", 8)),
        token_budget=int(kwargs.get("token_budget", 4000)),
        _record_filters={
            "confidence": requested_confidence,
            "provenance_type": requested_provenance,
            "verify_before_use": requested_verify,
        },
    )

    # ``query_frontier`` returns compact topology plus trust-bearing records.
    # Filter the records and all graph projections by stable ID so confidence,
    # provenance, and verify_before_use can never be silently ignored.
    records = [
        record
        for record in result.get("records", [])
        if _compatibility_record_matches(
            record,
            confidence=requested_confidence,
            provenance_type=requested_provenance,
            verify_before_use=requested_verify,
        )
    ]
    allowed_ids = {str(record.get("id", "")) for record in records}
    result["records"] = records
    result["nodes"] = [
        node for node in result.get("nodes", []) if str(node.get("id", "")) in allowed_ids
    ]
    result["edges"] = [
        edge
        for edge in result.get("edges", [])
        if str(edge.get("source", "")) in allowed_ids
        and str(edge.get("target", "")) in allowed_ids
    ]
    result["paths"] = [
        path_item
        for path_item in result.get("paths", [])
        if all(str(node_id) in allowed_ids for node_id in path_item.get("nodes", []))
    ]
    result["selected_ids"] = [str(record.get("id", "")) for record in records]
    selected = result.get("selected")
    if isinstance(selected, dict):
        selected["node_ids"] = list(result["selected_ids"])
        selected["seed_ids"] = [
            item for item in selected.get("seed_ids", []) if str(item) in allowed_ids
        ]
        selected["edge_digests"] = [
            str(edge.get("digest", "")) for edge in result["edges"]
        ]
        selected["path_count"] = len(result["paths"])
    result["node_count"] = len(result["nodes"])
    result["edge_count"] = len(result["edges"])
    result["path_count"] = len(result["paths"])
    result["status"] = "ready" if result["node_count"] else "empty"
    # A post-filtered response cannot claim the pre-filter token charge.
    result["token_estimate"] = sum(
        int(node.get("token_estimate", 0)) for node in result["nodes"]
    )
    result["compatibility"] = {
        "status": requested_status,
        "confidence": confidence,
        "provenance_type": provenance_type,
        "verify_before_use": verify_before_use,
        "applied_filters": _compatibility_filter_metadata(
            requested_status,
            requested_confidence,
            requested_provenance,
            requested_verify,
        ),
        "include_untrusted_for_filtering": include_untrusted,
    }
    return _response_token_accounting(result)


def _compatibility_status(value: str | None) -> str:
    """Validate the legacy status argument without broadening frontier scope."""

    if value is None:
        return "active"
    if not isinstance(value, str):
        raise TypeError("status must be a string")
    normalized = value.strip().lower() or "active"
    if normalized == "current":
        normalized = "active"
    if normalized != "active":
        raise ValueError("compatibility_graph supports status=active only")
    return normalized


def _compatibility_confidence(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("confidence must be a string")
    normalized = value.strip()
    return normalize_confidence(normalized) if normalized else None


def _compatibility_provenance(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("provenance_type must be a string")
    normalized = value.strip()
    return normalize_provenance_type(normalized) if normalized else None


def _compatibility_verify(value: str | bool | None) -> bool | None:
    if value is None or value == "":
        return None
    if type(value) is bool:
        return value
    if not isinstance(value, str):
        raise TypeError("verify_before_use must be a boolean or true/false string")
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise ValueError("verify_before_use expects true/false")


def _compatibility_record_matches(
    record: dict[str, Any],
    *,
    confidence: str | None,
    provenance_type: str | None,
    verify_before_use: bool | None,
) -> bool:
    if confidence is not None and record_confidence(record) != confidence:
        return False
    provenance = record.get("provenance", {})
    actual_provenance = provenance.get("type", "") if isinstance(provenance, dict) else ""
    if provenance_type is not None and str(actual_provenance).strip().lower() != provenance_type:
        return False
    if verify_before_use is not None and bool(record.get("verify_before_use")) is not verify_before_use:
        return False
    return str(record.get("status", "")).strip().lower() == "active"


def _compatibility_filter_metadata(
    status: str,
    confidence: str | None,
    provenance_type: str | None,
    verify_before_use: bool | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "confidence": confidence,
        "provenance_type": provenance_type,
        "verify_before_use": verify_before_use,
        "all_filters_enforced": True,
    }


memory_frontier = query_frontier
indexed_frontier = query_frontier
frontier = query_frontier


__all__ = [
    "FRONTIER_SCHEMA",
    "CLAIM_BOUNDARY",
    "compatibility_graph",
    "frontier",
    "indexed_frontier",
    "memory_frontier",
    "query_frontier",
]
