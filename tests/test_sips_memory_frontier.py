from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import memory_fabric_graph_index
from memory_fabric_graph_index import ensure_index, scope_contains


def load_frontier_module():
    path = Path(__file__).parents[1] / "scripts" / "sips_runtime" / "memory_frontier.py"
    spec = importlib.util.spec_from_file_location("sips_memory_frontier_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(
    number: int,
    *,
    title: str = "Graph needle",
    body: str = "A durable graph lesson.",
    scope: str = "project/frontier",
    tags: list[str] | None = None,
    provenance: str = "source_file",
    confidence: str = "high",
    status: str = "active",
    verify: bool = False,
    evidence: str = "evidence/frontier.md",
) -> dict:
    return {
        "schema_version": "1.0",
        "id": f"mem_{number:016x}",
        "tier": "learning",
        "title": title,
        "body": body,
        "scope": scope,
        "tags": tags or ["graph", "frontier"],
        "provenance": {"type": provenance, "evidence_path": evidence},
        "confidence": confidence,
        "verify_before_use": verify,
        "status": status,
        "created_at": f"2026-01-01T00:00:{number % 60:02d}+00:00",
    }


def write_store(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in records), encoding="utf-8")


def test_index_incremental_rebuild_and_corruption(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    first = ensure_index(store)
    assert first["status"] == "rebuilt"
    assert ensure_index(store)["status"] == "unchanged"
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record(2)) + "\n")
    appended = ensure_index(store)
    assert appended["status"] == "incremental"
    assert appended["record_count"] == 2

    store.write_text(json.dumps(record(1)) + "\n", encoding="utf-8")
    assert ensure_index(store)["status"] == "rebuilt"
    # Same-sized content with a changed prefix must invalidate the projection.
    changed = record(1, title="Graph needle")
    changed["body"] = "A durable graph lesson!"
    write_store(store, [changed])
    assert ensure_index(store)["status"] == "rebuilt"

    index = Path(str(store) + ".graph-index-v1.sqlite3")
    index.write_bytes(b"not sqlite")
    repaired = ensure_index(store)
    assert repaired["status"] == "corrupt_rebuilt"
    assert repaired["record_count"] == 1


def test_index_rebuilds_sidecar_from_older_contract_revision(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    receipt = ensure_index(store)
    with sqlite3.connect(receipt["index"]) as connection:
        connection.execute(
            "UPDATE meta SET value = '1' WHERE key = 'contract_version'"
        )
        connection.commit()

    rebuilt = ensure_index(store)
    assert rebuilt["status"] == "corrupt_rebuilt"
    assert rebuilt["meta"]["contract_version"] == "2"


def test_index_rebuilds_tampered_current_contract_schema(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    receipt = ensure_index(store)
    with sqlite3.connect(receipt["index"]) as connection:
        connection.executescript(
            """
            DROP VIEW terms;
            DROP TABLE weighted_terms;
            CREATE TABLE weighted_terms(record_id TEXT PRIMARY KEY, garbage TEXT);
            CREATE VIEW terms AS SELECT record_id, garbage FROM weighted_terms;
            """
        )

    rebuilt = ensure_index(store)
    assert rebuilt["ok"] is True
    assert rebuilt["status"] == "corrupt_rebuilt"
    with sqlite3.connect(rebuilt["index"]) as connection:
        columns = [
            row[1] for row in connection.execute("PRAGMA table_info(weighted_terms)")
        ]
        view_columns = [row[1] for row in connection.execute("PRAGMA table_info(terms)")]
    assert columns == ["record_id", "term", "field", "weight"]
    assert view_columns == columns


def test_ensure_index_preserves_failed_receipt_status(tmp_path, monkeypatch):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])

    monkeypatch.setattr(
        memory_fabric_graph_index,
        "_read_index_meta_connection",
        lambda _connection, path: {
            "ok": False,
            "index": str(path),
            "error": "SyntheticReceiptFailure",
            "detail": "receipt could not be read",
        },
    )
    receipt = memory_fabric_graph_index.ensure_index(store)
    assert receipt["ok"] is False
    assert receipt["status"] == "receipt_failed"
    assert receipt["action_status"] == "rebuilt"


def test_index_concurrent_first_build_is_serialized(tmp_path):
    store = tmp_path / "memory.jsonl"
    rows = [record(number) for number in range(1, 17)]
    write_store(store, rows)
    callers = 8
    barrier = threading.Barrier(callers)

    def build_once():
        barrier.wait()
        return ensure_index(store)

    with ThreadPoolExecutor(max_workers=callers) as pool:
        receipts = list(pool.map(lambda _index: build_once(), range(callers)))

    assert all(receipt["ok"] for receipt in receipts)
    assert {receipt["record_count"] for receipt in receipts} == {len(rows)}
    assert {receipt["indexed_offset"] for receipt in receipts} == {store.stat().st_size}
    with sqlite3.connect(receipts[0]["index"]) as connection:
        ids = {
            row[0]
            for row in connection.execute("SELECT id FROM records ORDER BY line_no")
        }
    assert ids == {item["id"] for item in rows}


def test_index_has_expected_tables_and_source_meta(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    receipt = ensure_index(store)
    assert receipt["meta"]["device"]
    assert receipt["meta"]["inode"]
    assert receipt["meta"]["offset"] == str(store.stat().st_size)
    assert receipt["meta"]["prefix_fingerprint"]
    assert receipt["meta"]["indexed_prefix_fingerprint"]
    assert receipt["meta"]["indexed_prefix_length"] == receipt["meta"]["offset"]
    with sqlite3.connect(receipt["index"]) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert {"meta", "records", "weighted_terms", "terms", "tags", "evidence_paths", "explicit_refs"} <= names


def test_index_rejects_non_finite_json_records_fail_closed(tmp_path):
    store = tmp_path / "memory.jsonl"
    malformed = record(1)
    line = json.dumps(malformed, sort_keys=True).replace(
        '"tags": ["graph", "frontier"]', '"tags": [NaN]'
    )
    assert "NaN" in line
    store.write_text(line + "\n", encoding="utf-8")

    receipt = ensure_index(store)
    assert receipt["record_count"] == 0
    assert receipt["invalid_lines"] == 1
    frontier = load_frontier_module().query_frontier(
        scope="project/frontier", query="needle", store=store
    )
    assert frontier["status"] == "empty"
    json.dumps(frontier, allow_nan=False)


def test_scope_contains_uses_exact_or_nested_path_boundaries():
    assert scope_contains("project/foo", "project/foo")
    assert scope_contains("project/foo/child", "project/foo")
    assert not scope_contains("unrelated-project/foo-evil", "project/foo")
    assert not scope_contains("other/foo", "project/foo")
    assert scope_contains(["other/foo", "project/foo/child"], "project/foo")


def test_index_rebuilds_same_size_mutation_beyond_prefix(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1, body="A" * 6_000)])
    ensure_index(store)
    original = bytearray(store.read_bytes())
    position = 5_000
    original[position] = ord("B") if original[position] != ord("B") else ord("C")
    previous_mtime = store.stat().st_mtime_ns
    store.write_bytes(bytes(original))
    os.utime(store, ns=(store.stat().st_atime_ns, max(store.stat().st_mtime_ns, previous_mtime + 1)))
    assert ensure_index(store)["status"] == "rebuilt"


def test_index_rebuilds_mutation_beyond_prefix_before_append(tmp_path):
    store = tmp_path / "memory.jsonl"
    original_body = "A" * 6_000
    write_store(store, [record(1, body=original_body)])
    ensure_index(store)

    payload = bytearray(store.read_bytes())
    body_start = payload.index(original_body.encode("utf-8"))
    payload[body_start + 5_000] = ord("B")
    store.write_bytes(bytes(payload))
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record(2), sort_keys=True) + "\n")

    rebuilt = ensure_index(store)
    assert rebuilt["status"] == "rebuilt"
    expected_body = "A" * 5_000 + "B" + "A" * 999
    with sqlite3.connect(rebuilt["index"]) as connection:
        indexed_body = connection.execute(
            "SELECT body FROM records WHERE id = ?", ("mem_0000000000000001",)
        ).fetchone()[0]
        record_count = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    assert indexed_body == expected_body
    assert record_count == 2


def test_frontier_queries_index_only(tmp_path, monkeypatch):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    ensure_index(store)
    import memory_fabric_jsonl

    monkeypatch.setattr(memory_fabric_jsonl, "load_records", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("source replay")))
    frontier = load_frontier_module()
    result = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    assert result["schema"] == "memory.frontier.v1"
    assert result["node_count"] == 1
    assert result["source_of_truth"].startswith("append-only")


def test_frontier_rows_are_bound_to_same_snapshot_receipt(tmp_path, monkeypatch):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1, title="unrelated")])
    ensure_index(store)
    frontier = load_frontier_module()
    original_open = frontier.open_index_with_receipt

    def append_then_open(source):
        with store.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(record(2, title="Snapshot needle"), sort_keys=True) + "\n"
            )
        return original_open(source)

    monkeypatch.setattr(frontier, "open_index_with_receipt", append_then_open)
    result = frontier.query_frontier(
        scope="project/frontier", query="snapshot needle", store=store
    )

    assert "mem_0000000000000002" in result["selected_ids"]
    assert int(result["index_metadata"]["offset"]) == store.stat().st_size
    assert result["index_metadata"]["record_count"] == 2


def test_frontier_scope_requires_exact_or_nested_path_boundary(tmp_path):
    store = tmp_path / "memory.jsonl"
    rows = [
        record(1, scope="project/foo"),
        record(2, scope="project/foo/child"),
        record(3, scope="unrelated-project/foo-evil"),
        record(4, scope="other/foo"),
    ]
    write_store(store, rows)
    frontier = load_frontier_module()
    result = frontier.query_frontier(
        scope="project/foo", query="needle", store=store, max_depth=0
    )
    assert set(result["selected_ids"]) == {"mem_0000000000000001", "mem_0000000000000002"}
    assert "mem_0000000000000003" not in result["selected_ids"]
    assert "mem_0000000000000004" not in result["selected_ids"]


def test_frontier_ranks_explicit_evidence_tags_then_scope(tmp_path):
    store = tmp_path / "memory.jsonl"
    root, explicit, evidence, tag, scoped = (record(index) for index in range(1, 6))
    explicit["id"] = "mem_0000000000000002"
    evidence["id"] = "mem_0000000000000003"
    tag["id"] = "mem_0000000000000004"
    scoped["id"] = "mem_0000000000000005"
    root["body"] = "Needle root depends on: mem_0000000000000002"
    root["provenance"]["evidence_path"] = "evidence/frontier.md"
    evidence["provenance"]["evidence_path"] = "evidence/frontier.md"
    explicit["provenance"]["evidence_path"] = "evidence/explicit.md"
    tag["provenance"]["evidence_path"] = "evidence/tag.md"
    scoped["provenance"]["evidence_path"] = "evidence/scope.md"
    explicit["tags"] = ["explicit"]
    evidence["tags"] = ["evidence"]
    scoped["tags"] = ["scope"]
    tag["tags"] = root["tags"]
    scoped["tags"] = ["other"]
    write_store(store, [root, explicit, evidence, tag, scoped])
    frontier = load_frontier_module()
    result = frontier.query_frontier(scope="project/frontier", query="root", store=store, seed_limit=1, fanout=8)
    types = [edge["type"] for edge in result["edges"]]
    assert types[:4] == ["depends_on", "shares_evidence", "shares_tag", "same_scope"]


def test_frontier_trust_supersession_and_untrusted_filter(tmp_path):
    store = tmp_path / "memory.jsonl"
    good, verify, context, old, superseder = [record(index) for index in range(1, 6)]
    verify["verify_before_use"] = True
    context["provenance"] = {"type": "live_ui", "evidence_path": ""}
    old["id"] = "mem_0000000000000004"
    superseder["id"] = "mem_0000000000000005"
    superseder["body"] = "This supersedes: mem_0000000000000004"
    write_store(store, [good, verify, context, old, superseder])
    frontier = load_frontier_module()
    trusted = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    assert "mem_0000000000000001" in trusted["selected_ids"]
    assert "mem_0000000000000002" not in trusted["selected_ids"]
    assert "mem_0000000000000003" not in trusted["selected_ids"]
    assert "mem_0000000000000004" not in trusted["selected_ids"]
    untrusted = frontier.query_frontier(scope="project/frontier", query="needle", store=store, include_untrusted=True)
    assert "mem_0000000000000002" in untrusted["selected_ids"]
    assert "mem_0000000000000003" in untrusted["selected_ids"]
    assert "mem_0000000000000004" not in untrusted["selected_ids"]


@pytest.mark.parametrize("invalid_verify", [0, 1, "false", "true", None, []])
def test_invalid_verify_before_use_values_fail_closed(tmp_path, invalid_verify):
    store = tmp_path / "memory.jsonl"
    invalid = record(1)
    invalid["verify_before_use"] = invalid_verify
    write_store(store, [invalid])
    frontier = load_frontier_module()

    trusted = frontier.query_frontier(
        scope="project/frontier", query="needle", store=store
    )
    untrusted = frontier.query_frontier(
        scope="project/frontier",
        query="needle",
        store=store,
        include_untrusted=True,
    )

    assert trusted["selected_ids"] == []
    assert untrusted["selected_ids"] == [invalid["id"]]
    assert untrusted["records"][0]["verify_before_use"] is True


def test_untrusted_superseder_does_not_hide_trusted_record(tmp_path):
    store = tmp_path / "memory.jsonl"
    trusted = record(1, title="Trusted needle")
    untrusted = record(
        2,
        title="Untrusted superseder",
        body="Supersedes: mem_0000000000000001",
        provenance="live_ui",
    )
    write_store(store, [trusted, untrusted])
    frontier = load_frontier_module()

    result = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    including_untrusted = frontier.query_frontier(
        scope="project/frontier", query="needle", store=store, include_untrusted=True
    )

    assert "mem_0000000000000001" in result["selected_ids"]
    assert "mem_0000000000000002" not in result["selected_ids"]
    assert "mem_0000000000000001" not in including_untrusted["selected_ids"]


def test_frontier_cycles_and_all_caps_are_bounded(tmp_path):
    store = tmp_path / "memory.jsonl"
    rows = []
    for number in range(1, 12):
        target = (number % 10) + 1
        rows.append(record(number, body=f"Needle cycle depends on: mem_{target:016x}"))
    write_store(store, rows)
    frontier = load_frontier_module()
    result = frontier.query_frontier(
        scope="project/frontier", query="needle", store=store, seed_limit=2, fanout=1,
        max_depth=2, max_nodes=3, max_edges=2, max_paths=1, token_budget=60,
    )
    assert result["node_count"] <= 3
    assert result["edge_count"] <= 2
    assert result["path_count"] <= 1
    assert result["token_estimate"] <= 60
    assert len(result["selected_ids"]) == len(set(result["selected_ids"]))


def test_frontier_chain_cycle_paths_preserve_parent_edges_and_caps(tmp_path):
    store = tmp_path / "memory.jsonl"
    rows = [
        record(
            1,
            title="Needle root",
            body="Needle root depends on: mem_0000000000000002",
            scope="project/frontier/1",
            tags=["chain-1"],
            evidence="evidence/chain-1.md",
        ),
        record(
            2,
            title="Chain middle",
            body="Middle depends on: mem_0000000000000003",
            scope="project/frontier/2",
            tags=["chain-2"],
            evidence="evidence/chain-2.md",
        ),
        record(
            3,
            title="Chain leaf",
            body="Leaf depends on: mem_0000000000000001",
            scope="project/frontier/3",
            tags=["chain-3"],
            evidence="evidence/chain-3.md",
        ),
    ]
    write_store(store, rows)
    frontier = load_frontier_module()
    kwargs = {
        "scope": "project/frontier",
        "query": "needle",
        "store": store,
        "seed_limit": 1,
        "fanout": 2,
        "max_depth": 3,
        "max_nodes": 3,
        "max_edges": 3,
        "max_paths": 3,
        "token_budget": 400,
    }
    result = frontier.query_frontier(**kwargs)
    repeated = frontier.query_frontier(**kwargs)

    assert result["paths"] == repeated["paths"]
    assert result["node_count"] <= kwargs["max_nodes"]
    assert result["edge_count"] <= kwargs["max_edges"]
    assert result["path_count"] <= kwargs["max_paths"]
    edge_by_digest = {edge["digest"]: edge for edge in result["edges"]}

    def digest_for(left: str, right: str) -> str:
        return next(
            digest
            for digest, edge in edge_by_digest.items()
            if {left, right} == {edge["source"], edge["target"]}
        )

    for path in result["paths"]:
        assert len(path["edges"]) == len(path["nodes"]) - 1
        for left, right, digest in zip(path["nodes"], path["nodes"][1:], path["edges"]):
            edge = edge_by_digest[digest]
            assert {left, right} == {edge["source"], edge["target"]}

    chain_path = next(
        path
        for path in result["paths"]
        if path["nodes"] == ["mem_0000000000000001", "mem_0000000000000002", "mem_0000000000000003"]
    )
    assert chain_path["edges"] == [
        digest_for("mem_0000000000000001", "mem_0000000000000002"),
        digest_for("mem_0000000000000002", "mem_0000000000000003"),
    ]


def test_frontier_reverse_explicit_edge_uses_discovery_orientation(tmp_path):
    store = tmp_path / "memory.jsonl"
    source = record(
        1,
        title="Source record",
        body="Source depends on: mem_0000000000000002",
        scope="project/frontier/source",
        tags=["source"],
        evidence="evidence/source.md",
    )
    seed = record(
        2,
        title="Reverse needle",
        body="Seed target",
        scope="project/frontier/seed",
        tags=["seed"],
        evidence="evidence/seed.md",
    )
    write_store(store, [source, seed])
    frontier = load_frontier_module()
    result = frontier.query_frontier(
        scope="project/frontier",
        query="needle",
        store=store,
        seed_limit=1,
        fanout=1,
        max_depth=1,
        max_nodes=2,
        max_edges=1,
        max_paths=1,
    )

    edge = result["edges"][0]
    assert result["paths"] == [
        {
            "nodes": ["mem_0000000000000002", "mem_0000000000000001"],
            "edges": [edge["digest"]],
            "score": 10,
            "edge_type": "depends_on",
        }
    ]


def test_frontier_oversized_first_seed_uses_actual_bounded_estimate(tmp_path):
    store = tmp_path / "memory.jsonl"
    oversized = record(
        1,
        title="Needle " + "T" * 120,
        body="B" * 200,
        scope="project/frontier/" + "S" * 120,
    )
    write_store(store, [oversized])
    frontier = load_frontier_module()
    token_budget = 80

    result = frontier.query_frontier(
        scope="project/frontier",
        query="needle",
        store=store,
        token_budget=token_budget,
    )

    node = result["nodes"][0]
    retrieved_record = result["records"][0]
    actual_estimate = max(
        1,
        (
            len(
                json.dumps(
                    retrieved_record,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            + 3
        )
        // 4,
    )
    assert set(node["truncated_fields"]) == {"title", "body", "scope"}
    assert node["token_estimate"] == actual_estimate
    assert result["token_estimate"] == actual_estimate
    assert actual_estimate <= token_budget
    assert not {"tags", "created_at", "tier"}.intersection(retrieved_record)
    assert result["truncated"] is True
    assert result["truncation"]["tokens"] is True


def test_frontier_unknown_raw_fields_cannot_escape_payload_budget(tmp_path):
    store = tmp_path / "memory.jsonl"
    padded = record(1, title="needle", body="tiny", scope="project/frontier")
    padded["padding"] = "X" * 100_000
    write_store(store, [padded])
    frontier = load_frontier_module()

    too_small = frontier.query_frontier(
        scope="project/frontier", query="needle", store=store, token_budget=10
    )
    assert too_small["node_count"] == 0
    assert too_small["token_estimate"] == 0
    assert too_small["omitted_reasons"][padded["id"]] == ["token_budget"]
    assert too_small["omitted"][0]["provenance"]["type"] == "source_file"
    assert too_small["omitted"][0]["token_estimate"] > 10

    admitted = frontier.query_frontier(
        scope="project/frontier", query="needle", store=store, token_budget=100
    )
    serialized = json.dumps(admitted, sort_keys=True)
    assert admitted["node_count"] == 1
    assert admitted["token_estimate"] <= 100
    assert "padding" not in admitted["records"][0]
    assert "X" * 1_000 not in serialized


def test_frontier_bounds_echoed_query_and_omission_metadata(tmp_path):
    store = tmp_path / "memory.jsonl"
    padded = record(1, evidence="evidence/" + "X" * 100_000)
    write_store(store, [padded])
    frontier = load_frontier_module()

    result = frontier.query_frontier(
        scope="project/frontier",
        query="needle",
        store=store,
        token_budget=10,
    )
    serialized = json.dumps(result, sort_keys=True, separators=(",", ":"))
    assert result["node_count"] == 0
    assert result["omission_summary"]["total"] == 1
    assert result["omitted"][0]["field_truncation"]["evidence_path"]["truncated"] is True
    assert "X" * 1_000 not in serialized
    assert len(serialized) < 20_000
    assert result["response_token_estimate"] >= (len(serialized) + 3) // 4

    with pytest.raises(ValueError, match="scope exceeds"):
        frontier.query_frontier(
            scope="S" * (frontier.MAX_SCOPE_CHARS + 1),
            query="needle",
            store=store,
        )
    with pytest.raises(ValueError, match="query exceeds"):
        frontier.query_frontier(
            scope="project/frontier",
            query="Q" * (frontier.MAX_QUERY_CHARS + 1),
            store=store,
        )


def test_frontier_is_deterministic_and_requires_scope_query(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1), record(2), record(3)])
    frontier = load_frontier_module()
    first = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    second = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    assert first["selected"] == second["selected"]
    assert first["edges"] == second["edges"]
    assert first["paths"] == second["paths"]
    with pytest.raises(ValueError):
        frontier.query_frontier(scope="", query="needle", store=store)
    with pytest.raises(ValueError):
        frontier.query_frontier(scope="project/frontier", query="", store=store)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("include_untrusted", "false"),
        ("token_budget", "100"),
        ("max_nodes", True),
        ("fanout", 1.5),
    ],
)
def test_frontier_rejects_type_confused_public_parameters(
    tmp_path, field, value
):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(1)])
    frontier = load_frontier_module()
    request = {
        "scope": "project/frontier",
        "query": "needle",
        "store": store,
        field: value,
    }
    with pytest.raises(TypeError):
        frontier.query_frontier(**request)


def test_frontier_hard_caps_cannot_be_expanded_by_callers(tmp_path):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(index) for index in range(1, 30)])
    frontier = load_frontier_module()
    result = frontier.query_frontier(
        scope="project/frontier",
        query="needle",
        store=store,
        seed_limit=999,
        fanout=999,
        max_depth=999,
        max_nodes=999,
        max_edges=999,
        max_paths=999,
        token_budget=999_999,
    )
    assert result["limits"] == {
        "seed_limit": 8,
        "fanout": 4,
        "max_depth": 2,
        "max_nodes": 24,
        "max_edges": 80,
        "max_paths": 8,
        "token_budget": 4_000,
    }


def test_frontier_handles_1000_records_without_quadratic_pair_builder(
    tmp_path, monkeypatch
):
    store = tmp_path / "memory.jsonl"
    write_store(store, [record(index, title=f"Graph needle {index}") for index in range(1, 1001)])
    import memory_fabric_graph_edges

    def forbidden_pair_builder(*_args, **_kwargs):
        raise AssertionError("indexed frontier called legacy quadratic pair builder")

    monkeypatch.setattr(memory_fabric_graph_edges, "build_edges", forbidden_pair_builder)
    frontier = load_frontier_module()
    result = frontier.query_frontier(scope="project/frontier", query="needle", store=store)
    assert result["index_metadata"]["record_count"] == 1000
    assert result["node_count"] <= 24
    assert result["edge_count"] <= 80
    assert result["path_count"] <= 8
