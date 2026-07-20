"""An incremental SQLite projection for the append-only Memory Fabric store.

The JSONL file remains authoritative.  This module only maintains a rebuildable,
read-optimized sidecar used by the bounded frontier runtime.  Nothing in the
sidecar is required for reading or appending the source store.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

import fcntl


INDEX_SCHEMA = "graph-index-v1"
INDEX_CONTRACT_VERSION = "2"
INDEX_SUFFIX = ".graph-index-v1.sqlite3"
PREFIX_BYTES = 4096
FINGERPRINT_CHUNK_BYTES = 1024 * 1024

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}

_TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_EXPLICIT_RE = re.compile(
    r"\b(alternative\s+to|blocked\s+by|caused\s+by|chosen\s+over|"
    r"decision\s+for|same\s+pattern\s+as|tradeoff\s+with|rejected\s+for|"
    r"proved\s+by|blocks|contradicts|depends\s+on|evidence\s+for|"
    r"fixes|supersedes)\s*:\s*([^\s;]+(?:\s*,\s*[^\s;]+)*)",
    re.IGNORECASE,
)
_EXPLICIT_LABELS = {
    "alternative to": "alternative_to",
    "blocked by": "blocked_by",
    "caused by": "caused_by",
    "chosen over": "chosen_over",
    "decision for": "decision_for",
    "same pattern as": "same_pattern_as",
    "tradeoff with": "tradeoff_with",
    "rejected for": "rejected_for",
    "proved by": "proved_by",
    "blocks": "blocks",
    "contradicts": "contradicts",
    "depends on": "depends_on",
    "evidence for": "evidence_for",
    "fixes": "fixes",
    "supersedes": "supersedes",
}

# The sidecar is rebuildable, so trusting a caller-writable schema marker is
# unnecessary risk.  Keep a concrete structural contract and rebuild whenever
# any table, view, foreign key, or query-critical index drifts from it.
_REQUIRED_COLUMNS: dict[str, tuple[tuple[str, str, int, int], ...]] = {
    "meta": (
        ("key", "TEXT", 0, 1),
        ("value", "TEXT", 1, 0),
    ),
    "records": (
        ("id", "TEXT", 0, 1),
        ("line_no", "INTEGER", 1, 0),
        ("offset", "INTEGER", 1, 0),
        ("end_offset", "INTEGER", 1, 0),
        ("raw", "TEXT", 1, 0),
        ("schema_version", "TEXT", 1, 0),
        ("tier", "TEXT", 1, 0),
        ("title", "TEXT", 1, 0),
        ("body", "TEXT", 1, 0),
        ("scope", "TEXT", 1, 0),
        ("status", "TEXT", 1, 0),
        ("confidence", "TEXT", 1, 0),
        ("verify_before_use", "INTEGER", 1, 0),
        ("provenance_type", "TEXT", 1, 0),
        ("evidence_path", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "weighted_terms": (
        ("record_id", "TEXT", 1, 1),
        ("term", "TEXT", 1, 2),
        ("field", "TEXT", 1, 3),
        ("weight", "INTEGER", 1, 0),
    ),
    "tags": (
        ("record_id", "TEXT", 1, 1),
        ("tag", "TEXT", 1, 2),
    ),
    "evidence_paths": (
        ("record_id", "TEXT", 1, 1),
        ("path", "TEXT", 1, 2),
    ),
    "explicit_refs": (
        ("source_id", "TEXT", 1, 1),
        ("target_id", "TEXT", 1, 2),
        ("edge_type", "TEXT", 1, 3),
    ),
}
_TERMS_VIEW_COLUMNS = (
    ("record_id", "TEXT"),
    ("term", "TEXT"),
    ("field", "TEXT"),
    ("weight", "INTEGER"),
)
_TERMS_VIEW_SQL = "CREATE VIEW terms AS SELECT record_id, term, field, weight FROM weighted_terms"
_REQUIRED_FOREIGN_KEYS = {
    "weighted_terms": (("records", "record_id", "id", "NO ACTION", "CASCADE", "NONE"),),
    "tags": (("records", "record_id", "id", "NO ACTION", "CASCADE", "NONE"),),
    "evidence_paths": (("records", "record_id", "id", "NO ACTION", "CASCADE", "NONE"),),
    "meta": (),
    "records": (),
    "explicit_refs": (),
}
_REQUIRED_INDEXES: dict[str, tuple[str, tuple[tuple[str, int], ...]]] = {
    "records_scope_idx": ("records", (("scope", 0),)),
    "scope_idx": ("records", (("scope", 0),)),
    "records_status_idx": ("records", (("status", 0),)),
    "records_trust_idx": (
        "records",
        (("provenance_type", 0), ("confidence", 0), ("verify_before_use", 0)),
    ),
    "weighted_terms_term_idx": (
        "weighted_terms",
        (("term", 0), ("weight", 1), ("record_id", 0)),
    ),
    "weighted_terms_record_idx": ("weighted_terms", (("record_id", 0),)),
    "tags_tag_idx": ("tags", (("tag", 0), ("record_id", 0))),
    "evidence_paths_path_idx": ("evidence_paths", (("path", 0), ("record_id", 0))),
    "explicit_refs_source_idx": (
        "explicit_refs",
        (("source_id", 0), ("edge_type", 0), ("target_id", 0)),
    ),
    "explicit_refs_target_idx": (
        "explicit_refs",
        (("target_id", 0), ("edge_type", 0), ("source_id", 0)),
    ),
}


def normalize_scope(scope: object) -> str:
    """Return the canonical scope spelling used by context and SQL filters.

    Scopes are path-like identifiers, not bags of components.  Only outer
    whitespace, case, and a trailing separator are normalized; separators in
    the middle remain meaningful hierarchy boundaries.
    """

    return str(scope or "").strip().lower().rstrip("/")


def scope_contains(candidate_scope: object, requested_scope: object) -> bool:
    """Whether *candidate_scope* is the requested scope or one of its children.

    The explicit boundary prevents substring collisions (for example,
    ``project/foo`` must not match ``unrelated-project/foo-evil``).  Collection
    values are supported as a list of complete scope paths; their components
    are never intersected independently.
    """

    wanted = normalize_scope(requested_scope)
    if not wanted:
        return True
    if isinstance(candidate_scope, (list, tuple, set, frozenset)):
        candidates = candidate_scope
    else:
        candidates = (candidate_scope,)
    return any(
        (candidate := normalize_scope(value)) == wanted or candidate.startswith(f"{wanted}/")
        for value in candidates
    )


def scope_sql(scope: object, alias: str = "r") -> tuple[str, tuple[str, ...]]:
    """Build the SQL predicate implementing :func:`scope_contains`.

    ``substr`` is used instead of ``LIKE`` so user scope text cannot introduce
    wildcard semantics.  The normalized column expression mirrors
    :func:`normalize_scope` for indexed rows.
    """

    wanted = normalize_scope(scope)
    if not wanted:
        return "1 = 1", ()
    column = f"lower(rtrim(trim({alias}.scope), '/'))"
    return (
        f"({column} = ? OR substr({column}, 1, length(?) + 1) = ?)",
        (wanted, wanted, f"{wanted}/"),
    )


def index_path(store: str | Path, index_path: str | Path | None = None) -> Path:
    """Return the sidecar path for *store*.

    ``index_path`` is intentionally injectable for tests and future migrations;
    production callers get ``<store>.graph-index-v1.sqlite3``.
    """

    if index_path is not None:
        return Path(index_path).expanduser().resolve()
    source = Path(store).expanduser().resolve()
    return Path(f"{source}{INDEX_SUFFIX}")


def sidecar_path(store: str | Path, index_path: str | Path | None = None) -> Path:
    return index_path_for(store, index_path)


def index_path_for(store: str | Path, index_path: str | Path | None = None) -> Path:
    return index_path if index_path is not None else Path(f"{Path(store).expanduser().resolve()}{INDEX_SUFFIX}")


def _source_path(store: str | Path) -> Path:
    return Path(store).expanduser().resolve()


def _process_lock(path: Path) -> threading.Lock:
    """Return the in-process lock corresponding to a sidecar lock path.

    ``flock`` coordinates independent processes, but an explicit thread lock
    also makes same-process callers deterministic on platforms whose flock
    implementation treats locks as process-owned.
    """

    key = str(path.expanduser().resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.Lock())


@contextmanager
def _sidecar_lock(target: Path):
    """Serialize all ensure/rebuild operations for one SQLite sidecar."""

    target = target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{target}.lock")
    process_lock = _process_lock(lock_path)
    with process_lock:
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _prefix_fingerprint(path: Path, length: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = PREFIX_BYTES if length is None else max(0, int(length))
    try:
        with path.open("rb") as handle:
            while remaining:
                chunk = handle.read(min(remaining, FINGERPRINT_CHUNK_BYTES))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
    except FileNotFoundError:
        return hashlib.sha256(b"").hexdigest()
    return digest.hexdigest()


def _source_meta(path: Path, *, offset: int = 0, line_no: int = 0) -> dict[str, str]:
    try:
        stat = path.stat()
        values: dict[str, str] = {
            "device": str(stat.st_dev),
            "inode": str(stat.st_ino),
            "size": str(stat.st_size),
            "mtime_ns": str(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
            "offset": str(int(offset)),
            "line_no": str(int(line_no)),
            "prefix_fingerprint": _prefix_fingerprint(path),
            "prefix_length": str(min(int(stat.st_size), PREFIX_BYTES)),
            "indexed_prefix_fingerprint": _prefix_fingerprint(path, offset),
            "indexed_prefix_length": str(int(offset)),
            "prefix_bytes": str(PREFIX_BYTES),
            "mtime": str(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
        }
    except FileNotFoundError:
        values = {
            "device": "",
            "inode": "",
            "size": "0",
            "mtime_ns": "0",
            "offset": str(int(offset)),
            "line_no": str(int(line_no)),
            "prefix_fingerprint": hashlib.sha256(b"").hexdigest(),
            "prefix_length": "0",
            "indexed_prefix_fingerprint": hashlib.sha256(b"").hexdigest(),
            "indexed_prefix_length": str(int(offset)),
            "prefix_bytes": str(PREFIX_BYTES),
            "mtime": "0",
        }
    values["schema"] = INDEX_SCHEMA
    values["contract_version"] = INDEX_CONTRACT_VERSION
    # Keep explicit source-prefixed aliases in the metadata receipt.  They
    # make the proof boundary self-describing while the short keys remain
    # convenient for SQL-side checks.
    values.update(
        {
            "source_device": values["device"],
            "source_inode": values["inode"],
            "source_size": values["size"],
            "source_mtime": values["mtime_ns"],
            "source_offset": values["offset"],
            "source_prefix_fingerprint": values["prefix_fingerprint"],
            "source_indexed_prefix_fingerprint": values["indexed_prefix_fingerprint"],
            "source_indexed_prefix_length": values["indexed_prefix_length"],
        }
    )
    return values


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            line_no INTEGER NOT NULL,
            offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            raw TEXT NOT NULL,
            schema_version TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            confidence TEXT NOT NULL DEFAULT '',
            verify_before_use INTEGER NOT NULL DEFAULT 0,
            provenance_type TEXT NOT NULL DEFAULT '',
            evidence_path TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS weighted_terms (
            record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            term TEXT NOT NULL,
            field TEXT NOT NULL,
            weight INTEGER NOT NULL,
            PRIMARY KEY(record_id, term, field)
        );
        CREATE TABLE IF NOT EXISTS tags (
            record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            PRIMARY KEY(record_id, tag)
        );
        CREATE TABLE IF NOT EXISTS evidence_paths (
            record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            PRIMARY KEY(record_id, path)
        );
        CREATE TABLE IF NOT EXISTS explicit_refs (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            PRIMARY KEY(source_id, target_id, edge_type)
        );
        CREATE INDEX IF NOT EXISTS records_scope_idx ON records(scope);
        CREATE INDEX IF NOT EXISTS scope_idx ON records(scope);
        CREATE INDEX IF NOT EXISTS records_status_idx ON records(status);
        CREATE INDEX IF NOT EXISTS records_trust_idx ON records(provenance_type, confidence, verify_before_use);
        CREATE INDEX IF NOT EXISTS weighted_terms_term_idx ON weighted_terms(term, weight DESC, record_id);
        CREATE INDEX IF NOT EXISTS weighted_terms_record_idx ON weighted_terms(record_id);
        CREATE INDEX IF NOT EXISTS tags_tag_idx ON tags(tag, record_id);
        CREATE INDEX IF NOT EXISTS evidence_paths_path_idx ON evidence_paths(path, record_id);
        CREATE INDEX IF NOT EXISTS explicit_refs_source_idx ON explicit_refs(source_id, edge_type, target_id);
        CREATE INDEX IF NOT EXISTS explicit_refs_target_idx ON explicit_refs(target_id, edge_type, source_id);
        CREATE VIEW IF NOT EXISTS terms AS SELECT record_id, term, field, weight FROM weighted_terms;
        """
    )


def _get_meta(connection: sqlite3.Connection) -> dict[str, str]:
    return {str(row["key"]): str(row["value"]) for row in connection.execute("SELECT key, value FROM meta")}


def _schema_is_usable(connection: sqlite3.Connection) -> bool:
    try:
        objects = {
            str(row["name"]): str(row["type"])
            for row in connection.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view', 'index')"
            )
        }
        if any(objects.get(name) != "table" for name in _REQUIRED_COLUMNS):
            return False
        if objects.get("terms") != "view":
            return False

        for table, expected in _REQUIRED_COLUMNS.items():
            actual = tuple(
                (
                    str(row["name"]),
                    str(row["type"]).upper(),
                    int(row["notnull"]),
                    int(row["pk"]),
                )
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            )
            if actual != expected:
                return False

        view_columns = tuple(
            (str(row["name"]), str(row["type"]).upper())
            for row in connection.execute('PRAGMA table_info("terms")')
        )
        if view_columns != _TERMS_VIEW_COLUMNS:
            return False
        view_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name='terms'"
        ).fetchone()
        normalize_sql = lambda value: " ".join(str(value or "").split()).lower()
        if not view_row or normalize_sql(view_row[0]) != normalize_sql(_TERMS_VIEW_SQL):
            return False

        for table, expected in _REQUIRED_FOREIGN_KEYS.items():
            actual = tuple(
                sorted(
                    (
                        str(row["table"]),
                        str(row["from"]),
                        str(row["to"]),
                        str(row["on_update"]).upper(),
                        str(row["on_delete"]).upper(),
                        str(row["match"]).upper(),
                    )
                    for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')
                )
            )
            if actual != expected:
                return False

        for index_name, (table, expected_columns) in _REQUIRED_INDEXES.items():
            index_rows = {
                str(row["name"]): row
                for row in connection.execute(f'PRAGMA index_list("{table}")')
            }
            index_row = index_rows.get(index_name)
            if (
                index_row is None
                or int(index_row["unique"]) != 0
                or str(index_row["origin"]) != "c"
                or int(index_row["partial"]) != 0
            ):
                return False
            actual_columns = tuple(
                (str(row["name"]), int(row["desc"]))
                for row in connection.execute(f'PRAGMA index_xinfo("{index_name}")')
                if int(row["key"]) == 1
            )
            if actual_columns != expected_columns:
                return False

        meta = _get_meta(connection)
        if (
            meta.get("schema") != INDEX_SCHEMA
            or meta.get("contract_version") != INDEX_CONTRACT_VERSION
        ):
            return False
        # These fields are used for source identity and receipt binding.  A
        # malformed value is corruption, not a zero or an unchanged index.
        for key in (
            "device",
            "inode",
            "size",
            "mtime_ns",
            "offset",
            "line_no",
            "indexed_prefix_length",
            "invalid_lines",
        ):
            if int(meta[key]) < 0:
                return False
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            return False
        result = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(result and str(result[0]).lower() == "ok")
    except (KeyError, TypeError, ValueError, sqlite3.DatabaseError):
        return False


def _read_index_meta_connection(
    connection: sqlite3.Connection, path: Path
) -> dict[str, Any]:
    try:
        if not _schema_is_usable(connection):
            return {
                "ok": False,
                "index": str(path),
                "error": "InvalidSchema",
                "detail": "graph index schema or metadata contract is not usable",
            }
        meta = _get_meta(connection)
        count = int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
    except (KeyError, TypeError, ValueError, sqlite3.DatabaseError, OSError) as exc:
        return {
            "ok": False,
            "index": str(path),
            "error": type(exc).__name__,
            "detail": str(exc),
        }
    return {"ok": True, "index": str(path), "record_count": count, "meta": meta, **meta}


def read_index_meta(store: str | Path, index_path: str | Path | None = None) -> dict[str, Any]:
    """Read sidecar metadata without creating or repairing the projection."""

    path = Path(index_path_for(store, index_path)).expanduser().resolve()
    if not path.is_file():
        return {
            "ok": False,
            "index": str(path),
            "error": "FileNotFoundError",
            "detail": "graph index sidecar does not exist",
        }
    try:
        with _connect(path) as connection:
            return _read_index_meta_connection(connection, path)
    except (sqlite3.DatabaseError, OSError) as exc:
        return {"ok": False, "index": str(path), "error": type(exc).__name__, "detail": str(exc)}


def _source_requires_rebuild(path: Path, meta: dict[str, str]) -> bool:
    if not meta or meta.get("schema") != INDEX_SCHEMA:
        return True
    current = _source_meta(path)
    if meta.get("device", "") != current.get("device", ""):
        return True
    if meta.get("inode", "") != current.get("inode", ""):
        return True
    try:
        old_size = int(meta.get("size", "0"))
        old_offset = int(meta.get("offset", "0"))
        indexed_prefix_length = int(meta.get("indexed_prefix_length", "-1"))
        new_size = int(current.get("size", "0"))
    except ValueError:
        return True
    if new_size < old_offset or new_size < old_size:
        return True
    # An append-only source with unchanged size must also have unchanged
    # modification time.  A changed mtime at the same size is an in-place edit
    # (including mutations beyond the 4 KiB prefix) and invalidates the index.
    if new_size == old_size and meta.get("mtime_ns", "") != current.get("mtime_ns", ""):
        return True
    prefix_length = min(old_size, PREFIX_BYTES)
    if meta.get("prefix_fingerprint", "") != _prefix_fingerprint(path, prefix_length):
        return True
    # Validate every byte already projected into SQLite before treating new
    # bytes as an append.  Older sidecars lack this metadata and rebuild once
    # to establish the stronger incremental-index authority boundary.
    if indexed_prefix_length != old_offset:
        return True
    indexed_prefix_fingerprint = meta.get("indexed_prefix_fingerprint", "")
    if not indexed_prefix_fingerprint:
        return True
    if indexed_prefix_fingerprint != _prefix_fingerprint(path, old_offset):
        return True
    return False


def _tokens(value: Any) -> list[str]:
    return sorted({token.lower() for token in _TOKEN_RE.findall(str(value or "").lower()) if token})


def _tags(value: Any) -> list[str]:
    values = value if isinstance(value, list) else re.split(r"[,\s]+", str(value or ""))
    return sorted({str(item).strip().lower() for item in values if str(item).strip()})


def _explicit_references(record: dict[str, Any]) -> list[tuple[str, str, str]]:
    source = str(record.get("id", ""))
    body = str(record.get("body", ""))
    refs: set[tuple[str, str, str]] = set()
    for match in _EXPLICIT_RE.finditer(body):
        label = " ".join(match.group(1).lower().split())
        edge_type = _EXPLICIT_LABELS.get(label)
        if not edge_type:
            continue
        for target in match.group(2).split(","):
            target = target.strip().strip("[](){}<>\"'")
            if target and target != source:
                refs.add((source, target, edge_type))
    return sorted(refs)


def _validate_json_contract(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"non-string JSON object key at {path}")
            _validate_json_contract(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_contract(item, f"{path}[{index}]")


def _record_values(record: dict[str, Any], *, line_no: int, offset: int, end_offset: int) -> dict[str, Any] | None:
    _validate_json_contract(record)
    record_id = str(record.get("id", "")).strip()
    if not record_id:
        return None
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    normalized = dict(record)
    normalized.setdefault("schema_version", "1.0")
    raw = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return {
        "id": record_id,
        "line_no": int(line_no),
        "offset": int(offset),
        "end_offset": int(end_offset),
        "raw": raw,
        "schema_version": str(normalized.get("schema_version", "")),
        "tier": str(normalized.get("tier", "")),
        "title": str(normalized.get("title", "")),
        "body": str(normalized.get("body", "")),
        "scope": str(normalized.get("scope", "")),
        "status": str(normalized.get("status", "")),
        "confidence": str(normalized.get("confidence", "")),
        # Only the exact JSON boolean false is trusted as reusable. Invalid
        # legacy values fail closed into the verification-required bucket.
        "verify_before_use": int(
            normalized.get("verify_before_use", False) is not False
        ),
        "provenance_type": str(provenance.get("type", "")),
        "evidence_path": str(provenance.get("evidence_path", "")),
        "created_at": str(normalized.get("created_at", "")),
        "record": normalized,
    }


def _upsert_record(connection: sqlite3.Connection, values: dict[str, Any]) -> None:
    record_id = values["id"]
    connection.execute("DELETE FROM weighted_terms WHERE record_id = ?", (record_id,))
    connection.execute("DELETE FROM tags WHERE record_id = ?", (record_id,))
    connection.execute("DELETE FROM evidence_paths WHERE record_id = ?", (record_id,))
    connection.execute("DELETE FROM explicit_refs WHERE source_id = ?", (record_id,))
    connection.execute(
        """
        INSERT INTO records
          (id, line_no, offset, end_offset, raw, schema_version, tier, title, body,
           scope, status, confidence, verify_before_use, provenance_type,
           evidence_path, created_at)
        VALUES (:id, :line_no, :offset, :end_offset, :raw, :schema_version,
                :tier, :title, :body, :scope, :status, :confidence,
                :verify_before_use, :provenance_type, :evidence_path, :created_at)
        ON CONFLICT(id) DO UPDATE SET
          line_no=excluded.line_no, offset=excluded.offset, end_offset=excluded.end_offset,
          raw=excluded.raw, schema_version=excluded.schema_version, tier=excluded.tier,
          title=excluded.title, body=excluded.body, scope=excluded.scope,
          status=excluded.status, confidence=excluded.confidence,
          verify_before_use=excluded.verify_before_use, provenance_type=excluded.provenance_type,
          evidence_path=excluded.evidence_path, created_at=excluded.created_at
        """,
        values,
    )
    fields = (("title", values["title"], 8), ("tags", " ".join(_tags(values["record"].get("tags")),), 6),
              ("scope", values["scope"], 4), ("body", values["body"], 2))
    for field, text, weight in fields:
        for term in _tokens(text):
            connection.execute(
                "INSERT OR IGNORE INTO weighted_terms(record_id, term, field, weight) VALUES (?, ?, ?, ?)",
                (record_id, term, field, weight),
            )
    for tag in _tags(values["record"].get("tags")):
        connection.execute("INSERT OR IGNORE INTO tags(record_id, tag) VALUES (?, ?)", (record_id, tag))
    if values["evidence_path"]:
        connection.execute(
            "INSERT OR IGNORE INTO evidence_paths(record_id, path) VALUES (?, ?)",
            (record_id, values["evidence_path"]),
        )
    for source, target, edge_type in _explicit_references(values["record"]):
        connection.execute(
            "INSERT OR IGNORE INTO explicit_refs(source_id, target_id, edge_type) VALUES (?, ?, ?)",
            (source, target, edge_type),
        )


def _scan(path: Path, start: int = 0, line_start: int = 0) -> tuple[list[dict[str, Any]], int, int, int]:
    values: list[dict[str, Any]] = []
    offset = int(start)
    line_no = int(line_start)
    invalid_lines = 0
    if not path.exists():
        return values, offset, line_no, invalid_lines
    with path.open("rb") as handle:
        handle.seek(start)
        while True:
            raw_line = handle.readline()
            if not raw_line:
                break
            end = offset + len(raw_line)
            if not raw_line.endswith((b"\n", b"\r")):
                # A writer may have left a partial final record.  Keep the
                # offset at the last complete line so a later append retries it.
                break
            line_no += 1
            try:
                item = json.loads(
                    raw_line.decode("utf-8"),
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(f"non-finite JSON constant: {value}")
                    ),
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                invalid_lines += 1
                offset = end
                continue
            if isinstance(item, dict):
                try:
                    values_item = _record_values(
                        item, line_no=line_no, offset=offset, end_offset=end
                    )
                except ValueError:
                    invalid_lines += 1
                    offset = end
                    continue
                if values_item is not None:
                    values.append(values_item)
            offset = end
    return values, offset, line_no, invalid_lines


def _fresh_build(store: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp-", dir=str(target.parent)
    )
    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        # mkstemp gives us a unique path even when several processes rebuild
        # different sidecars in the same directory.  SQLite must create the
        # database itself, so remove the placeholder before connecting.
        temporary.unlink()
        with _connect(temporary) as connection:
            _create_schema(connection)
            connection.execute("BEGIN")
            values, offset, line_no, invalid = _scan(store)
            for item in values:
                _upsert_record(connection, item)
            meta = _source_meta(store, offset=offset, line_no=line_no)
            meta["invalid_lines"] = str(invalid)
            connection.execute("DELETE FROM meta")
            connection.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", meta.items())
            connection.commit()
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"status": "rebuilt", "indexed_offset": int(offset), "invalid_lines": int(invalid)}


def _incremental_update(store: Path, target: Path, meta: dict[str, str]) -> dict[str, Any]:
    try:
        offset = int(meta.get("offset", "0"))
        line_no = int(meta.get("line_no", "0"))
    except ValueError:
        return _fresh_build(store, target)
    values, new_offset, new_line_no, invalid = _scan(store, offset, line_no)
    with _connect(target) as connection:
        connection.execute("BEGIN")
        for item in values:
            _upsert_record(connection, item)
        source = _source_meta(store, offset=new_offset, line_no=new_line_no)
        previous_invalid = int(meta.get("invalid_lines", "0") or 0)
        source["invalid_lines"] = str(previous_invalid + invalid)
        connection.execute("DELETE FROM meta")
        connection.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", source.items())
        connection.commit()
    return {
        "status": "incremental" if values or invalid or new_offset != offset else "unchanged",
        "indexed_offset": int(new_offset),
        "indexed_records": len(values),
        "invalid_lines": int(invalid),
    }


def _refresh_index_locked(source: Path, target: Path) -> tuple[dict[str, Any], str]:
    """Refresh *target* while its sidecar mutex is held."""

    reason = "missing"
    if not target.exists():
        return _fresh_build(source, target), reason
    try:
        with _connect(target) as connection:
            usable = _schema_is_usable(connection)
            meta = _get_meta(connection) if usable else {}
    except (sqlite3.DatabaseError, OSError):
        usable, meta = False, {}
    if not usable:
        reason = "schema_or_corruption"
        action = _fresh_build(source, target)
        action["status"] = "corrupt_rebuilt"
        return action, reason
    if _source_requires_rebuild(source, meta):
        reason = "source_identity_shrink_or_prefix"
        action = _fresh_build(source, target)
        action["status"] = "rebuilt"
        return action, reason
    return _incremental_update(source, target, meta), reason


def _finalize_index_receipt(
    metadata: dict[str, Any],
    *,
    action: dict[str, Any],
    reason: str,
    source: Path,
    target: Path,
) -> dict[str, Any]:
    """Bind refresh action metadata to the exact sidecar receipt read."""

    receipt = dict(metadata)
    if receipt.get("ok") is not True:
        # Never turn a failed receipt read into success merely because the
        # preceding rebuild/update call returned.
        receipt.update(
            {
                "status": "receipt_failed",
                "action_status": action.get("status", "unknown"),
                "store": str(source),
                "index": str(target),
                "source_of_truth": "append-only memory fabric JSONL store",
            }
        )
        return receipt
    receipt.update(
        {
            "status": action.get("status", "unchanged"),
            "reason": reason
            if action.get("status") in {"rebuilt", "corrupt_rebuilt"}
            else "",
            "store": str(source),
            "index": str(target),
            "indexed_offset": action.get(
                "indexed_offset", int(receipt.get("offset", 0) or 0)
            ),
            "indexed_records": action.get(
                "indexed_records", receipt.get("record_count", 0)
            ),
            "invalid_lines": action.get(
                "invalid_lines", int(receipt.get("invalid_lines", 0) or 0)
            ),
            "source_of_truth": "append-only memory fabric JSONL store",
        }
    )
    return receipt


def ensure_index(store: str | Path, index_path: str | Path | None = None) -> dict[str, Any]:
    """Create, incrementally update, or safely rebuild a graph sidecar."""

    source = _source_path(store)
    target = Path(index_path_for(source, index_path)).expanduser().resolve()
    # Existence/schema/source checks, mutation, and the receipt read share one
    # lock so the receipt cannot describe a different replacement sidecar.
    with _sidecar_lock(target):
        action, reason = _refresh_index_locked(source, target)
        try:
            with _connect(target) as connection:
                metadata = _read_index_meta_connection(connection, target)
        except (sqlite3.DatabaseError, OSError) as exc:
            metadata = {
                "ok": False,
                "index": str(target),
                "error": type(exc).__name__,
                "detail": str(exc),
            }
        return _finalize_index_receipt(
            metadata,
            action=action,
            reason=reason,
            source=source,
            target=target,
        )


# Compatibility aliases used by small scripts and downstream experiments.
build_index = ensure_index
index_store = ensure_index
rebuild_index = ensure_index


def open_index_with_receipt(
    store: str | Path, index_path: str | Path | None = None
) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """Open one read snapshot and return the receipt for that exact snapshot.

    The read transaction is established before releasing the sidecar lock.
    Even if a later caller refreshes or replaces the projection, all rows read
    from the returned connection remain bound to the returned metadata.
    """

    source = _source_path(store)
    target = Path(index_path_for(source, index_path)).expanduser().resolve()
    with _sidecar_lock(target):
        action, reason = _refresh_index_locked(source, target)
        connection = _connect(target)
        try:
            connection.execute("BEGIN")
            metadata = _read_index_meta_connection(connection, target)
            receipt = _finalize_index_receipt(
                metadata,
                action=action,
                reason=reason,
                source=source,
                target=target,
            )
            if receipt.get("ok") is not True:
                raise sqlite3.DatabaseError(
                    str(receipt.get("detail", "graph index receipt is not usable"))
                )
        except Exception:
            connection.close()
            raise
    return connection, receipt


def open_index(store: str | Path, index_path: str | Path | None = None) -> sqlite3.Connection:
    """Ensure and open a receipt-bound read snapshot for indexed joins."""

    connection, _receipt = open_index_with_receipt(store, index_path)
    return connection


def edge_digest(source: str, target: str, edge_type: str, evidence: str = "", weight: int = 0) -> str:
    payload = json.dumps(
        {"source": str(source), "target": str(target), "type": str(edge_type), "evidence": str(evidence), "weight": int(weight)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


__all__ = [
    "INDEX_CONTRACT_VERSION",
    "INDEX_SCHEMA",
    "INDEX_SUFFIX",
    "build_index",
    "edge_digest",
    "ensure_index",
    "index_path",
    "index_path_for",
    "index_store",
    "open_index",
    "open_index_with_receipt",
    "normalize_scope",
    "read_index_meta",
    "rebuild_index",
    "scope_contains",
    "scope_sql",
    "sidecar_path",
]
