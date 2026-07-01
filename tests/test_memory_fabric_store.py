from __future__ import annotations

import json

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
