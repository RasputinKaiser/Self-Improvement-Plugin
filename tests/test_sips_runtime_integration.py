from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from harness_homebase_mcp import runtime_tool_payload
from sips_runtime import RuntimeController, SliceResult, canonical_hash
from sips_runtime import controller as controller_module
from sips_runtime.budget import BudgetLedger, HardBudgetExceeded, RESOURCE_DIMENSIONS
from sips_runtime.controller import InvalidTransition
from sips_runtime.events import EventIntegrityError, EventStore, IdempotencyConflict
from sips_runtime.fanin import fan_in, validate_slice_result
from sips_runtime.api import RuntimeAPI
from sips_runtime.leases import LeaseManager, StaleLeaseError


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sips_runtime.py"


def gates() -> dict[str, dict[str, object]]:
    return {
        name: {
            "ok": True,
            "evidence": [
                {"status": "passed", "count": 1, "source_id": f"gate:{name}"}
            ],
        }
        for name in ("integrity", "correctness", "regression", "resource", "benefit")
    }


def success_mapping() -> dict[str, object]:
    return {"status": "succeeded", "gates": gates()}


def complete_promotable_run(
    controller: RuntimeController, run_id: str
) -> dict[str, object]:
    controller.create(
        {"run_id": run_id, "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit(run_id, idempotency_key="submit", expected_revision=1)
    state = controller.lease(run_id, "worker", "lease", 2)
    task = state["tasks"]["a"]
    return controller.advance(
        run_id,
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": task["lease"]["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": task["reservation"]["resources"]},
            },
        },
        "advance",
        3,
    )


def test_canonical_slice_lifecycle_and_immutable_receipt(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    state = controller.create(
        {
            "run_id": "canonical",
            "workspace_root": str(tmp_path),
            "tasks": [
                {
                    "id": "task",
                    "description": "prove the canonical result contract",
                    "acceptance": [{"id": "criterion"}],
                    "estimated_tokens": 100,
                }
            ],
        },
        idempotency_key="create",
        expected_revision=0,
    )
    state = controller.submit("canonical", idempotency_key="submit", expected_revision=1)
    state = controller.lease(
        "canonical", "worker", idempotency_key="lease", expected_revision=2
    )
    task = state["tasks"]["task"]
    reservation = task["reservation"]["resources"]
    result = SliceResult(
        slice_id="task",
        task_id="task",
        run_id="canonical",
        attempt_id="task-attempt-001",
        lease_id="canonical:task:1",
        lease={**task["lease"], "active": True},
        owner="worker",
        fencing_token=task["lease"]["fencing_token"],
        plan_digest=canonical_hash(task["spec"]),
        context_digest=task["context"]["digest"],
        status="succeeded",
        claims=({"id": "claim", "text": "contract passed", "evidence_refs": ["proof"]},),
        evidence=(
            {
                "id": "proof",
                "status": "passed",
                "count": 1,
                "source_id": "test:canonical-slice",
            },
        ),
        gates=gates(),
        acceptance_results=({"ok": True, "evidence": ["proof"]},),
        usage={"resources": {key: int(reservation[key]) for key in RESOURCE_DIMENSIONS}},
        lesson_candidate={"text": "symptom contract; fix validation; proof receipt"},
    )
    assert validate_slice_result(result, allowed_paths=[])["ok"] is True
    state = controller.advance(
        "canonical", result, idempotency_key="advance", expected_revision=3
    )
    assert state["status"] == "succeeded"
    receipt = controller.read_receipt("canonical")
    assert receipt["revision"] == 4
    assert receipt["structured"]["task_results"][0]["result_hash"]
    assert receipt["structured"]["task_results"][0]["owner"] == "worker"
    assert receipt["structured"]["task_results"][0]["lease_owner"] == "worker"
    assert len(receipt["markdown"]) <= 8_000
    receipt_path = (
        tmp_path
        / "home"
        / "runtime"
        / "v1"
        / "runs"
        / "canonical"
        / "receipts"
        / "graph-receipt.json"
    )
    before = receipt_path.read_bytes()
    assert controller.read_receipt("canonical")["digest"] == receipt["digest"]
    assert receipt_path.read_bytes() == before


def test_advance_retry_rebuilds_receipts_after_post_event_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "receipt-resume", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("receipt-resume", idempotency_key="submit", expected_revision=1)
    state = controller.lease("receipt-resume", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    payload = {
        "task_id": "a",
        "owner": "worker",
        "fencing_token": lease["fencing_token"],
        "result": success_mapping(),
    }
    original_write = controller_module.atomic_write_json
    crashed = {"value": False}

    def write_with_one_crash(path, value):
        if "receipts" in path.parts and not crashed["value"]:
            crashed["value"] = True
            raise OSError("simulated receipt crash")
        return original_write(path, value)

    monkeypatch.setattr(controller_module, "atomic_write_json", write_with_one_crash)
    with pytest.raises(OSError, match="simulated receipt crash"):
        controller.advance("receipt-resume", payload, "advance", 3)
    assert controller.read_status("receipt-resume")["revision"] == 4

    resumed = controller.advance("receipt-resume", payload, "advance", 3)
    assert resumed["status"] == "succeeded"
    run_dir = tmp_path / "home" / "runtime" / "v1" / "runs" / "receipt-resume"
    assert len(list((run_dir / "receipts").glob("000004-a-*.json"))) == 1
    assert (run_dir / "slices" / "a" / "attempt-001.json").exists()
    assert (run_dir / "receipts" / "graph-receipt.json").exists()


def test_graph_receipt_tamper_is_rejected_on_read_and_idempotent_retry(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "receipt-tamper", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("receipt-tamper", idempotency_key="submit", expected_revision=1)
    state = controller.lease("receipt-tamper", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    payload = {
        "task_id": "a",
        "owner": "worker",
        "fencing_token": lease["fencing_token"],
        "result": success_mapping(),
    }
    controller.advance("receipt-tamper", payload, "advance", 3)
    receipt_path = (
        tmp_path
        / "home"
        / "runtime"
        / "v1"
        / "runs"
        / "receipt-tamper"
        / "receipts"
        / "graph-receipt.json"
    )
    forged = json.loads(receipt_path.read_text())
    forged["structured"]["claims"] = [{"id": "forged", "text": "not authoritative"}]
    receipt_path.write_text(json.dumps(forged, sort_keys=True))

    with pytest.raises(InvalidTransition, match="structured digest mismatch"):
        controller.read_receipt("receipt-tamper")
    with pytest.raises(InvalidTransition, match="structured digest mismatch"):
        controller.advance("receipt-tamper", payload, "advance", 3)


def test_receipt_reconstruction_stays_bound_to_old_attempt_after_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "attempt-receipt", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("attempt-receipt", idempotency_key="submit", expected_revision=1)
    state = controller.lease("attempt-receipt", "worker-one", "lease-one", 2)
    first_lease = state["tasks"]["a"]["lease"]
    first_payload = {
        "task_id": "a",
        "owner": "worker-one",
        "fencing_token": first_lease["fencing_token"],
        "result": {"status": "retry"},
    }
    original_write = controller_module.atomic_write_json
    crashed = {"value": False}

    def write_with_one_crash(path, value):
        if "receipts" in path.parts and not crashed["value"]:
            crashed["value"] = True
            raise OSError("simulated retry receipt crash")
        return original_write(path, value)

    monkeypatch.setattr(controller_module, "atomic_write_json", write_with_one_crash)
    with pytest.raises(OSError, match="simulated retry receipt crash"):
        controller.advance("attempt-receipt", first_payload, "advance-one", 3)

    state = controller.lease(
        "attempt-receipt", "worker-two", "lease-two", 4, task_id="a"
    )
    second_lease = state["tasks"]["a"]["lease"]
    controller.advance("attempt-receipt", first_payload, "advance-one", 3)
    run_dir = tmp_path / "home" / "runtime" / "v1" / "runs" / "attempt-receipt"
    assert (run_dir / "slices" / "a" / "attempt-001.json").exists()
    assert not (run_dir / "slices" / "a" / "attempt-002.json").exists()

    completed = controller.advance(
        "attempt-receipt",
        {
            "task_id": "a",
            "owner": "worker-two",
            "fencing_token": second_lease["fencing_token"],
            "result": success_mapping(),
        },
        "advance-two",
        5,
    )
    assert completed["status"] == "succeeded"
    assert (run_dir / "slices" / "a" / "attempt-002.json").exists()


@pytest.mark.parametrize(
    "result_override",
    [
        {"run_id": "other-run"},
        {"task_id": "other-task"},
        {"attempt_id": "other-attempt"},
        {"lease_id": "other-lease"},
        {"owner": "other-worker"},
        {"fencing_token": 999},
        {"lease": {"active": False, "owner": "worker", "fencing_token": 1}},
        {"lease": {"active": True, "owner": "worker", "token": 999}},
        {"run_id": None},
        {"task_id": ""},
        {"attempt_id": ""},
        {"lease_id": None},
        {"owner": ""},
        {"fencing_token": None},
        {"fencing_token": "1"},
        {"lease": {}},
        {"plan_digest": ""},
        {"plan_id": "wrong"},
        {"context_digest": None},
        {"context_id": "wrong"},
    ],
)
def test_advance_rejects_embedded_result_identity_mismatch(
    tmp_path: Path, result_override: dict[str, object]
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "binding", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("binding", idempotency_key="submit", expected_revision=1)
    state = controller.lease("binding", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="result .*active lease|result lease is not active"):
        controller.advance(
            "binding",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {**success_mapping(), **result_override},
            },
            "advance",
            3,
        )


@pytest.mark.parametrize(
    "usage_override",
    [
        {"cost_tokens": -1},
        {"cost_tokens": 1.5},
        {"usage": {"resources": {"retrieval_tokens": -1}}},
        {"usage": {"resources": {"wall_time_seconds": 0.5}}},
    ],
)
def test_advance_rejects_negative_or_fractional_usage(
    tmp_path: Path, usage_override: dict[str, object]
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "usage", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("usage", idempotency_key="submit", expected_revision=1)
    state = controller.lease("usage", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="usage .* non-negative integer"):
        controller.advance(
            "usage",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {**success_mapping(), **usage_override},
            },
            "advance",
            3,
        )
    assert controller.read_status("usage")["revision"] == 3
    assert controller.read_status("usage")["budget_usage"]["charged_tokens"] == 10


def test_advance_rejects_unknown_usage_resource_dimensions(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "unknown-resource-usage", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit(
        "unknown-resource-usage", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("unknown-resource-usage", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="unknown resource dimensions"):
        controller.advance(
            "unknown-resource-usage",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {
                    **success_mapping(),
                    "usage": {"resources": {"mystery_gpu": 999_999_999}},
                },
            },
            "advance",
            3,
        )
    assert controller.read_status("unknown-resource-usage")["revision"] == 3


def test_advance_rejects_result_larger_than_output_reservation(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "oversized-result", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit(
        "oversized-result", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("oversized-result", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="result output exceeds reservation"):
        controller.advance(
            "oversized-result",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {**success_mapping(), "summary": "X" * 100_000},
            },
            "advance",
            3,
        )
    assert controller.read_status("oversized-result")["revision"] == 3


def test_persisted_result_output_accounting_covers_its_own_fields(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "result-accounting",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "resource_estimates": {
                        "model_tokens": 10,
                        "output_tokens": 5_000,
                    },
                }
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "result-accounting", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("result-accounting", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    zero_usage = {dimension: 0 for dimension in RESOURCE_DIMENSIONS}
    completed = controller.advance(
        "result-accounting",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": {**success_mapping(), "usage": {"resources": zero_usage}},
        },
        "advance",
        3,
    )
    result = completed["tasks"]["a"]["result"]
    measured = (
        len(json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        + 3
    ) // 4
    assert result["usage"]["runtime_output_token_estimate"] >= measured
    assert result["usage"]["resources"]["output_tokens"] >= measured


@pytest.mark.parametrize(
    "outer_binding",
    [
        {"owner": "worker"},
        {"fencing_token": 1},
    ],
)
def test_advance_requires_complete_outer_fencing(
    tmp_path: Path, outer_binding: dict[str, object]
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "outer-fence", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("outer-fence", idempotency_key="submit", expected_revision=1)
    controller.lease("outer-fence", "worker", "lease", 2)
    with pytest.raises(StaleLeaseError, match="missing lease fencing"):
        controller.advance(
            "outer-fence",
            {"task_id": "a", "result": success_mapping(), **outer_binding},
            "advance",
            3,
        )


@pytest.mark.parametrize(
    "outer_binding",
    [
        {"owner": "worker", "fencing_token": True},
        {"owner": "worker", "fencing_token": 1.0},
        {"owner": "worker", "fencing_token": "1"},
    ],
)
def test_advance_rejects_non_int_outer_fencing_token(
    tmp_path: Path, outer_binding: dict[str, object]
) -> None:
    """A fencing token must be an exact int; bool, float, and str are rejected
    by the type guard before the owner/value checks, with a distinct message."""
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "outer-fence", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("outer-fence", idempotency_key="submit", expected_revision=1)
    controller.lease("outer-fence", "worker", "lease", 2)
    with pytest.raises(StaleLeaseError, match="invalid fencing token"):
        controller.advance(
            "outer-fence",
            {"task_id": "a", "result": success_mapping(), **outer_binding},
            "advance",
            3,
        )


@pytest.mark.parametrize(
    "bad_evidence",
    [
        {"id": "e", "status": "unknown", "count": 0},
        {"id": "e", "status": "contradictory", "count": 1},
        {"id": "e", "status": "passed", "count": 0},
        {"id": "e", "status": "passed", "count": 1},
        {},
    ],
)
def test_material_claim_requires_usable_nonzero_evidence(
    tmp_path: Path, bad_evidence: dict[str, object]
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "claim-proof", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("claim-proof", idempotency_key="submit", expected_revision=1)
    state = controller.lease("claim-proof", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="material claims lack usable evidence"):
        controller.advance(
            "claim-proof",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {
                    **success_mapping(),
                    "claims": [
                        {"id": "claim", "text": "material", "evidence_refs": ["e"]}
                    ],
                    "evidence": [bad_evidence],
                },
            },
            "advance",
            3,
        )


def test_acceptance_rejects_unresolved_unknown_evidence(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "acceptance-proof",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "acceptance": [{"id": "criterion"}],
                }
            ],
        },
        "create",
        0,
    )
    controller.submit("acceptance-proof", idempotency_key="submit", expected_revision=1)
    state = controller.lease("acceptance-proof", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="acceptance criterion 1 lacks passing evidence"):
        controller.advance(
            "acceptance-proof",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {
                    **success_mapping(),
                    "acceptance_results": [{"ok": True, "evidence": ["unknown"]}],
                },
            },
            "advance",
            3,
        )


def test_high_impact_requires_bound_independent_reviewer_receipt(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "reviewed",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "risk_tags": ["external_write"],
                }
            ],
        },
        "create",
        0,
    )
    controller.submit("reviewed", idempotency_key="submit", expected_revision=1)
    state = controller.lease("reviewed", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    base_result = success_mapping()
    with pytest.raises(InvalidTransition, match="independent reviewer required"):
        controller.advance(
            "reviewed",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {
                    **base_result,
                    "reviewer": {"id": "made-up", "independent": True},
                },
            },
            "unbound-review",
            3,
        )

    for index, reviewer_alias in enumerate(("worker ", "WORKER"), start=1):
        alias_body = {
            "id": reviewer_alias,
            "independent": True,
            "status": "passed",
            "run_id": "reviewed",
            "task_id": "a",
            "plan_digest": canonical_hash(state["tasks"]["a"]["spec"]),
            "result_digest": canonical_hash(base_result),
            "evidence": [
                {
                    "status": "passed",
                    "count": 1,
                    "source_id": "review:identity-alias",
                }
            ],
        }
        alias_review = {
            **alias_body,
            "receipt_digest": canonical_hash(alias_body),
        }
        with pytest.raises(
            InvalidTransition, match="independent reviewer required"
        ):
            controller.advance(
                "reviewed",
                {
                    "task_id": "a",
                    "owner": "worker",
                    "fencing_token": lease["fencing_token"],
                    "result": {**base_result, "reviewer": alias_review},
                },
                f"identity-alias-{index}",
                3,
            )

    review_body = {
        "id": "reviewer-2",
        "independent": True,
        "status": "passed",
        "run_id": "reviewed",
        "task_id": "a",
        "plan_digest": canonical_hash(state["tasks"]["a"]["spec"]),
        "result_digest": canonical_hash(base_result),
        "evidence": [
            {
                "status": "passed",
                "count": 1,
                "id": "review-proof",
                "source_id": "review:bound-receipt",
            }
        ],
    }
    reviewer = {**review_body, "receipt_digest": canonical_hash(review_body)}
    completed = controller.advance(
        "reviewed",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": {**base_result, "reviewer": reviewer},
        },
        "bound-review",
        3,
    )
    assert completed["status"] == "succeeded"


def test_high_risk_label_cannot_mint_a_reviewer_tag_from_an_unbound_id(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "high-risk-review",
            "tasks": [{"id": "a", "estimated_tokens": 10, "risk": "high"}],
        },
        "create",
        0,
    )
    controller.submit(
        "high-risk-review", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("high-risk-review", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    with pytest.raises(InvalidTransition, match="independent reviewer required"):
        controller.advance(
            "high-risk-review",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {
                    **success_mapping(),
                    "reviewer": {"id": "made-up"},
                },
            },
            "advance",
            3,
        )


@pytest.mark.parametrize("bad_revision", [False, 0.0, "0", -1])
def test_direct_controller_requires_exact_nonnegative_integer_revision(
    tmp_path: Path, bad_revision: object
) -> None:
    controller = RuntimeController(tmp_path / str(type(bad_revision).__name__))
    with pytest.raises(ValueError, match="non-negative integer"):
        controller.create(
            {"run_id": "typed-revision", "tasks": [{"id": "a"}]},
            "create",
            bad_revision,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("operation", ["status", "plan", "events", "receipt"])
def test_unknown_read_does_not_create_run_authority(
    tmp_path: Path, operation: str
) -> None:
    controller = RuntimeController(tmp_path / "home")
    run_dir = controller.root / f"missing-{operation}"
    with pytest.raises(controller_module.ControllerError, match="unknown run"):
        controller.read(operation, f"missing-{operation}")
    assert not run_dir.exists()


def test_all_optional_plan_terminalizes_and_receipts_on_submit(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "all-optional",
            "tasks": [
                {"id": "optional", "estimated_tokens": 10, "required": False}
            ],
        },
        "create",
        0,
    )
    state = controller.submit(
        "all-optional", idempotency_key="submit", expected_revision=1
    )
    assert state["status"] == "succeeded"
    assert state["tasks"]["optional"]["status"] == "canceled"
    receipt = controller.read_receipt("all-optional")
    assert receipt["revision"] == 2
    assert receipt["structured"]["required_task_ids"] == []
    assert receipt["structured"]["optional_task_ids"] == ["optional"]


def test_required_closure_skips_independent_optional_task_and_receipts_it(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "optional-slice",
            "tasks": [
                {"id": "a-required", "estimated_tokens": 10},
                {"id": "z-optional", "estimated_tokens": 10, "required": False},
            ],
        },
        "create",
        0,
    )
    controller.submit("optional-slice", idempotency_key="submit", expected_revision=1)
    state = controller.lease("optional-slice", "worker", "lease", 2)
    task = state["tasks"]["a-required"]
    completed = controller.advance(
        "optional-slice",
        {
            "task_id": "a-required",
            "owner": "worker",
            "fencing_token": task["lease"]["fencing_token"],
            "result": success_mapping(),
        },
        "advance",
        3,
    )
    assert completed["status"] == "succeeded"
    assert completed["tasks"]["z-optional"]["status"] == "canceled"
    assert (
        completed["tasks"]["z-optional"]["result"]["reason"]
        == "optional_task_skipped_after_required_terminal"
    )
    receipt = controller.read_receipt("optional-slice")["structured"]
    assert receipt["required_task_ids"] == ["a-required"]
    assert receipt["optional_task_ids"] == ["z-optional"]
    assert [item["task_id"] for item in receipt["task_results"]] == [
        "a-required",
        "z-optional",
    ]


def test_failed_optional_task_does_not_block_required_success(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "optional-failure",
            "tasks": [
                {"id": "required", "estimated_tokens": 10},
                {"id": "optional", "estimated_tokens": 10, "required": False},
            ],
        },
        "create",
        0,
    )
    controller.submit("optional-failure", idempotency_key="submit", expected_revision=1)
    state = controller.lease(
        "optional-failure", "worker", "lease-optional", 2, task_id="optional"
    )
    optional = state["tasks"]["optional"]
    state = controller.advance(
        "optional-failure",
        {
            "task_id": "optional",
            "owner": "worker",
            "fencing_token": optional["lease"]["fencing_token"],
            "result": {"status": "failed", "blockers": ["optional proof failed"]},
        },
        "advance-optional",
        3,
    )
    assert state["status"] == "running"
    state = controller.lease(
        "optional-failure",
        "worker",
        "lease-required",
        4,
        task_id="required",
    )
    required = state["tasks"]["required"]
    completed = controller.advance(
        "optional-failure",
        {
            "task_id": "required",
            "owner": "worker",
            "fencing_token": required["lease"]["fencing_token"],
            "result": success_mapping(),
        },
        "advance-required",
        5,
    )
    assert completed["status"] == "succeeded"
    receipt = controller.read_receipt("optional-failure")["structured"]
    by_task = {item["task_id"]: item["status"] for item in receipt["task_results"]}
    assert by_task == {"optional": "failed", "required": "succeeded"}
    assert any(item["task_id"] == "optional" for item in receipt["blocked"])


def test_optional_dependency_is_effectively_required(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "optional-dependency",
            "tasks": [
                {"id": "base", "estimated_tokens": 10, "required": False},
                {"id": "final", "estimated_tokens": 10, "depends_on": ["base"]},
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "optional-dependency", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("optional-dependency", "worker", "lease-base", 2)
    base = state["tasks"]["base"]
    state = controller.advance(
        "optional-dependency",
        {
            "task_id": "base",
            "owner": "worker",
            "fencing_token": base["lease"]["fencing_token"],
            "result": success_mapping(),
        },
        "advance-base",
        3,
    )
    assert state["status"] == "running"
    state = controller.lease(
        "optional-dependency", "worker", "lease-final", state["revision"]
    )
    final = state["tasks"]["final"]
    completed = controller.advance(
        "optional-dependency",
        {
            "task_id": "final",
            "owner": "worker",
            "fencing_token": final["lease"]["fencing_token"],
            "result": success_mapping(),
        },
        "advance-final",
        state["revision"],
    )
    assert completed["status"] == "succeeded"
    assert controller.read_receipt("optional-dependency")["structured"][
        "required_task_ids"
    ] == ["base", "final"]


def test_three_slice_blocked_fanin_closes_descendants(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "blocked",
            "tasks": [
                {"id": "a", "estimated_tokens": 20},
                {"id": "b", "estimated_tokens": 20},
                {"id": "join", "depends_on": ["a", "b"], "estimated_tokens": 20},
            ],
        },
        "create",
        0,
    )
    controller.submit("blocked", idempotency_key="submit", expected_revision=1)
    state = controller.lease("blocked", "one", "lease-a", 2, task_id="a")
    state = controller.lease("blocked", "two", "lease-b", 3, task_id="b")
    lease_a = state["tasks"]["a"]["lease"]
    lease_b = state["tasks"]["b"]["lease"]
    controller.advance(
        "blocked",
        {"task_id": "a", "owner": "one", "fencing_token": lease_a["fencing_token"], "result": success_mapping()},
        "advance-a",
        4,
    )
    state = controller.advance(
        "blocked",
        {
            "task_id": "b",
            "owner": "two",
            "fencing_token": lease_b["fencing_token"],
            "result": {"status": "blocked", "blockers": ["external dependency"]},
        },
        "advance-b",
        5,
    )
    assert state["status"] == "blocked"
    assert state["tasks"]["join"]["status"] == "blocked"
    with pytest.raises(InvalidTransition):
        controller.lease("blocked", "three", "late", 6)
    receipt = controller.read_receipt("blocked")
    assert receipt["status"] == "blocked"
    assert {item["task_id"] for item in receipt["structured"]["blocked"]} == {"b", "join"}


def test_controller_fanin_rejects_cross_slice_claim_conflict(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "claim-conflict",
            "tasks": [
                {"id": "a", "estimated_tokens": 10},
                {"id": "b", "estimated_tokens": 10},
            ],
        },
        "create",
        0,
    )
    controller.submit("claim-conflict", idempotency_key="submit", expected_revision=1)
    state = controller.lease("claim-conflict", "worker-a", "lease-a", 2, task_id="a")
    state = controller.lease("claim-conflict", "worker-b", "lease-b", 3, task_id="b")
    lease_a = state["tasks"]["a"]["lease"]
    lease_b = state["tasks"]["b"]["lease"]

    def claimed(text: str, evidence_id: str) -> dict[str, object]:
        return {
            **success_mapping(),
            "claims": [
                {
                    "id": "shared",
                    "text": text,
                    "evidence_refs": [evidence_id],
                }
            ],
            "evidence": [
                {
                    "id": evidence_id,
                    "status": "passed",
                    "count": 1,
                    "source_id": f"test:{evidence_id}",
                }
            ],
        }

    controller.advance(
        "claim-conflict",
        {
            "task_id": "a",
            "owner": "worker-a",
            "fencing_token": lease_a["fencing_token"],
            "result": claimed("first conclusion", "proof-a"),
        },
        "advance-a",
        4,
    )
    with pytest.raises(InvalidTransition, match="fan-in gate failed: shared"):
        controller.advance(
            "claim-conflict",
            {
                "task_id": "b",
                "owner": "worker-b",
                "fencing_token": lease_b["fencing_token"],
                "result": claimed("different conclusion", "proof-b"),
            },
            "advance-b",
            5,
        )
    state = controller.read_status("claim-conflict")
    assert state["status"] == "running"
    assert state["tasks"]["b"]["status"] == "leased"
    assert controller.read_receipt("claim-conflict")["provisional"] is True


def test_cancel_writes_and_idempotently_repairs_terminal_graph_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "cancel-receipt", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("cancel-receipt", idempotency_key="submit", expected_revision=1)
    original_write = controller_module.atomic_write_json
    crashed = {"value": False}

    def write_with_one_crash(path, value):
        if path.name == "graph-receipt.json" and not crashed["value"]:
            crashed["value"] = True
            raise OSError("simulated cancel receipt crash")
        return original_write(path, value)

    monkeypatch.setattr(controller_module, "atomic_write_json", write_with_one_crash)
    with pytest.raises(OSError, match="simulated cancel receipt crash"):
        controller.cancel("cancel-receipt", "stop", "cancel", 2)
    assert controller.read_status("cancel-receipt")["status"] == "canceled"

    state = controller.cancel("cancel-receipt", "stop", "cancel", 2)
    assert state["revision"] == 3
    receipt = controller.read_receipt("cancel-receipt")
    assert receipt["status"] == "canceled"
    assert receipt.get("provisional") is not True
    assert receipt["structured"]["task_results"][0]["status"] == "canceled"


def test_create_without_run_id_is_cross_process_idempotent(tmp_path: Path) -> None:
    request = {"tasks": [{"id": "a", "estimated_tokens": 10}]}
    first = RuntimeController(tmp_path).create(request, "same-create", 0)
    second = RuntimeController(tmp_path).create(request, "same-create", 0)
    assert second["run_id"] == first["run_id"]
    with pytest.raises(IdempotencyConflict):
        RuntimeController(tmp_path).create(
            {"tasks": [{"id": "different", "estimated_tokens": 10}]},
            "same-create",
            0,
        )


def test_conflicting_concurrent_leases_are_serialized(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "race",
            "workspace_root": str(tmp_path),
            "tasks": [
                {"id": "a", "estimated_tokens": 10, "write_set": ["shared"]},
                {"id": "b", "estimated_tokens": 10, "write_set": ["shared/file"]},
            ],
        },
        "create",
        0,
    )
    controller.submit("race", idempotency_key="submit", expected_revision=1)

    def acquire(task_id: str) -> tuple[str, str]:
        try:
            RuntimeController(tmp_path).lease(
                "race", task_id, f"lease-{task_id}", 2, task_id=task_id
            )
            return task_id, "leased"
        except Exception as exc:
            return task_id, type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = dict(pool.map(acquire, ("a", "b")))
    assert list(outcomes.values()).count("leased") == 1
    state = RuntimeController(tmp_path).read_status("race")
    assert sum(item["status"] == "leased" for item in state["tasks"].values()) == 1
    pending = next(task_id for task_id, item in state["tasks"].items() if item["status"] == "pending")
    with pytest.raises(InvalidTransition, match="paths conflict"):
        RuntimeController(tmp_path).lease(
            "race", "retry", f"retry-{pending}", 3, task_id=pending
        )


def test_event_payload_alias_tamper_fails_closed(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "tamper", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    path = tmp_path / "runtime" / "v1" / "runs" / "tamper" / "events.jsonl"
    event = json.loads(path.read_text())
    event["payload_digest"] = "0" * 64
    path.write_text(json.dumps(event) + "\n")
    with pytest.raises(EventIntegrityError):
        controller.submit("tamper", idempotency_key="submit", expected_revision=1)


def test_mcp_and_cli_share_sips_home_but_preserve_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_home = tmp_path / "sips-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("SIPS_HOME", str(runtime_home))
    created = runtime_tool_payload(
        workspace,
        "create",
        json.dumps(
            {
                "run_id": "parity",
                "idempotency_key": "create",
                "expected_revision": 0,
                "tasks": [{"id": "a", "estimated_tokens": 10}],
            }
        ),
        write=True,
    )
    assert created["ok"] is True
    environment = dict(os.environ, SIPS_HOME=str(runtime_home))
    cli = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "read",
            "--op",
            "status",
            "--json",
            json.dumps({"run_id": "parity"}),
            "--detail",
            "full",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert cli.returncode == 0, cli.stderr
    status = json.loads(cli.stdout)
    assert status["data"]["head_hash"] == created["data"]["head_hash"]
    assert status["data"]["workspace_root"] == str(workspace.resolve())
    assert (
        runtime_home / "runtime" / "v1" / "runs" / "parity" / "events.jsonl"
    ).exists()


def test_fanin_is_permutation_invariant_and_rejects_result_conflicts() -> None:
    base = {
        "run_id": "r",
        "attempt_id": "a",
        "lease_id": "l",
        "fencing_token": 1,
        "plan_digest": "p",
        "context_digest": "c",
        "owner": "worker",
        "lease": {"active": True, "owner": "worker", "fencing_token": 1},
        "status": "succeeded",
        "changed_paths": [],
    }
    left = {**base, "task_id": "left", "slice_id": "left", "claims": [{"id": "same", "text": "left"}]}
    right = {**base, "task_id": "right", "slice_id": "right", "claims": [{"id": "same", "text": "right"}]}
    first = fan_in([left, right], allowed_paths={"left": [], "right": []})
    second = fan_in([right, left], allowed_paths={"left": [], "right": []})
    assert canonical_hash(first) == canonical_hash(second)
    conflict = fan_in(
        [left, {**left, "attempt_id": "different"}],
        expected_task_ids=["left"],
        allowed_paths={"left": []},
    )
    assert conflict["ok"] is False
    assert conflict["result_conflicts"][0]["task_id"] == "left"


def test_promotion_is_candidate_first_receipt_bound_and_idempotent(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "promotion", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("promotion", idempotency_key="submit", expected_revision=1)
    state = controller.lease("promotion", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    reservation = state["tasks"]["a"]["reservation"]["resources"]
    controller.advance(
        "promotion",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": reservation},
            },
        },
        "advance",
        3,
    )
    store = tmp_path / "memory.jsonl"
    request = {
        "run_id": "promotion",
        "idempotency_key": "promote",
        "expected_revision": 4,
        "activate": True,
        "memory_store": str(store),
        "lesson": {
            "title": "Receipt-bound lesson",
            "text": "Symptom: stale claim. Fix: bind the receipt. Proof: promotion audit passed.",
            "tags": ["integration"],
            "conflict_audit": {"ok": True},
            "usage": {
                "unknown_dimensions": [],
                "efficiency_claim_eligible": True,
            },
        },
    }
    first = RuntimeAPI(controller=controller).write("promote", request)
    assert first["ok"] is True
    assert first["data"]["promotion"]["activated"] is True
    assert (
        first["data"]["promotion"]["candidate"]["conflict_audit"]["source"]
        == "graph_receipt_and_memory_store"
    )
    events = controller.read_events("promotion")
    assert [event["event_type"] for event in events[-2:]] == [
        "memory.promotion.candidate",
        "memory.promotion.receipt",
    ]
    record = json.loads(store.read_text())
    assert record["run_id"] == "promotion"
    assert record["receipt_digest"] == controller.read_receipt("promotion")["digest"]
    retried = RuntimeAPI(controller=RuntimeController(tmp_path / "home")).write(
        "promote", request
    )
    assert retried["ok"] is True
    assert retried["revision"] == first["revision"]
    assert len(store.read_text().splitlines()) == 1


def test_promotion_cannot_claim_efficiency_when_provider_usage_is_unknown(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "unknown-usage-promotion", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit(
        "unknown-usage-promotion", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("unknown-usage-promotion", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    controller.advance(
        "unknown-usage-promotion",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": success_mapping(),
        },
        "advance",
        3,
    )
    store = tmp_path / "must-not-exist.jsonl"
    result = controller.promote(
        "unknown-usage-promotion",
        {
            "text": "Symptom: unknown usage. Fix: fail closed. Proof: no active record.",
            "usage": {
                "unknown_dimensions": [],
                "efficiency_claim_eligible": True,
            },
        },
        activate=True,
        memory_store=store,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert result["promotion"]["activated"] is False
    assert result["promotion"]["candidate"]["audits"]["usage"]["ok"] is False
    assert not store.exists()


def test_promotion_rejects_forged_record_with_expected_id(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "promotion-forgery", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("promotion-forgery", idempotency_key="submit", expected_revision=1)
    state = controller.lease("promotion-forgery", "worker", "lease", 2)
    task = state["tasks"]["a"]
    controller.advance(
        "promotion-forgery",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": task["lease"]["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": task["reservation"]["resources"]},
            },
        },
        "advance",
        3,
    )
    lesson = {
        "text": "Symptom: forged resume. Fix: compare content. Proof: conflict receipt.",
        "tags": ["integration"],
    }
    memory_store = tmp_path / "forged-memory.jsonl"
    candidate_state = controller.promote(
        "promotion-forgery",
        lesson,
        activate=False,
        memory_store=memory_store,
        idempotency_key="candidate",
        expected_revision=4,
    )
    candidate = candidate_state["promotion"]["candidate"]
    receipt = controller.read_receipt("promotion-forgery")
    bound = {
        **lesson,
        "run_id": "promotion-forgery",
        "receipt_digest": receipt["digest"],
        "evidence_path": str(
            controller.root
            / "promotion-forgery"
            / "receipts"
            / "graph-receipt.json"
        ),
        "provenance_type": "source_backed_agent_run",
        "usage": candidate["usage"],
        "conflict_audit": candidate["conflict_audit"],
    }
    record_id = "mem_graph_" + canonical_hash(
        {
            "run_id": "promotion-forgery",
            "receipt_digest": receipt["digest"],
            "lesson": lesson,
        }
    )[:20]
    forged = {"schema_version": "1.0", "id": record_id, "body": "FORGED"}
    memory_store.write_text(json.dumps(forged) + "\n", encoding="utf-8")
    activated = controller.promote(
        "promotion-forgery",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="activate",
        expected_revision=5,
    )
    assert activated["promotion"]["activated"] is False
    assert "different content" in activated["promotion"]["error"]
    assert json.loads(memory_store.read_text(encoding="utf-8")) == forged


def test_promotion_verifies_memory_writer_postcondition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "promotion-noop-writer", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit(
        "promotion-noop-writer", idempotency_key="submit", expected_revision=1
    )
    state = controller.lease("promotion-noop-writer", "worker", "lease", 2)
    task = state["tasks"]["a"]
    controller.advance(
        "promotion-noop-writer",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": task["lease"]["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": task["reservation"]["resources"]},
            },
        },
        "advance",
        3,
    )
    import memory_fabric_jsonl

    monkeypatch.setattr(
        memory_fabric_jsonl,
        "append_record",
        lambda *_args, **_kwargs: {"ok": True},
    )
    target = tmp_path / "noop-memory.jsonl"
    result = controller.promote(
        "promotion-noop-writer",
        {
            "text": "Symptom: no-op writer. Fix: verify postcondition. Proof: failed promotion.",
        },
        activate=True,
        memory_store=target,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert result["promotion"]["activated"] is False
    assert "without persisting" in result["promotion"]["error"]
    assert not target.exists()
    assert controller.read_events("promotion-noop-writer")[-1]["event_type"] == "memory.promotion.failed"


def test_promotion_retry_completes_receipt_after_post_writer_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "promotion-resume", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("promotion-resume", idempotency_key="submit", expected_revision=1)
    state = controller.lease("promotion-resume", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    reservation = state["tasks"]["a"]["reservation"]["resources"]
    controller.advance(
        "promotion-resume",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": reservation},
            },
        },
        "advance",
        3,
    )
    memory_store = tmp_path / "resume-memory.jsonl"
    lesson = {
        "text": "Symptom: receipt append crash. Fix: resume intent. Proof: one durable record.",
        "tags": ["integration"],
    }
    original_append = EventStore.append
    crashed = {"value": False}

    def append_with_one_crash(self, event_type, *args, **kwargs):
        if event_type == "memory.promotion.receipt" and not crashed["value"]:
            crashed["value"] = True
            raise RuntimeError("simulated post-writer crash")
        return original_append(self, event_type, *args, **kwargs)

    monkeypatch.setattr(EventStore, "append", append_with_one_crash)
    with pytest.raises(RuntimeError, match="simulated post-writer crash"):
        controller.promote(
            "promotion-resume",
            lesson,
            activate=True,
            memory_store=memory_store,
            idempotency_key="promote",
            expected_revision=4,
        )
    assert len(memory_store.read_text().splitlines()) == 1

    interleaved = controller.promote(
        "promotion-resume",
        {
            "text": "Symptom: second candidate. Fix: keep intent separate. Proof: linked digests.",
            "tags": ["integration"],
        },
        activate=False,
        memory_store=memory_store,
        idempotency_key="other-candidate",
        expected_revision=5,
    )
    assert interleaved["revision"] == 6

    resumed = controller.promote(
        "promotion-resume",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert resumed["promotion"]["activated"] is True
    assert len(memory_store.read_text().splitlines()) == 1
    events = controller.read_events("promotion-resume")
    assert [event["event_type"] for event in events[-3:]] == [
        "memory.promotion.candidate",
        "memory.promotion.candidate",
        "memory.promotion.receipt",
    ]
    assert events[-1]["payload"]["candidate_event_digest"] == events[-3]["event_digest"]


def test_promotion_accepts_persisted_record_when_writer_raises_after_fsync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    complete_promotable_run(controller, "promotion-ambiguous-writer")
    memory_store = tmp_path / "ambiguous-memory.jsonl"
    lesson = {
        "text": "Symptom: ambiguous writer return. Fix: verify the durable record. Proof: one receipt-bound line.",
    }
    import memory_fabric_jsonl

    original_writer = memory_fabric_jsonl.append_record

    def persist_then_raise(record, path):
        original_writer(record, path)
        raise OSError("simulated failure after durable append")

    monkeypatch.setattr(memory_fabric_jsonl, "append_record", persist_then_raise)
    promoted = controller.promote(
        "promotion-ambiguous-writer",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert promoted["promotion"]["activated"] is True
    assert promoted["promotion"]["writer_outcome"] == "persisted_despite_writer_exception"
    assert len(memory_store.read_text(encoding="utf-8").splitlines()) == 1
    assert controller.read_events("promotion-ambiguous-writer")[-1]["event_type"] == "memory.promotion.receipt"

    retried = controller.promote(
        "promotion-ambiguous-writer",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert retried["promotion"]["activated"] is True
    assert len(memory_store.read_text(encoding="utf-8").splitlines()) == 1


def test_promotion_resume_reaudits_mutated_memory_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    complete_promotable_run(controller, "promotion-reaudit")
    memory_store = tmp_path / "reaudit-memory.jsonl"
    memory_store.write_text(
        json.dumps({"id": "memory-base", "status": "active", "body": "anchor"}) + "\n",
        encoding="utf-8",
    )
    lesson = {
        "text": "Symptom: stale eligibility. Fix: re-audit on resume. Proof: dangling reference blocks activation.",
        "references": [{"type": "references", "target_id": "memory-base"}],
    }
    import memory_fabric_jsonl

    original_writer = memory_fabric_jsonl.append_record

    def interrupt_before_write(*_args, **_kwargs):
        raise KeyboardInterrupt("simulated process loss after candidate event")

    monkeypatch.setattr(memory_fabric_jsonl, "append_record", interrupt_before_write)
    with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
        controller.promote(
            "promotion-reaudit",
            lesson,
            activate=True,
            memory_store=memory_store,
            idempotency_key="promote",
            expected_revision=4,
        )
    assert controller.read_events("promotion-reaudit")[-1]["event_type"] == "memory.promotion.candidate"

    memory_store.write_text("", encoding="utf-8")
    monkeypatch.setattr(memory_fabric_jsonl, "append_record", original_writer)
    resumed = controller.promote(
        "promotion-reaudit",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="promote",
        expected_revision=4,
    )
    promotion = resumed["promotion"]
    assert promotion["activated"] is False
    assert promotion["candidate"]["audits"]["dangling_references"] == {
        "ok": False,
        "dangling": ["memory-base"],
    }
    assert memory_store.read_text(encoding="utf-8") == ""
    assert controller.read_events("promotion-reaudit")[-1]["event_type"] == "memory.promotion.failed"


def test_promotion_rejects_caller_spoofed_known_memory_ids(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path / "home")
    complete_promotable_run(controller, "promotion-spoofed-reference")
    memory_store = tmp_path / "empty-memory.jsonl"
    lesson = {
        "text": "Symptom: caller-spoofed reference. Fix: audit the real store. Proof: activation fails closed.",
        "known_record_ids": ["never-existed"],
        "references": [{"type": "references", "target_id": "never-existed"}],
    }
    result = controller.promote(
        "promotion-spoofed-reference",
        lesson,
        activate=True,
        memory_store=memory_store,
        idempotency_key="promote",
        expected_revision=4,
    )
    assert result["promotion"]["activated"] is False
    assert result["promotion"]["candidate"]["known_record_ids"] == []
    assert result["promotion"]["candidate"]["audits"]["dangling_references"]["ok"] is False
    assert not memory_store.exists()


def test_promotion_candidate_retry_rejects_implicit_target_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RuntimeController(tmp_path / "home")
    complete_promotable_run(controller, "promotion-target-drift")
    first_store = tmp_path / "memory-a.jsonl"
    second_store = tmp_path / "memory-b.jsonl"
    lesson = {
        "text": "Symptom: implicit target drift. Fix: bind resolved path. Proof: retry conflict.",
    }
    import memory_fabric_jsonl

    original_writer = memory_fabric_jsonl.append_record
    monkeypatch.setenv("CODEX_MEMORY_FABRIC_STORE", str(first_store))
    monkeypatch.setattr(
        memory_fabric_jsonl,
        "append_record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            KeyboardInterrupt("simulated process loss")
        ),
    )
    with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
        controller.promote(
            "promotion-target-drift",
            lesson,
            activate=True,
            idempotency_key="promote",
            expected_revision=4,
        )

    monkeypatch.setenv("CODEX_MEMORY_FABRIC_STORE", str(second_store))
    monkeypatch.setattr(memory_fabric_jsonl, "append_record", original_writer)
    with pytest.raises(IdempotencyConflict, match="payload changed"):
        controller.promote(
            "promotion-target-drift",
            lesson,
            activate=True,
            idempotency_key="promote",
            expected_revision=4,
        )
    assert not first_store.exists()
    assert not second_store.exists()


def test_failed_memory_writer_preserves_candidate_and_never_claims_activation(
    tmp_path: Path,
) -> None:
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {"run_id": "writer-failure", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("writer-failure", idempotency_key="submit", expected_revision=1)
    state = controller.lease("writer-failure", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    reservation = state["tasks"]["a"]["reservation"]["resources"]
    controller.advance(
        "writer-failure",
        {
            "task_id": "a",
            "owner": "worker",
            "fencing_token": lease["fencing_token"],
            "result": {
                **success_mapping(),
                "usage": {"resources": reservation},
            },
        },
        "advance",
        3,
    )
    unwritable_target = tmp_path / "memory-target-is-a-directory"
    unwritable_target.mkdir()
    response = RuntimeAPI(controller=controller).write(
        "promote",
        {
            "run_id": "writer-failure",
            "idempotency_key": "promote",
            "expected_revision": 4,
            "activate": True,
            "memory_store": str(unwritable_target),
            "lesson": {
                "text": "Symptom: writer unavailable. Fix: preserve candidate. Proof: failed receipt.",
                "tags": "integration",
            },
        },
    )
    assert response["ok"] is False
    promotion = response["data"]["promotion"]
    assert promotion["activated"] is False
    assert promotion["candidate"]["status"] == "candidate"
    assert promotion["candidate"]["verify_before_use"] is True
    events = controller.read_events("writer-failure")
    assert [event["event_type"] for event in events[-2:]] == [
        "memory.promotion.candidate",
        "memory.promotion.failed",
    ]
    assert "Memory Fabric writer failed" in promotion["error"]


def test_multidimensional_budget_tranches_and_attempt_ceiling(tmp_path: Path) -> None:
    ledger = BudgetLedger(
        60,
        120,
        {
            "model_tokens": 120,
            "retrieval_tokens": 20,
            "output_tokens": 20,
            "delegations": 2,
            "tool_calls": 2,
            "repairs": 1,
            "wall_time_seconds": 900,
            "memory_bytes": 1_024,
        },
    )
    reservation = ledger.reserve(
        "task",
        30,
        {
            "model_tokens": 30,
            "retrieval_tokens": 10,
            "output_tokens": 10,
            "delegations": 1,
            "tool_calls": 2,
            "repairs": 1,
            "wall_time_seconds": 900,
            "memory_bytes": 512,
        },
    )
    assert reservation.resources["tool_calls"] == 2
    assert ledger.snapshot()["tranche_percentages"] == [30, 35, 35]
    assert ledger.snapshot()["released_tranches"] == 1
    with pytest.raises(HardBudgetExceeded):
        ledger.reserve(
            "too-many-tools",
            1,
            {
                "model_tokens": 1,
                "retrieval_tokens": 0,
                "output_tokens": 0,
                "delegations": 0,
                "tool_calls": 1,
                "repairs": 0,
                "wall_time_seconds": 0,
                "memory_bytes": 0,
            },
        )
    with pytest.raises(ValueError, match="model_tokens"):
        RuntimeController(tmp_path).create(
            {
                "run_id": "bypass",
                "soft_budget": 60,
                "hard_budget": 120,
                "resource_limits": {"model_tokens": 999},
                "tasks": [{"id": "a", "estimated_tokens": 200}],
            },
            "create",
            0,
        )

    now = [0.0]
    leases = LeaseManager(clock=lambda: now[0])
    lease = leases.acquire("task", "worker")
    for heartbeat_at in range(89, 891, 89):
        now[0] = float(heartbeat_at)
        leases.heartbeat("task", "worker", lease.fencing_token)
    now[0] = 900.0
    with pytest.raises(StaleLeaseError):
        leases.heartbeat("task", "worker", lease.fencing_token)


def test_controller_records_automatic_tranche_release_with_lease(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "tranches",
            "soft_budget": 60,
            "hard_budget": 120,
            "tasks": [{"id": "a", "estimated_tokens": 40}],
        },
        "create",
        0,
    )
    controller.submit("tranches", idempotency_key="submit", expected_revision=1)
    state = controller.lease("tranches", "worker", "lease", 2)
    assert state["budget_usage"]["released_tranches"] == 2
    assert state["budget_usage"]["released_token_limit"] == 78
    lease_event = controller.read_events("tranches")[-1]
    assert lease_event["payload"]["tranche_release"] == {
        "advanced": True,
        "reason": "accepted_reservation_demand",
        "released_after": 2,
        "released_before": 1,
        "released_token_limit": 78,
        "tranche_limits": [36, 78, 120],
    }


def test_controller_heartbeat_loss_expires_persisted_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1_000.0]
    monkeypatch.setattr(controller_module.time, "time", lambda: now[0])
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "heartbeat-loss", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("heartbeat-loss", idempotency_key="submit", expected_revision=1)
    state = controller.lease("heartbeat-loss", "worker", "lease", 2)
    lease = state["tasks"]["a"]["lease"]
    assert lease["next_heartbeat_due"] == 1_015.0
    now[0] = 1_091.0
    with pytest.raises(StaleLeaseError, match="stale fencing token"):
        controller.advance(
            "heartbeat-loss",
            {
                "task_id": "a",
                "owner": "worker",
                "fencing_token": lease["fencing_token"],
                "result": {"status": "running"},
            },
            "late-heartbeat",
            3,
        )


def test_attempt_ceiling_caps_heartbeat_and_allows_fenced_reacquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1_000.0]
    monkeypatch.setattr(controller_module.time, "time", lambda: now[0])
    controller = RuntimeController(tmp_path)
    controller.create(
        {"run_id": "attempt-cap", "tasks": [{"id": "a", "estimated_tokens": 10}]},
        "create",
        0,
    )
    controller.submit("attempt-cap", idempotency_key="submit", expected_revision=1)
    state = controller.lease("attempt-cap", "worker-one", "lease-one", 2)
    first = state["tasks"]["a"]["lease"]
    # Keep the 90-second lease alive, then prove renewals cannot extend the
    # original attempt beyond its absolute 900-second ceiling.
    for heartbeat, timestamp in enumerate([*range(1_080, 1_890, 80), 1_890], start=1):
        now[0] = float(timestamp)
        state = controller.advance(
            "attempt-cap",
            {
                "task_id": "a",
                "owner": "worker-one",
                "fencing_token": first["fencing_token"],
                "result": {"status": "running"},
            },
            f"heartbeat-{heartbeat}",
            state["revision"],
        )
    assert state["tasks"]["a"]["lease"]["expires_at"] == 1_900.0
    now[0] = 1_901.0
    state = controller.lease(
        "attempt-cap", "worker-two", "lease-two", state["revision"], task_id="a"
    )
    second = state["tasks"]["a"]["lease"]
    assert second["fencing_token"] > first["fencing_token"]
    assert state["tasks"]["a"]["attempts"] == 2
    # The abandoned attempt's reservation is charged, so the retry is not free.
    assert state["budget_usage"]["charged_tokens"] == 20


def test_required_untrusted_context_blocks_lease(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "context",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "required_sources": [
                        {
                            "id": "required",
                            "scope": "repo",
                            "status": "active",
                            "trust": "context_only",
                            "text": "unverified",
                        }
                    ],
                }
            ],
        },
        "create",
        0,
    )
    controller.submit("context", idempotency_key="submit", expected_revision=1)
    with pytest.raises(InvalidTransition, match="required context source missing"):
        controller.lease("context", "worker", "lease", 2)


def test_required_context_without_provenance_blocks_lease(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "context-provenance",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "required_sources": [
                        {
                            "id": "required",
                            "scope": "repo",
                            "status": "active",
                            "trust": "ready",
                            "text": "missing provenance",
                        }
                    ],
                }
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "context-provenance", idempotency_key="submit", expected_revision=1
    )
    with pytest.raises(InvalidTransition, match="required context source missing"):
        controller.lease("context-provenance", "worker", "lease", 2)


def test_controller_context_query_preserves_frontier_trust_and_seed_ids(
    tmp_path: Path,
) -> None:
    memory_store = tmp_path / "memory.jsonl"
    memory_store.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "id": "trusted-seed",
                "tier": "knowledge",
                "title": "Needle runtime record",
                "body": "needle context backed by source evidence",
                "scope": "project/foo",
                "tags": ["runtime"],
                "provenance": {
                    "type": "source_file",
                    "evidence_path": str(tmp_path / "proof.txt"),
                },
                "confidence": "high",
                "verify_before_use": False,
                "status": "active",
                "created_at": "2026-07-18T00:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "frontier-context",
            "memory_store": str(memory_store),
            "memory_scope": "project/foo",
            "tasks": [
                {
                    "id": "a",
                    "estimated_tokens": 10,
                    "context_query": "needle",
                }
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "frontier-context", idempotency_key="submit", expected_revision=1
    )
    leased = controller.lease("frontier-context", "worker", "lease", 2)
    context = leased["tasks"]["a"]["context"]
    assert context["selected_ids"] == ["trusted-seed"]
    assert context["records"][0]["trust"]["status"] == "ready"
    assert context["frontier"]["seed_ids"] == ["trusted-seed"]
    assert context["frontier"]["node_count"] == 1
    reservation = leased["tasks"]["a"]["reservation"]["resources"]
    assert context["estimated_tokens"] <= reservation["retrieval_tokens"]
    assert len(json.dumps(context, sort_keys=True).encode("utf-8")) <= reservation["memory_bytes"]


def test_controller_context_handoff_never_exceeds_retrieval_reservation(
    tmp_path: Path,
) -> None:
    memory_store = tmp_path / "large-memory.jsonl"
    memory_store.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "id": "large-seed",
                "tier": "knowledge",
                "title": "Needle large record",
                "body": "needle " + "X" * 15_500,
                "scope": "project/large",
                "tags": ["runtime"],
                "provenance": {
                    "type": "source_file",
                    "evidence_path": str(tmp_path / "proof.txt"),
                },
                "confidence": "high",
                "verify_before_use": False,
                "status": "active",
                "created_at": "2026-07-18T00:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "bounded-context",
            "memory_store": str(memory_store),
            "memory_scope": "project/large",
            "tasks": [
                {"id": "a", "estimated_tokens": 10, "context_query": "needle"}
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "bounded-context", idempotency_key="submit", expected_revision=1
    )
    leased = controller.lease("bounded-context", "worker", "lease", 2)
    task = leased["tasks"]["a"]
    assert (
        task["context"]["response_token_estimate"]
        <= task["reservation"]["resources"]["retrieval_tokens"]
    )
    assert "X" * 1_000 not in json.dumps(task["context"], sort_keys=True)


def test_controller_context_preserves_frontier_omission_and_truncation_ledger(
    tmp_path: Path,
) -> None:
    memory_store = tmp_path / "memory.jsonl"
    rows = []
    for record_id in ("a", "b"):
        rows.append(
            {
                "schema_version": "1.0",
                "id": record_id,
                "tier": "knowledge",
                "title": f"needle {record_id}",
                "body": "X" * 20_000,
                "scope": "project/foo",
                "tags": ["runtime"],
                "provenance": {
                    "type": "source_file",
                    "evidence_path": str(tmp_path / f"{record_id}.txt"),
                },
                "confidence": "high",
                "verify_before_use": False,
                "status": "active",
                "created_at": f"2026-07-18T00:00:0{record_id == 'b'}Z",
            }
        )
    memory_store.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    controller = RuntimeController(tmp_path / "home")
    controller.create(
        {
            "run_id": "frontier-omissions",
            "memory_store": str(memory_store),
            "memory_scope": "project/foo",
            "tasks": [
                {"id": "task", "estimated_tokens": 10, "context_query": "needle"}
            ],
        },
        "create",
        0,
    )
    controller.submit(
        "frontier-omissions", idempotency_key="submit", expected_revision=1
    )
    leased = controller.lease("frontier-omissions", "worker", "lease", 2)
    context = leased["tasks"]["task"]["context"]
    assert context["frontier"]["truncated"] is True
    assert context["frontier"]["truncation"]["tokens"] is True
    assert context["frontier"]["omitted_ids"]
    omitted = [
        item
        for item in context["omitted"]
        if item.get("stage") == "memory_frontier"
    ]
    assert omitted
    assert omitted[0]["reason"] == "frontier_token_budget"
    assert omitted[0]["provenance"]["type"] == "source_file"
    assert omitted[0]["token_estimate"] > 4_000
