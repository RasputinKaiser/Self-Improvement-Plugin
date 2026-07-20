from __future__ import annotations

import json

import pytest

from sips_runtime import EventIntegrityError, EventStore, RuntimeController, audit_run, recover_run
from sips_runtime.canonical import canonical_json
from sips_runtime.contracts import Event as RuntimeEvent
from sips_runtime.recovery import RecoveryError, RECOVERY_EVENT_TYPE


def _create_run(tmp_path):
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "damaged",
            "objective": "recover this plan",
            "workspace_root": str(tmp_path),
            "tasks": [{"id": "task-a", "estimated_tokens": 10}],
        },
        idempotency_key="create",
    )
    controller.submit("damaged", idempotency_key="submit", expected_revision=1)
    return controller, tmp_path / "runtime" / "v1" / "runs" / "damaged"


def test_audit_reports_truncated_tail_and_preserves_bytes(tmp_path):
    _controller, run_dir = _create_run(tmp_path)
    events_path = run_dir / "events.jsonl"
    original = events_path.read_bytes()
    events_path.write_bytes(original + b'{"event_type":"task.advanced"')
    damaged = events_path.read_bytes()

    audit = audit_run(run_dir)

    assert not audit.valid
    assert not audit.writable
    assert audit.reason in {"truncated_event", "corrupt_event"}
    assert audit.verified_prefix_revision == 2
    assert audit.events_path == events_path
    assert events_path.read_bytes() == damaged
    assert audit.raw_events == damaged


def test_audit_reports_corrupt_hash_without_writing_head(tmp_path):
    _controller, run_dir = _create_run(tmp_path)
    events_path = run_dir / "events.jsonl"
    head_path = run_dir / "head.json"
    original_events = events_path.read_bytes()
    original_head = head_path.read_bytes()
    lines = events_path.read_text().splitlines()
    event = json.loads(lines[0])
    event["event_hash"] = "0" * 64
    event["event_digest"] = event["event_hash"]
    lines[0] = json.dumps(event, sort_keys=True)
    events_path.write_text("\n".join(lines) + "\n")

    audit = audit_run(run_dir)

    assert audit.reason == "corrupt_event"
    assert audit.verified_prefix_revision == 0
    assert head_path.read_bytes() == original_head
    assert events_path.read_bytes() != original_events


def test_recovery_audit_requires_exact_event_and_head_schema_fields(tmp_path):
    _controller, run_dir = _create_run(tmp_path)
    events_path = run_dir / "events.jsonl"
    head_path = run_dir / "head.json"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    for event in events:
        event.pop("schema")
        event.pop("schema_version")
    events_path.write_text(
        "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n"
    )
    head = json.loads(head_path.read_text())
    head.pop("schema")
    head.pop("schema_version")
    head_path.write_text(json.dumps(head, sort_keys=True))

    audit = audit_run(run_dir)

    assert audit.valid is False
    assert audit.writable is False
    assert audit.verified_prefix_revision == 0
    assert "required fields" in audit.reason_detail
    with pytest.raises(EventIntegrityError):
        EventStore(run_dir).verify()


def test_recovery_forks_linked_valid_chain_and_leaves_source_unchanged(tmp_path):
    controller, run_dir = _create_run(tmp_path)
    events_path = run_dir / "events.jsonl"
    source_bytes = events_path.read_bytes()
    events_path.write_bytes(source_bytes + b'{"event_type":"truncated"')
    damaged_bytes = events_path.read_bytes()

    result = recover_run(controller, "damaged", new_run_id="recovered")

    assert result.source_run_id == "damaged"
    assert result.run_id == "recovered"
    assert result.provenance_event.event_type == RECOVERY_EVENT_TYPE
    assert result.provenance_event.payload["source_run_id"] == "damaged"
    assert result.provenance_event.payload["verified_prefix_revision"] == 2
    assert events_path.read_bytes() == damaged_bytes

    recovered_store = EventStore(result.run_dir)
    assert recovered_store.verify()
    recovered_events = recovered_store.events()
    assert [event.event_type for event in recovered_events] == ["run.created", RECOVERY_EVENT_TYPE]
    assert recovered_events[0].run_id == "recovered"
    assert recovered_events[0].payload["tasks"][0]["id"] == "task-a"
    assert recovered_events[1].payload["source_run_id"] == "damaged"


def test_recovery_retry_resumes_creation_only_destination_and_is_idempotent(
    tmp_path, monkeypatch
):
    controller, run_dir = _create_run(tmp_path)
    source_bytes = (run_dir / "events.jsonl").read_bytes()
    original_append = EventStore.append

    def fail_after_creation(self, event_type, *args, **kwargs):
        if event_type == RECOVERY_EVENT_TYPE:
            raise OSError("simulated crash before provenance")
        return original_append(self, event_type, *args, **kwargs)

    monkeypatch.setattr(EventStore, "append", fail_after_creation)
    with pytest.raises(RecoveryError, match="not resumable"):
        recover_run(
            controller,
            "damaged",
            new_run_id="retry-recovered",
            recovery_id="operation-1",
        )
    partial_dir = tmp_path / "runtime" / "v1" / "runs" / "retry-recovered"
    assert [event.event_type for event in EventStore(partial_dir).events()] == [
        "run.created"
    ]

    monkeypatch.setattr(EventStore, "append", original_append)
    completed = recover_run(
        controller,
        "damaged",
        new_run_id="retry-recovered",
        recovery_id="operation-1",
    )
    repeated = recover_run(
        controller,
        "damaged",
        new_run_id="retry-recovered",
        recovery_id="operation-1",
    )
    events = EventStore(completed.run_dir).events()
    assert [event.event_type for event in events] == [
        "run.created",
        RECOVERY_EVENT_TYPE,
    ]
    assert repeated.provenance_event.event_hash == completed.provenance_event.event_hash
    assert (run_dir / "events.jsonl").read_bytes() == source_bytes


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("new_run_id", "bad/run"),
        ("new_run_id", "bad\\run"),
        ("new_run_id", "bad\nrun"),
        ("new_run_id", 5),
        ("recovery_id", "bad/recovery"),
        ("recovery_id", "bad\x00recovery"),
    ],
)
def test_recovery_rejects_unsafe_destination_ids_before_writing(
    tmp_path, field, value
) -> None:
    controller, _run_dir = _create_run(tmp_path)
    before = {path.name for path in controller.root.iterdir()}
    kwargs = {field: value}
    with pytest.raises(ValueError, match="safe single path component"):
        recover_run(controller, "damaged", **kwargs)
    assert {path.name for path in controller.root.iterdir()} == before


def test_recovery_requires_verified_creation_event(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    store = EventStore(run_dir)
    store.append("run.submitted", "run", {})
    with pytest.raises(RecoveryError):
        recover_run(run_dir, new_run_id="fork")


def test_recovery_preserves_complete_budget_configuration(tmp_path):
    run_dir = tmp_path / "budgeted"
    store = EventStore(run_dir)
    budget_config = {
        "soft_limit": 80,
        "hard_limit": 160,
        "resource_limits": {
            "model_tokens": 160,
            "retrieval_tokens": 123,
            "output_tokens": 321,
            "delegations": 7,
            "tool_calls": 19,
            "repairs": 5,
            "wall_time_seconds": 600,
            "memory_bytes": 4096,
        },
        "tranche_percentages": [30, 35, 35],
        "tranche_limits": [48, 104, 160],
        "released_tranches": 2,
        "released_token_limit": 104,
    }
    store.append(
        "run.created",
        "budgeted",
        {
            "objective": "preserve budget",
            "workspace_root": str(tmp_path),
            "metadata": {"mode": "runtime"},
            "terminal_policy": "block_descendants",
            "budgets": budget_config,
            "tasks": [{"id": "task-a", "estimated_tokens": 10}],
            "memory_edges": [],
        },
        idempotency_key="create",
        expected_revision=0,
    )

    result = recover_run(run_dir, new_run_id="budgeted-copy")

    source_budget = store.events()[0].payload["budgets"]
    recovered_budget = EventStore(result.run_dir).events()[0].payload["budgets"]
    assert recovered_budget == source_budget
    assert recovered_budget["resource_limits"]["retrieval_tokens"] == 123
    assert recovered_budget["tranche_percentages"] == [30, 35, 35]
    assert recovered_budget["tranche_limits"] == [48, 104, 160]
    assert recovered_budget["released_tranches"] == 2
    assert result.state["budget_usage"]["released_tranches"] == 2
    assert result.state["budget_usage"]["released_token_limit"] == 104


def test_recovery_rejects_nonstandard_tranche_configuration(tmp_path):
    run_dir = tmp_path / "custom-tranches"
    store = EventStore(run_dir)
    store.append(
        "run.created",
        "custom-tranches",
        {
            "objective": "reject unsupported tranche profile",
            "workspace_root": str(tmp_path),
            "budgets": {
                "soft_limit": 80,
                "hard_limit": 160,
                "resource_limits": {"model_tokens": 160},
                "tranche_percentages": [20, 30, 50],
                "tranche_limits": [32, 80, 160],
                "released_tranches": 1,
                "released_token_limit": 32,
            },
            "tasks": [{"id": "task-a", "estimated_tokens": 10}],
        },
        idempotency_key="create",
        expected_revision=0,
    )

    with pytest.raises(RecoveryError, match="nonstandard tranche percentages"):
        recover_run(run_dir, new_run_id="fork")


def test_recovery_rejects_creation_event_after_revision_one(tmp_path):
    run_dir = tmp_path / "out-of-order"
    store = EventStore(run_dir)
    store.append(
        "run.submitted",
        "out-of-order",
        {},
        idempotency_key="submit",
        expected_revision=0,
    )
    late_creation = RuntimeEvent(
        event_type="run.created",
        run_id="out-of-order",
        revision=2,
        payload={
            "objective": "ambiguous order",
            "workspace_root": str(tmp_path),
            "budgets": {},
            "tasks": [{"id": "task-a", "estimated_tokens": 10}],
        },
        prev_hash=store.events()[0].event_hash,
        idempotency_key="create",
    ).seal()
    with store.events_path.open("ab") as handle:
        handle.write(canonical_json(late_creation.to_dict()).encode("utf-8") + b"\n")
    store.head_path.write_text(
        canonical_json(
            {
                "schema": "sips.runtime.head.v1",
                "schema_version": 1,
                "seq": 2,
                "event_digest": late_creation.event_hash,
                "revision": 2,
                "hash": late_creation.event_hash,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    audit = audit_run(run_dir)

    assert not audit.valid
    assert audit.reason in {"corrupt_event", "truncated_event"}
    assert audit.creation_event is None
    with pytest.raises(RecoveryError):
        recover_run(run_dir, new_run_id="fork")


def test_duplicate_run_creation_is_rejected_by_writer_verify_and_audit(tmp_path):
    controller, run_dir = _create_run(tmp_path)
    store = EventStore(run_dir)
    with pytest.raises(EventIntegrityError, match="exactly once"):
        store.append(
            "run.created",
            "damaged",
            {"tasks": [{"id": "replacement", "estimated_tokens": 10}]},
            idempotency_key="duplicate-create",
            expected_revision=2,
        )

    first_two = store.events()
    duplicate = RuntimeEvent(
        event_type="run.created",
        run_id="damaged",
        revision=3,
        payload={"tasks": [{"id": "replacement", "estimated_tokens": 10}]},
        prev_hash=first_two[-1].event_hash,
        idempotency_key="duplicate-create",
    ).seal()
    with store.events_path.open("ab") as handle:
        handle.write(canonical_json(duplicate.to_dict()).encode("utf-8") + b"\n")
    store.head_path.write_text(
        canonical_json(
            {
                "schema": "sips.runtime.head.v1",
                "schema_version": 1,
                "seq": 3,
                "event_digest": duplicate.event_hash,
                "revision": 3,
                "hash": duplicate.event_hash,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EventIntegrityError, match="exactly once"):
        store.verify()
    audit = audit_run(run_dir)
    assert audit.valid is False
    assert audit.verified_prefix_revision == 2
    assert audit.creation_event is not None
    recovered = recover_run(controller, "damaged", new_run_id="duplicate-recovered")
    assert recovered.state["tasks"].keys() == {"task-a"}
