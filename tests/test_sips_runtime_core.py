from __future__ import annotations

import json

import pytest

from sips_runtime import (
    BudgetLedger,
    EventIntegrityError,
    EventStore,
    IdempotencyConflict,
    LeaseManager,
    PathLockTable,
    RevisionConflict,
    RuntimeController,
    SnapshotMismatch,
    SnapshotStore,
    SliceResult,
    StaleLeaseError,
    TaskSpec,
    TrancheNotReleased,
    UnknownCostError,
    canonical_hash,
    compile_dag,
    paths_overlap,
)
from sips_runtime.dag import DAGError


def _success_result() -> dict:
    evidence = [
        {"status": "passed", "count": 1, "source_id": "test:core-success"}
    ]
    return {
        "status": "succeeded",
        "gates": {
            name: {"ok": True, "evidence": evidence}
            for name in ("integrity", "correctness", "regression", "resource", "benefit")
        },
    }


def test_canonical_hash_rejects_non_finite() -> None:
    with pytest.raises(ValueError):
        canonical_hash({"value": float("nan")})
    with pytest.raises(ValueError, match="key.*must be a string"):
        canonical_hash({1: "not canonical JSON"})
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


def test_contract_models_reject_non_string_nested_json_keys() -> None:
    with pytest.raises(ValueError, match="keys must be strings"):
        TaskSpec.from_dict(
            {"id": "task", "estimated_tokens": 1, "metadata": {1: "ambiguous"}}
        )
    with pytest.raises(ValueError, match="keys must be strings"):
        SliceResult.from_dict(
            {
                "slice_id": "task",
                "status": "succeeded",
                "claims": [{1: "ambiguous"}],
            }
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"values": {"unordered", "set"}},
    ],
)
def test_task_contract_rejects_noncanonical_nested_values(metadata) -> None:
    with pytest.raises(ValueError):
        TaskSpec.from_dict(
            {"id": "task", "estimated_tokens": 1, "metadata": metadata}
        )


def test_direct_promotion_requires_exact_boolean_activation(tmp_path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "typed-activation", "tasks": [{"id": "a"}]},
        "create",
        0,
    )
    with pytest.raises(ValueError, match="activate must be a boolean"):
        controller.promote(
            "typed-activation",
            {"text": "candidate"},
            activate="false",  # type: ignore[arg-type]
            idempotency_key="promote",
            expected_revision=1,
        )


def test_dag_cycle_and_and_readiness() -> None:
    with pytest.raises(ValueError, match="safe single path component"):
        TaskSpec("../escape")
    with pytest.raises(DAGError):
        compile_dag([TaskSpec("a", depends_on=("b",)), TaskSpec("b", depends_on=("a",))])
    with pytest.raises(DAGError, match="escaping path"):
        compile_dag([TaskSpec("escape", write_set=("../outside",))])
    with pytest.raises(ValueError, match="required must be a boolean"):
        TaskSpec.from_dict({"id": "typed-required", "required": "false"})
    with pytest.raises(ValueError, match="exceeds cost_cap"):
        TaskSpec("over-cap", estimated_tokens=11, cost_cap=10)
    with pytest.raises(ValueError, match="must match estimated_tokens"):
        TaskSpec(
            "resource-over-cap",
            estimated_tokens=5,
            cost_cap=10,
            resource_estimates={"model_tokens": 11},
        )
    graph = compile_dag(
        [
            TaskSpec("z", priority=1),
            TaskSpec("a", priority=1),
            TaskSpec("join", depends_on=("z", "a")),
        ]
    )
    assert graph.ready_ids() == ("a", "z")
    assert graph.ready_ids(("a",)) == ("z",)
    assert graph.ready_ids(("z",)) == ("a",)


@pytest.mark.parametrize(
    "task_id",
    ["task/id", "task\\id", "task\x00id", "task\nid", "task id", "x" * 129],
)
def test_task_spec_rejects_unsafe_bounded_ids(task_id: str) -> None:
    with pytest.raises(ValueError, match="safe single path component"):
        TaskSpec(task_id)


@pytest.mark.parametrize(
    "task_id",
    ["task/id", "task\\id", "task\x00id", "task\nid", "task id", "x" * 129],
)
def test_controller_rejects_unsafe_task_ids_before_event_append(tmp_path, task_id: str) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="safe single path component"):
        controller.create(
            {"run_id": "pre-event", "tasks": [{"id": task_id}]},
            idempotency_key="create",
            expected_revision=0,
        )
    run_dir = tmp_path / "runtime" / "v1" / "runs" / "pre-event"
    assert not (run_dir / "events.jsonl").exists()


@pytest.mark.parametrize(
    "run_id",
    ["run/id", "run\\id", "run\x00id", "run\nid", ".hidden", "run id", "x" * 129, 5],
)
def test_controller_rejects_unsafe_run_ids_without_filesystem_side_effects(
    tmp_path, run_id
) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="run_id must be a safe single path component"):
        controller.create(
            {"run_id": run_id, "tasks": [{"id": "a", "estimated_tokens": 10}]},
            idempotency_key="create",
            expected_revision=0,
        )
    assert not controller.root.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [("priority", float("nan")), ("expected_value", float("inf")), ("weight", float("-inf"))],
)
def test_task_spec_rejects_non_finite_scheduler_values(field, value) -> None:
    with pytest.raises(ValueError, match=f"{field} must be finite"):
        TaskSpec("bad", **{field: value})


def test_canonical_path_overlap_and_locks(tmp_path) -> None:
    parent = tmp_path / "work"
    assert paths_overlap(parent, parent / "file.txt")
    locks = PathLockTable()
    first = TaskSpec("a", write_set=(str(parent / "file.txt"),))
    second = TaskSpec("b", read_set=(str(parent),))
    assert locks.acquire("a", first)
    assert not locks.can_acquire(second)
    locks.release("a")
    assert locks.acquire("b", second)


def test_path_lock_owner_cannot_strand_prior_task_locks(tmp_path) -> None:
    locks = PathLockTable()
    first = TaskSpec("first", write_set=(str(tmp_path / "first"),))
    second = TaskSpec("second", write_set=(str(tmp_path / "second"),))
    assert locks.acquire("worker", first)
    assert locks.acquire("worker", second) is False
    locks.release("worker")
    assert locks.acquire("other", first)


def test_leases_fence_and_expire() -> None:
    now = [10.0]
    leases = LeaseManager(clock=lambda: now[0])
    first = leases.acquire("task", "worker")
    assert first.fencing_token == 1
    now[0] += 90
    with pytest.raises(StaleLeaseError):
        leases.require("task", "worker", first.fencing_token)
    second = leases.acquire("task", "worker-2")
    assert second.fencing_token > first.fencing_token
    with pytest.raises(StaleLeaseError):
        leases.heartbeat("task", "worker", first.fencing_token)


@pytest.mark.parametrize("owner", ["", "   ", " worker", "worker ", 1])
def test_standalone_lease_manager_rejects_invalid_owners(owner) -> None:
    with pytest.raises(ValueError, match="non-empty trimmed string"):
        LeaseManager().acquire("task", owner)  # type: ignore[arg-type]


@pytest.mark.parametrize("token", [True, 0, -1, 1.0, "1"])
def test_standalone_lease_manager_requires_exact_positive_fence(token) -> None:
    with pytest.raises(Exception, match="positive integer"):
        LeaseManager().acquire(
            "task", "worker", fencing_token=token  # type: ignore[arg-type]
        )


def test_budget_unknown_fail_closed_and_soft_hard() -> None:
    ledger = BudgetLedger()
    with pytest.raises(UnknownCostError):
        ledger.reserve("unknown", None)
    with pytest.raises(TrancheNotReleased):
        ledger.reserve("not-released", 60_001)
    assert ledger.release_next_tranche() is True
    reservation = ledger.reserve("known", 60_001)
    assert reservation.soft_exceeded
    assert ledger.snapshot()["released_tranches"] == 2
    assert ledger.release_next_tranche() is True
    assert ledger.release_next_tranche() is False
    with pytest.raises(Exception):
        ledger.reserve("too-much", 120_000)
    with pytest.raises(UnknownCostError, match="must be integers"):
        ledger.reserve("fractional", 1, {"tool_calls": 1.9})
    with pytest.raises(UnknownCostError, match="must be integers"):
        ledger.reserve("negative-fraction", 1, {"tool_calls": -0.1})
    with pytest.raises(ValueError, match="resource limits must be integers"):
        BudgetLedger(resource_limits={"tool_calls": 1.9})


def test_task_budget_fields_reject_bool_and_fractional_values() -> None:
    with pytest.raises(ValueError, match="estimated_tokens"):
        TaskSpec("bool-estimate", estimated_tokens=True)
    with pytest.raises(ValueError, match="positive integer"):
        TaskSpec("zero-estimate", estimated_tokens=0)
    with pytest.raises(ValueError, match="retry_limit"):
        TaskSpec.from_dict({"id": "fractional-retry", "retry_limit": 1.9})
    with pytest.raises(ValueError, match="insertion_ordinal"):
        TaskSpec.from_dict({"id": "bool-ordinal", "insertion_ordinal": True})


@pytest.mark.parametrize(
    "task",
    [
        {"id": "unknown-resource", "estimated_tokens": 1, "resource_estimates": {"mystery": 1}},
        {"id": "mismatched-model", "estimated_tokens": 1, "resource_estimates": {"model_tokens": 2}},
        {"id": "model-without-estimate", "resource_estimates": {"model_tokens": 1}},
    ],
)
def test_invalid_task_resource_reservations_fail_before_run_event(tmp_path, task) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError):
        controller.create(
            {"run_id": "invalid-reservation", "tasks": [task]},
            "create",
            0,
        )
    assert not controller.root.exists()


@pytest.mark.parametrize(
    "run_request",
    [
        {"tasks": [{"id": "too-many-tokens", "estimated_tokens": 120_001}]},
        {
            "resource_limits": {"output_tokens": 100},
            "tasks": [{"id": "output-too-large", "estimated_tokens": 10}],
        },
    ],
)
def test_task_reservation_must_fit_run_limits_before_event(tmp_path, run_request) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="reservation exceeds run resource limits"):
        controller.create(
            {"run_id": "over-limit", **run_request},
            "create",
            0,
        )
    assert not controller.root.exists()


def test_task_resource_estimate_cannot_underreserve_mandatory_context(tmp_path) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="below mandatory reservation"):
        controller.create(
            {
                "run_id": "underreserved-context",
                "tasks": [
                    {
                        "id": "a",
                        "estimated_tokens": 10,
                        "context_query": "needle",
                        "resource_estimates": {
                            "model_tokens": 10,
                            "retrieval_tokens": 0,
                        },
                    }
                ],
            },
            "create",
            0,
        )
    assert not controller.root.exists()


def test_zero_model_token_reservations_fail_before_dispatch(tmp_path) -> None:
    ledger = BudgetLedger()
    assert ledger.can_reserve(0) is False
    with pytest.raises(UnknownCostError, match="invalid model token cost"):
        ledger.reserve("zero-cost", 0, {"tool_calls": 1, "output_tokens": 1})

    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        controller.create(
            {"run_id": "zero-cost", "tasks": [{"id": "a", "estimated_tokens": 0}]},
            "create",
            0,
        )
    run_dir = tmp_path / "runtime" / "v1" / "runs" / "zero-cost"
    assert not (run_dir / "events.jsonl").exists()


@pytest.mark.parametrize("owner", ["", "   ", " worker", "worker ", 5, None])
def test_invalid_lease_owner_cannot_consume_attempt_or_budget(tmp_path, owner) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "invalid-owner", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("invalid-owner", idempotency_key="submit", expected_revision=1)
    with pytest.raises(ValueError, match="non-empty trimmed string"):
        controller.lease(
            "invalid-owner",
            owner,  # type: ignore[arg-type]
            idempotency_key="lease",
            expected_revision=2,
        )
    state = controller.read_status("invalid-owner")
    assert state["revision"] == 2
    assert state["tasks"]["a"]["attempts"] == 0
    assert state["budget_usage"]["charged_tokens"] == 0


def test_controller_rejects_fractional_budget_configuration(tmp_path) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="soft_budget and hard_budget must be integers"):
        controller.create(
            {"run_id": "fractional-soft", "soft_budget": 1.9, "tasks": [{"id": "a"}]},
            "create",
            0,
        )
    with pytest.raises(ValueError, match="resource_limits values must be integers"):
        controller.create(
            {
                "run_id": "fractional-tools",
                "resource_limits": {"tool_calls": 1.9},
                "tasks": [{"id": "a"}],
            },
            "create",
            0,
        )


def test_budget_commit_charges_reservation_for_unreported_dimensions() -> None:
    ledger = BudgetLedger()
    reservation = ledger.reserve(
        "partial-provider-usage",
        10,
        {"retrieval_tokens": 5, "output_tokens": 4},
    )
    ledger.commit(reservation.reservation_id, actual_tokens=2)
    committed = ledger.snapshot()["committed_resources"]
    assert committed["model_tokens"] == 2
    assert committed["retrieval_tokens"] == 5
    assert committed["output_tokens"] == 4


def test_controller_rejects_unknown_merge_strategy(tmp_path) -> None:
    with pytest.raises(DAGError, match="merge strategy must be deterministic"):
        compile_dag(
            [TaskSpec("a", merge_contract={"strategy": "arrival_order"})]
        )
    controller = RuntimeController(tmp_path)
    with pytest.raises(ValueError, match="merge strategy must be deterministic"):
        controller.create(
            {
                "run_id": "bad-merge",
                "tasks": [
                    {
                        "id": "a",
                        "estimated_tokens": 10,
                        "merge_contract": {"strategy": "arrival_order"},
                    }
                ],
            },
            "create",
            0,
        )


def test_event_integrity_idempotency_revision_and_snapshot(tmp_path) -> None:
    store = EventStore(tmp_path)
    first = store.append("created", "run", {"ok": True}, idempotency_key="one", expected_revision=0)
    assert store.append("created", "run", {"ok": True}, idempotency_key="one").event_hash == first.event_hash
    with pytest.raises(IdempotencyConflict):
        store.append("created", "other-run", {"ok": True}, idempotency_key="one")
    with pytest.raises(EventIntegrityError, match="run identity changed"):
        store.append("next", "other-run", {})
    with pytest.raises(RevisionConflict):
        store.append("next", "run", {}, expected_revision=0)
    second = store.append("next", "run", {}, expected_revision=1)
    assert store.verify() and second.prev_hash == first.event_hash
    state = store.replay(lambda current, event: {"count": (current or {"count": 0})["count"] + 1}, None)
    assert state == {"count": 2}
    snapshots = SnapshotStore(tmp_path)
    snapshots.save(store.revision, store.head_hash, state)
    assert snapshots.validate_against(store)["state"] == state
    document = json.loads(snapshots.path.read_text())
    document["revision"] = 0
    snapshots.path.write_text(json.dumps(document))
    with pytest.raises(SnapshotMismatch):
        snapshots.validate_against(store)
    snapshots.save(store.revision, store.head_hash, state)
    document = json.loads(snapshots.path.read_text())
    document["schema"] = "sips.runtime.state.v0"
    snapshots.path.write_text(json.dumps(document))
    with pytest.raises(SnapshotMismatch, match="schema or version"):
        snapshots.validate_against(store)


@pytest.mark.parametrize(
    ("first_payload", "retry_payload"),
    [
        ({"value": 1}, {"value": True}),
        ({"value": 1}, {"value": 1.0}),
    ],
)
def test_event_idempotency_distinguishes_json_numeric_and_boolean_types(
    tmp_path, first_payload, retry_payload
) -> None:
    store = EventStore(tmp_path / "strict-idempotency")
    store.append(
        "created",
        "run",
        first_payload,
        idempotency_key="same-key",
        expected_revision=0,
    )
    with pytest.raises(IdempotencyConflict):
        store.append(
            "created",
            "run",
            retry_payload,
            idempotency_key="same-key",
            expected_revision=0,
        )
    assert store.revision == 1


@pytest.mark.parametrize(
    "field,value",
    [("schema_version", True), ("revision", 1.0), ("revision", "1")],
)
def test_controller_rebuilds_type_tampered_snapshot(
    tmp_path, field, value
) -> None:
    controller = RuntimeController(tmp_path / "home")
    state = controller.create(
        {"run_id": "snapshot-types", "tasks": [{"id": "a"}]},
        "create",
        0,
    )
    snapshot_path = (
        controller.root / "snapshot-types" / "snapshot.json"
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot[field] = value
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    rebuilt = controller.read_status("snapshot-types")
    repaired = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert rebuilt["revision"] == state["revision"] == 1
    assert type(repaired["schema_version"]) is int
    assert type(repaired["revision"]) is int


def test_event_store_missing_head_preserves_existing_event_bytes(tmp_path) -> None:
    run_dir = tmp_path / "missing-head"
    store = EventStore(run_dir)
    store.append("run.created", "missing-head", {"tasks": []})
    original = store.events_path.read_bytes()
    store.head_path.unlink()

    with pytest.raises(EventIntegrityError, match="head is missing"):
        EventStore(run_dir)

    assert store.events_path.read_bytes() == original
    assert store.head_path.exists() is False


def test_event_store_requires_canonical_event_schema_version_field(tmp_path) -> None:
    store = EventStore(tmp_path / "missing-event-version")
    store.append("run.created", "missing-event-version", {"tasks": []})
    event = json.loads(store.events_path.read_text())
    event.pop("schema_version")
    store.events_path.write_text(json.dumps(event, sort_keys=True) + "\n")

    with pytest.raises(EventIntegrityError, match="missing required fields"):
        store.verify()


def test_controller_lifecycle_and_stale_fencing(tmp_path) -> None:
    controller = RuntimeController(tmp_path)
    state = controller.create({"run_id": "r", "tasks": [{"id": "a", "estimated_tokens": 10}, {"id": "b", "depends_on": ["a"], "estimated_tokens": 10}]}, "create")
    assert state["status"] == "pending"
    state = controller.submit("r", {}, "submit", 1)
    assert state["status"] == "running"
    state = controller.lease("r", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(StaleLeaseError):
        controller.advance(
            "r",
            {"task_id": "a", "owner": "other", "fencing_token": lease["fencing_token"], "result": {"status": "succeeded"}},
            "stale-advance",
            3,
        )
    state = controller.advance("r", {"task_id": "a", "owner": "worker", "fencing_token": lease["fencing_token"], "result": _success_result()}, "advance", 3)
    assert state["tasks"]["a"]["status"] == "succeeded"
    state = controller.lease("r", "worker", "lease-b", 4)
    lease = state["tasks"]["b"]["lease"]
    state = controller.advance("r", {"task_id": "b", "owner": "worker", "fencing_token": lease["fencing_token"], "result": _success_result()}, "advance-b", 5)
    assert state["status"] == "succeeded"
    assert controller.read_receipt("r")["revision"] == 6
