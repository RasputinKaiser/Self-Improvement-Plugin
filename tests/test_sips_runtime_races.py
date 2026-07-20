from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event, Thread

import pytest
import sips_runtime.controller as controller_module
import sips_runtime.events as events_module
from sips_runtime import (
    EventIntegrityError,
    EventStore,
    InvalidTransition,
    RuntimeController,
    StaleLeaseError,
    audit_run,
    recover_run,
)
from sips_runtime.api import RuntimeAPI
from sips_runtime.budget import RESOURCE_DIMENSIONS
from sips_runtime.controller import runtime_root


def test_constructor_cannot_overwrite_head_after_concurrent_append(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = tmp_path / "late-head"
    existing = EventStore(run_dir)
    existing.head_path.unlink()

    init_entered = Event()
    release_init = Event()
    original_write = events_module.atomic_write_json

    def paused_write(path: Path, value: dict) -> None:
        if path == existing.head_path and value.get("revision") == 0 and not init_entered.is_set():
            init_entered.set()
            if not release_init.wait(timeout=5):
                raise RuntimeError("timed out waiting to release head initialization")
        original_write(path, value)

    monkeypatch.setattr(events_module, "atomic_write_json", paused_write)

    append_called = Event()
    original_append = EventStore.append

    def append_wrapper(self, *args, **kwargs):
        if self is existing:
            append_called.set()
        return original_append(self, *args, **kwargs)

    monkeypatch.setattr(EventStore, "append", append_wrapper)
    errors: list[BaseException] = []

    def construct_late() -> None:
        try:
            EventStore(run_dir)
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    def append_first() -> None:
        try:
            existing.append("run.created", "late-head", {"tasks": []}, expected_revision=0)
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    constructor_thread = Thread(target=construct_late)
    append_thread = Thread(target=append_first)
    constructor_thread.start()
    assert init_entered.wait(timeout=5)
    append_thread.start()
    assert append_called.wait(timeout=5)
    release_init.set()
    constructor_thread.join(timeout=5)
    append_thread.join(timeout=5)

    assert not constructor_thread.is_alive()
    assert not append_thread.is_alive()
    assert errors == []
    reopened = EventStore(run_dir)
    assert reopened.revision == 1
    assert len(reopened.events()) == 1


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((5, "writer-input"), {}),
        (("run.created", "writer-input"), {"payload": []}),
        (("run.created", "writer-input"), {"idempotency_key": 5}),
        (("run.created", "writer-input"), {"timestamp": 5}),
        (("run.created", "writer-input"), {"expected_revision": True}),
    ],
)
def test_event_writer_rejects_invalid_wire_inputs_without_append(
    tmp_path: Path, args: tuple[object, ...], kwargs: dict[str, object]
) -> None:
    store = EventStore(tmp_path / "writer-input")
    before_head = store.head_path.read_bytes()
    with pytest.raises((TypeError, ValueError)):
        store.append(*args, **kwargs)  # type: ignore[arg-type]
    assert not store.events_path.exists()
    assert store.head_path.read_bytes() == before_head
    assert store.verify() is True


def test_concurrent_create_with_generated_run_id_is_idempotent(tmp_path: Path) -> None:
    request = {"tasks": [{"id": "a", "estimated_tokens": 10}]}

    def create_once() -> dict:
        return RuntimeController(tmp_path).create(request, "same-create", 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(lambda _: create_once(), range(2)))

    assert len({state["run_id"] for state in states}) == 1
    run_id = states[0]["run_id"]
    assert all(state["revision"] == 1 for state in states)
    assert len(RuntimeController(tmp_path).read_events(run_id)) == 1


def test_event_fsync_before_head_failure_is_non_writable_and_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "runtime" / "v1" / "runs" / "head-crash"
    store = EventStore(run_dir)
    original_write = events_module.atomic_write_json

    def fail_head_replace(path: Path, value: dict) -> None:
        if path == store.head_path and value.get("revision") == 1:
            raise OSError("simulated head replacement crash")
        original_write(path, value)

    monkeypatch.setattr(events_module, "atomic_write_json", fail_head_replace)
    with pytest.raises(OSError, match="simulated head replacement crash"):
        store.append(
            "run.created",
            "head-crash",
            {"tasks": [{"id": "task", "estimated_tokens": 10}]},
            idempotency_key="create",
            expected_revision=0,
        )

    assert len(store.events_path.read_bytes().splitlines()) == 1
    assert store.head_path.read_text(encoding="utf-8").find('"revision":0') >= 0
    with pytest.raises(EventIntegrityError):
        store.verify()

    audit = audit_run(run_dir)
    assert audit.valid is False
    assert audit.reason == "head_mismatch"
    source_events = store.events_path.read_bytes()
    monkeypatch.setattr(events_module, "atomic_write_json", original_write)
    recovered = recover_run(run_dir, new_run_id="head-crash-recovered")
    assert source_events == store.events_path.read_bytes()
    assert EventStore(recovered.run_dir).verify()
    assert recovered.run_id == "head-crash-recovered"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "task_id": "a",
            "lease": {"fencing_token": 1},
            "reservation": {"tokens": 10},
        },
        {
            "task_id": "a",
            "lease": {"fencing_token": 1},
            "reservation": {
                "tokens": 10,
                "resources": {"model_tokens": 10, "not_a_dimension": 1},
            },
        },
    ],
)
def test_hash_valid_malformed_lease_resources_fail_closed(
    tmp_path: Path, payload: dict
) -> None:
    store = EventStore(tmp_path / "malformed-lease")
    store.append(
        "run.created",
        "malformed-lease",
        {"tasks": []},
        idempotency_key="create",
        expected_revision=0,
    )
    store.append(
        "task.leased",
        "malformed-lease",
        payload,
        idempotency_key="lease",
        expected_revision=1,
    )
    with pytest.raises(EventIntegrityError, match="reservation"):
        RuntimeController._charged_resources(store)


def test_hash_valid_malformed_usage_resources_fail_closed(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "malformed-usage")
    store.append(
        "run.created",
        "malformed-usage",
        {"tasks": []},
        idempotency_key="create",
        expected_revision=0,
    )
    resources = {dimension: 0 for dimension in RESOURCE_DIMENSIONS}
    resources["model_tokens"] = 10
    store.append(
        "task.leased",
        "malformed-usage",
        {
            "task_id": "a",
            "lease": {"fencing_token": 1},
            "reservation": {"tokens": 10, "resources": resources},
        },
        idempotency_key="lease",
        expected_revision=1,
    )
    store.append(
        "task.advanced",
        "malformed-usage",
        {
            "task_id": "a",
            "fencing_token": 1,
            "result": {"usage": {"resources": {"model_tokens": "10"}}},
        },
        idempotency_key="advance",
        expected_revision=2,
    )
    with pytest.raises(EventIntegrityError, match="usage"):
        RuntimeController._charged_resources(store)


def test_read_only_controller_and_api_initialization_do_not_create_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_home = tmp_path / "sips-home"
    monkeypatch.setenv("SIPS_HOME", str(runtime_home))
    expected_root = runtime_root()
    assert not expected_root.exists()
    controller = RuntimeController()
    assert not expected_root.exists()
    api = RuntimeAPI(controller)
    response = api.read("status", {"run_id": "missing"})
    assert response["ok"] is False
    assert not expected_root.exists()


def test_cross_controller_persisted_path_locks_and_fencing_reacquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1_000.0]
    monkeypatch.setattr(controller_module.time, "time", lambda: now[0])
    controller_one = RuntimeController(tmp_path)
    controller_one.create(
        {
            "run_id": "persisted-authority",
            "workspace_root": str(tmp_path),
            "tasks": [
                {"id": "a", "estimated_tokens": 10, "write_set": ["shared"]},
                {
                    "id": "b",
                    "estimated_tokens": 10,
                    "write_set": ["shared/file"],
                },
            ],
        },
        "create",
        0,
    )
    controller_one.submit("persisted-authority", idempotency_key="submit", expected_revision=1)
    first = controller_one.lease(
        "persisted-authority", "worker-one", "lease-a", 2, task_id="a"
    )
    first_lease = first["tasks"]["a"]["lease"]

    controller_two = RuntimeController(tmp_path)
    with pytest.raises(InvalidTransition, match="paths conflict"):
        controller_two.lease(
            "persisted-authority", "worker-two", "lease-b-conflict", 2, task_id="b"
        )
    assert controller_two.read_status("persisted-authority")["revision"] == 3

    now[0] = 1_091.0
    second = controller_two.lease(
        "persisted-authority", "worker-two", "lease-b", 3, task_id="b"
    )
    second_lease = second["tasks"]["b"]["lease"]
    assert second_lease["fencing_token"] > first_lease["fencing_token"]
    with pytest.raises(StaleLeaseError):
        controller_one.advance(
            "persisted-authority",
            {
                "task_id": "a",
                "owner": "worker-one",
                "fencing_token": first_lease["fencing_token"],
                "result": {"status": "running"},
            },
            "late-old-worker",
            4,
        )


def test_cross_controller_read_returns_one_coherent_event_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = RuntimeController(tmp_path)
    reader.create(
        {"run_id": "coherent-read", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    writer = RuntimeController(tmp_path)
    read_inside_snapshot = Event()
    release_read = Event()
    original_charges = RuntimeController._charged_resources
    paused = {"value": False}

    def paused_charges(source):
        if isinstance(source, tuple) and not paused["value"]:
            paused["value"] = True
            read_inside_snapshot.set()
            if not release_read.wait(timeout=5):
                raise RuntimeError("timed out waiting to release coherent read")
        return original_charges(source)

    monkeypatch.setattr(RuntimeController, "_charged_resources", staticmethod(paused_charges))
    outcomes: dict[str, dict] = {}

    read_thread = Thread(
        target=lambda: outcomes.setdefault("read", reader.read_status("coherent-read"))
    )
    write_thread = Thread(
        target=lambda: outcomes.setdefault(
            "write",
            writer.submit(
                "coherent-read", idempotency_key="submit", expected_revision=1
            ),
        )
    )
    read_thread.start()
    assert read_inside_snapshot.wait(timeout=5)
    write_thread.start()
    assert write_thread.is_alive()
    release_read.set()
    read_thread.join(timeout=5)
    write_thread.join(timeout=5)

    assert outcomes["read"]["revision"] == 1
    assert outcomes["read"]["status"] == "pending"
    assert outcomes["write"]["revision"] == 2
    assert outcomes["write"]["status"] == "running"


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("revision", 1.0), ("seq", "1")],
)
def test_event_store_rejects_non_exact_event_integer_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    store = EventStore(tmp_path / "event-tamper")
    store.append("run.created", "event-tamper", {})
    lines = [json.loads(line) for line in store.events_path.read_text().splitlines()]
    lines[0][field] = value
    store.events_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")

    with pytest.raises(EventIntegrityError, match="exact integers"):
        store.verify()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor", 7),
        ("event_type", 7),
        ("run_id", 7),
        ("timestamp", 7),
        ("event_id", 7),
        ("prev_hash", 7),
        ("payload_digest", 7),
        ("idempotency_key", 7),
    ],
)
def test_event_wire_string_types_cannot_be_changed_without_rehash(
    tmp_path: Path, field: str, value: object
) -> None:
    store = EventStore(tmp_path / "event-wire-tamper")
    store.append("run.created", "event-wire-tamper", {}, idempotency_key="create")
    event = json.loads(store.events_path.read_text(encoding="utf-8"))
    event[field] = value
    store.events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(EventIntegrityError):
        store.verify()
    audit = audit_run(store.run_dir)
    assert audit.valid is False
    assert audit.reason in {"corrupt_event", "truncated_event"}


def test_event_wire_rejects_unhashed_extra_fields(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "event-extra-field")
    store.append("run.created", "event-extra-field", {})
    event = json.loads(store.events_path.read_text(encoding="utf-8"))
    event["unhashed_extension"] = "must not be ignored"
    store.events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(EventIntegrityError, match="unexpected fields"):
        store.verify()


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("revision", 1.0), ("seq", "1")],
)
def test_event_store_rejects_non_exact_head_integer_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    store = EventStore(tmp_path / "head-tamper")
    store.append("run.created", "head-tamper", {})
    head = json.loads(store.head_path.read_text())
    head[field] = value
    store.head_path.write_text(json.dumps(head))

    with pytest.raises(EventIntegrityError, match="exact integers"):
        store.verify()


@pytest.mark.parametrize("field", ["schema", "hash", "event_digest"])
def test_event_store_rejects_non_string_head_identity_fields(
    tmp_path: Path, field: str
) -> None:
    store = EventStore(tmp_path / "head-string-tamper")
    store.append("run.created", "head-string-tamper", {})
    head = json.loads(store.head_path.read_text(encoding="utf-8"))
    head[field] = 7
    store.head_path.write_text(json.dumps(head), encoding="utf-8")

    with pytest.raises(EventIntegrityError, match="must be strings"):
        store.verify()


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", False), ("revision", 1.0), ("seq", "1")],
)
def test_recovery_rejects_non_exact_head_integer_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "head-tamper", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    head_path = tmp_path / "runtime" / "v1" / "runs" / "head-tamper" / "head.json"
    head = json.loads(head_path.read_text())
    head[field] = value
    head_path.write_text(json.dumps(head))

    audit = audit_run(head_path.parent)
    assert audit.valid is False
    assert audit.reason == "invalid_head"


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("revision", 1.0), ("seq", "1")],
)
def test_recovery_rejects_non_exact_event_integer_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "event-audit-tamper", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    events_path = tmp_path / "runtime" / "v1" / "runs" / "event-audit-tamper" / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    events[0][field] = value
    events_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

    audit = audit_run(events_path.parent)
    assert audit.valid is False
    assert audit.reason in {"corrupt_event", "truncated_event"}
