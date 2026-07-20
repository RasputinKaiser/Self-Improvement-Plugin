from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from memory_fabric_jsonl import append_record, load_records
from memory_fabric_records import make_record
from memory_fabric_schema import record_schema_version, schema
from memory_fabric_store_audit import store_audit


def test_schema_declares_record_schema_version():
    data = schema()

    assert data["schema_version"] == record_schema_version()
    assert data["required_fields"][0] == "schema_version"


def test_new_records_write_schema_version(tmp_path):
    store = tmp_path / "memory.jsonl"
    record = make_record(
        tier="learning",
        title="Schema versions are durable",
        body="New records include schema_version for forward migrations.",
        provenance_type="source_backed_agent_run",
        evidence_path=str(store),
        confidence="high",
    )

    result = append_record(record, store)
    stored = json.loads(store.read_text().strip())

    assert result["record"]["schema_version"] == record_schema_version()
    assert stored["schema_version"] == record_schema_version()


def test_legacy_records_are_backfilled_on_load(tmp_path):
    store = tmp_path / "legacy.jsonl"
    legacy = make_record(
        tier="work",
        title="Legacy record",
        body="Existing stores without schema_version remain readable.",
    )
    legacy.pop("schema_version")
    store.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    records = load_records(store)

    assert records[0]["schema_version"] == record_schema_version()


def test_invalid_jsonl_line_becomes_verify_before_use_record(tmp_path):
    store = tmp_path / "corrupt.jsonl"
    store.write_text('{"id":"ok"}\n{"id":\n', encoding="utf-8")

    records = load_records(store)

    invalid = records[1]
    assert invalid["schema_version"] == record_schema_version()
    assert invalid["id"] == "invalid_line_2"
    assert invalid["verify_before_use"] is True
    assert "invalid-jsonl" in invalid["tags"]


def test_append_rejects_unterminated_tail_without_mutating_store(tmp_path):
    store = tmp_path / "unterminated.jsonl"
    original = b'{"id":"tail","body":"preserve these bytes"}'
    store.write_bytes(original)

    with pytest.raises(ValueError, match="unterminated tail"):
        append_record({"id": "new", "body": "must not be concatenated"}, store)

    assert store.read_bytes() == original


@pytest.mark.parametrize(
    "record",
    [
        {"id": "nan", "value": float("nan")},
        {"id": "infinite", "value": float("inf")},
        {"id": "bad-key", "nested": {1: "integer key"}},
    ],
)
def test_append_rejects_noncanonical_json_before_creating_store(tmp_path, record):
    store = tmp_path / "noncanonical.jsonl"
    with pytest.raises(ValueError):
        append_record(record, store)
    assert not store.exists()


@pytest.mark.parametrize("raw_value", ["NaN", "1e9999"])
def test_load_non_finite_json_fails_closed_to_invalid_record(tmp_path, raw_value):
    store = tmp_path / "non-finite.jsonl"
    store.write_text(f'{{"id":"bad","value":{raw_value}}}\n', encoding="utf-8")
    loaded = load_records(store)
    assert loaded[0]["id"] == "invalid_line_1"
    assert loaded[0]["verify_before_use"] is True
    audit = store_audit(store)
    assert audit["ok"] is False
    assert audit["violations"][0]["code"] == "json_invalid"


def test_store_audit_flags_raw_missing_schema_version_and_invalid_json(tmp_path):
    store = tmp_path / "audit.jsonl"
    legacy = make_record(tier="learning", title="Legacy", body="Missing schema_version.")
    legacy.pop("schema_version")
    store.write_text(json.dumps(legacy) + "\nnot json\n", encoding="utf-8")

    audit = store_audit(store)
    codes = {item["code"] for item in audit["violations"]}

    assert audit["ok"] is False
    assert "schema_version_missing" in codes
    assert "json_invalid" in codes


def test_concurrent_append_records_are_complete_and_durable(tmp_path):
    store = tmp_path / "concurrent.jsonl"
    records = [
        {"id": f"concurrent_{index:04d}", "tier": "learning", "body": f"body {index}"}
        for index in range(64)
    ]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda item: append_record(item, store), records))

    assert all(result["ok"] for result in results)
    lines = store.read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    assert len(parsed) == len(records)
    assert {item["id"] for item in parsed} == {item["id"] for item in records}
    assert all(item["schema_version"] == record_schema_version() for item in parsed)
    assert load_records(store) == parsed


def test_append_record_fsyncs_file_and_parent_directory(tmp_path, monkeypatch):
    import memory_fabric_jsonl

    store = tmp_path / "durable.jsonl"
    original_fsync = memory_fabric_jsonl.os.fsync
    fsynced_fds = []

    def record_fsync(file_descriptor):
        fsynced_fds.append(file_descriptor)
        return original_fsync(file_descriptor)

    monkeypatch.setattr(memory_fabric_jsonl.os, "fsync", record_fsync)
    append_record({"id": "durable", "body": "flush me"}, store)

    assert len(fsynced_fds) == 2
    assert store.read_text(encoding="utf-8").endswith("\n")
