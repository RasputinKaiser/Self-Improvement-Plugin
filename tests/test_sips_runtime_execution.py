from __future__ import annotations

import json

import pytest

from sips_runtime.adapters import import_legacy
from sips_runtime.api import RuntimeAPI
from sips_runtime.context import build_context_packet
from sips_runtime.fanin import fan_in, validate_slice_result
from sips_runtime.projection import GraphReceipt, make_graph_receipt
from sips_runtime.promotion import promote_lesson
from sips_runtime.quality import evaluate_gates, validate_evidence_items


def _structured(task_id: str, *, status: str = "done", claims=None):
    return {
        "run_id": "run-1",
        "task_id": task_id,
        "slice_id": task_id,
        "attempt_id": "attempt-1",
        "lease_id": "lease-1",
        "owner": "worker",
        "fence_token": 1,
        "plan_id": "plan-1",
        "context_id": "context-1",
        "lease": {"active": True, "owner": "worker", "fencing_token": 1},
        "status": status,
        "changed_paths": ["src/a.py"],
        "claims": claims or [],
    }


def test_context_required_first_and_trust_omissions():
    packet = build_context_packet(
        [
            {"id": "optional", "scope": "repo", "status": "active", "trust": "ready", "text": "other", "provenance": {"type": "test"}},
            {"id": "required", "scope": "repo", "status": "active", "trust": "ready", "text": "needed", "provenance": {"type": "test"}},
            {"id": "bad", "scope": "repo", "status": "active", "trust": "context_only", "text": "ignore"},
        ],
        required_sources=["required"],
        scope="repo",
        query="needed",
    )
    assert packet["selected_ids"] == ["required"]
    assert any(item["id"] == "bad" for item in packet["omitted"])


def test_context_fails_closed_when_required_source_is_unavailable():
    packet = build_context_packet(
        [
            {
                "id": "required",
                "scope": "repo",
                "status": "active",
                "trust": "context_only",
                "text": "not yet verified",
            }
        ],
        required_sources=["required"],
        scope="repo",
    )
    assert packet["ok"] is False
    assert packet["error"] == "required_sources_unavailable"
    assert packet["required_sources_unavailable"] == ["required"]


def test_context_never_fabricates_trust_for_missing_provenance():
    packet = build_context_packet(
        [
            {
                "id": "required",
                "scope": "repo",
                "status": "active",
                "text": "no provenance",
            }
        ],
        required_sources=["required"],
        scope="repo",
    )
    assert packet["ok"] is False
    assert packet["selected_ids"] == []
    assert packet["required_sources_unavailable"] == ["required"]
    assert any(
        item["id"] == "required" and item["reason"] == "trust_excluded"
        for item in packet["omitted"]
    )


@pytest.mark.parametrize(
    "field,value",
    [("verify_before_use", 0), ("verify_before_use", "false"), ("superseded", 0)],
)
def test_context_invalid_trust_flags_fail_closed(field, value):
    record = {
        "id": "invalid-flag",
        "scope": "repo",
        "status": "active",
        "trust": "ready",
        "text": "must not be admitted",
        "provenance": {"type": "source_file"},
        field: value,
    }
    packet = build_context_packet([record], scope="repo", query="admitted")
    assert packet["selected_ids"] == []
    assert packet["omitted"][0]["reason"] in {"trust_excluded", "trust_not_ready"}


def test_context_rejects_broad_scan_and_scope_prefix():
    broad = build_context_packet([{"id": "a"}])
    assert broad["ok"] is False
    packet = build_context_packet(
        [{"id": "a", "scope": "repo", "status": "active", "trust": "ready", "text": "needle", "provenance": {"type": "test"}}],
        query="scope:repo needle",
    )
    assert packet["ok"] is True and packet["selected_ids"] == ["a"]


def test_context_packet_bounds_task_query_and_omission_envelope():
    records = [
        {
            "id": f"record-{index}",
            "scope": "repo",
            "status": "active",
            "trust": "ready",
            "text": "unrelated",
            "provenance": {"type": "source_file", "blob": "X" * 100_000},
        }
        for index in range(300)
    ]
    packet = build_context_packet(
        records,
        task={
            "id": "task",
            "description": "D" * 100_000,
            "acceptance": ["A" * 100_000],
        },
        scope="repo",
        query="needle",
    )
    serialized = json.dumps(packet, sort_keys=True, separators=(",", ":"))
    assert packet["input_truncated"] is True
    assert 0 < packet["omission_summary"]["emitted"] <= 32
    assert packet["omission_summary"]["suppressed"] > 0
    assert packet["task"]["field_truncation"]["description"]["truncated"] is True
    assert packet["acceptance_criteria"][0]["truncated"] is True
    assert "X" * 1_000 not in serialized
    assert len(serialized) < 100_000
    assert packet["response_token_estimate"] >= (len(serialized) + 3) // 4

    with pytest.raises(ValueError, match="query exceeds"):
        build_context_packet(
            [],
            scope="repo",
            query="Q" * 2_049,
        )


@pytest.mark.parametrize(
    "content",
    [
        {1: "integer", "1": "string"},
        {"nested": [{1: "integer", "1": "string"}]},
        dict(reversed([(1, "integer"), ("1", "string")])),
    ],
)
def test_graph_receipt_rejects_non_string_mapping_keys_without_collision(content):
    with pytest.raises(ValueError, match="keys must be strings"):
        make_graph_receipt(content, run_id="run")


def test_graph_receipt_rejects_forged_digest_and_non_json_set():
    with pytest.raises(ValueError, match="digest does not match"):
        GraphReceipt(
            run_id="run",
            status="complete",
            structured={"ok": True},
            digest="forged",
        )
    with pytest.raises(ValueError, match="JSON arrays"):
        make_graph_receipt({"values": {"a", "b"}}, run_id="run")


def test_context_scope_requires_exact_or_nested_path_boundary():
    records = [
        {
            "id": "exact",
            "scope": "project/foo",
            "status": "active",
            "trust": "ready",
            "text": "needle",
            "provenance": {"type": "source_file"},
        },
        {
            "id": "nested",
            "scope": "project/foo/child",
            "status": "active",
            "trust": "ready",
            "text": "needle",
            "provenance": {"type": "source_file"},
        },
        {
            "id": "prefix_collision",
            "scope": "unrelated-project/foo-evil",
            "status": "active",
            "trust": "ready",
            "text": "needle",
            "provenance": {"type": "source_file"},
        },
        {
            "id": "other_branch",
            "scope": "other/foo",
            "status": "active",
            "trust": "ready",
            "text": "needle",
            "provenance": {"type": "source_file"},
        },
    ]
    packet = build_context_packet(records, scope="project/foo", query="needle")
    assert packet["selected_ids"] == ["exact", "nested"]
    assert {item["id"] for item in packet["omitted"] if item["reason"] == "scope_mismatch"} == {
        "other_branch",
        "prefix_collision",
    }


def test_context_diversity_is_deterministic_and_prefers_new_facets():
    records = [
        {
            "id": "a",
            "scope": "repo",
            "status": "active",
            "trust": "ready",
            "text": "memory lesson",
            "tags": ["scheduler"],
            "provenance": {"type": "test"},
        },
        {
            "id": "b",
            "scope": "repo",
            "status": "active",
            "trust": "ready",
            "text": "memory lesson",
            "tags": ["scheduler"],
            "provenance": {"type": "test"},
        },
        {
            "id": "c",
            "scope": "repo",
            "status": "active",
            "trust": "ready",
            "text": "memory lesson",
            "tags": ["evidence"],
            "provenance": {"type": "receipt"},
        },
    ]
    expected = build_context_packet(
        records, scope="repo", query="memory", max_records=2
    )
    permuted = build_context_packet(
        reversed(records), scope="repo", query="memory", max_records=2
    )
    assert expected["selected_ids"] == ["a", "c"]
    assert permuted["selected_ids"] == expected["selected_ids"]
    assert expected["diversity"]["strategy"] == "greedy_new_facets_v1"
    assert any(item == {"id": "b", "reason": "record_cap", "provenance": {"type": "test"}} for item in expected["omitted"])


def test_slice_result_scope_and_fence_validation():
    assert validate_slice_result(_structured("t1"), allowed_paths=["src"]) ["ok"]
    escaped = _structured("t1")
    escaped["changed_paths"] = ["src/../outside.py"]
    assert validate_slice_result(escaped, allowed_paths=["src"])["ok"] is False
    missing_owner = _structured("t1")
    missing_owner.pop("owner")
    checked_owner = validate_slice_result(missing_owner, allowed_paths=["src"])
    assert checked_owner["ok"] is False
    assert "owner_required" in checked_owner["errors"]


def test_slice_result_payload_cannot_self_declare_legacy_or_coerce_fence_owner():
    forged_legacy = _structured("t1")
    forged_legacy.update(
        {"legacy": "false", "mode": "legacy", "changed_paths": ["../escape"]}
    )
    checked_legacy = validate_slice_result(forged_legacy, allowed_paths=["src"])
    assert checked_legacy["ok"] is False
    assert "changed_path_escape" in checked_legacy["errors"]

    string_fence = _structured("t1")
    string_fence["fence_token"] = "1"
    checked_fence = validate_slice_result(string_fence, allowed_paths=["src"])
    assert checked_fence["ok"] is False
    assert "fence_token_invalid" in checked_fence["errors"]

    whitespace_owner = _structured("t1")
    whitespace_owner["owner"] = "   "
    whitespace_owner["lease"]["owner"] = "   "
    checked_owner = validate_slice_result(whitespace_owner, allowed_paths=["src"])
    assert checked_owner["ok"] is False
    assert "owner_invalid" in checked_owner["errors"]
    assert "lease_owner_required" in checked_owner["errors"]

    with pytest.raises(TypeError, match="legacy must be a boolean"):
        validate_slice_result(_structured("t1"), allowed_paths=["src"], legacy=1)


def test_slice_result_rejects_unverifiable_monotonic_expiry_without_hook():
    result = _structured("t1")
    result["lease"] = {
        "active": True,
        "owner": "worker",
        "fencing_token": 1,
        "expires_at": 1.0,
    }
    checked = validate_slice_result(result, allowed_paths=["src"])
    assert checked["ok"] is False
    assert "lease_inactive" in checked["errors"]


def test_fan_in_is_sorted_deduped_and_preserves_blocked_missing():
    first = _structured("b", claims=[{"id": "claim", "text": "same"}])
    second = _structured("a", claims=[{"id": "claim", "text": "same"}])
    blocked = _structured("c", status="blocked")
    merged = fan_in([first, blocked, second], expected_task_ids=["a", "b", "c", "missing"], allowed_paths={"a": ["src"], "b": ["src"], "c": ["src"]})
    assert merged["ok"] is False
    assert merged["missing"] == ["missing"]
    assert merged["blocked"][0]["task_id"] == "c"
    assert [item["task_id"] for item in merged["results"]] == ["a", "b", "c"]
    assert len(merged["claims"]) == 1


def test_fan_in_uses_canonical_content_not_worker_supplied_digest_for_conflicts():
    left = _structured(
        "a", claims=[{"id": "claim", "text": "left", "digest": "forged"}]
    )
    right = _structured(
        "b", claims=[{"id": "claim", "text": "right", "digest": "forged"}]
    )
    merged = fan_in(
        [left, right],
        expected_task_ids=["a", "b"],
        allowed_paths={"a": ["src"], "b": ["src"]},
    )
    assert merged["ok"] is False
    assert merged["conflicts"][0]["kind"] == "claim"
    assert merged["conflicts"][0]["id"] == "claim"
    assert len(merged["conflicts"][0]["digests"]) == 2

    identical_left = _structured(
        "c", claims=[{"id": "same", "text": "same", "digest": "external"}]
    )
    identical_right = _structured(
        "d", claims=[{"id": "same", "text": "same", "digest": "external"}]
    )
    duplicate = fan_in(
        [identical_left, identical_right],
        expected_task_ids=["c", "d"],
        allowed_paths={"c": ["src"], "d": ["src"]},
    )
    assert duplicate["conflicts"] == []
    assert any(item["kind"] == "claim" for item in duplicate["duplicates"])


def test_fan_in_fails_closed_for_nonterminal_slice_results():
    running = fan_in(
        [{"task_id": "a", "status": "running"}],
        expected_task_ids=["a"],
        legacy=True,
        require_lease=False,
    )
    assert running["ok"] is False
    assert running["missing"] == []
    assert running["incomplete"] == [{"task_id": "a", "status": "running"}]


def test_quality_gates_are_lexicographic_and_evidence_bearing():
    all_gates = {
        name: {
            "ok": True,
            "evidence": [
                {
                    "status": "passed",
                    "count": 1,
                    "id": name,
                    "source_id": f"gate:{name}",
                }
            ],
        }
        for name in ("integrity", "correctness", "regression", "resource", "benefit")
    }
    result = evaluate_gates(all_gates, impact="high", reviewer_tags=["reviewer:alice"])
    assert result["ok"] is True
    assert result["gate_order"] == ["integrity", "correctness", "regression", "resource", "benefit"]
    assert evaluate_gates(all_gates, risk_tags=["external_write"])["ok"] is False
    empty = dict(all_gates)
    empty["correctness"] = {"ok": True, "evidence": [{}]}
    assert evaluate_gates(empty)["ok"] is False
    for invalid_evidence in (
        {"command": "pytest"},
        {"status": "passed", "scenario_count": 0, "command": "bench"},
        {"passed": 0, "total": 0, "command": "pytest"},
        {"ok": 0, "case_count": 1, "command": "pytest"},
    ):
        invalid = dict(all_gates)
        invalid["correctness"] = {"ok": True, "evidence": [invalid_evidence]}
        assert evaluate_gates(invalid)["ok"] is False


def test_evidence_requires_both_positive_outcome_and_positive_case_count() -> None:
    outcome_only = validate_evidence_items(
        [{"source_id": "test:outcome-only", "status": "passed"}]
    )
    count_only = validate_evidence_items(
        [{"source_id": "test:count-only", "count": 1}]
    )
    complete = validate_evidence_items(
        [{"source_id": "test:complete", "status": "passed", "count": 1}]
    )
    assert outcome_only == (False, ["evidence_missing_case_count"])
    assert count_only == (False, ["evidence_missing_positive_outcome"])
    assert complete == (True, [])


def test_receipt_is_bounded_and_structured_content_is_full():
    receipt = make_graph_receipt({"run_id": "run", "answer": "\n".join(f"line-{i}" for i in range(20)), "omissions": list(range(10))}, max_chars=200)
    assert len(receipt.markdown) <= 200
    assert receipt.structured["answer_unit_count"] == 20
    assert receipt.structured["omission_count"] == 10
    assert receipt.structured["omissions"] == tuple(range(10))
    with pytest.raises(ValueError, match="non-finite"):
        make_graph_receipt({"run_id": "run", "value": float("nan")})


def test_fanin_rejects_non_finite_result_content():
    result = _structured("finite-boundary")
    result["value"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        fan_in([result], allowed_paths=["src"])


def test_promotion_candidate_and_legacy_adapter_are_read_only(tmp_path):
    candidate = promote_lesson({"text": "symptom s fix f proof p"})
    assert candidate["status"] == "candidate"
    assert candidate["verify_before_use"] is True
    evidence = tmp_path / "receipt.json"
    evidence.write_text("{}")
    active = promote_lesson(
        {
            "text": "symptom s fix f proof p",
            "run_id": "run-1",
            "receipt_digest": "digest",
            "provenance_type": "source_backed_agent_run",
            "evidence_path": str(evidence),
            "conflict_audit": {
                "ok": True,
                "source": "graph_receipt",
                "receipt_digest": "digest",
                "conflicts": [],
            },
            "usage": {
                "source": "graph_receipt",
                "receipt_digest": "digest",
                "unknown_dimensions": [],
                "efficiency_claim_eligible": True,
            },
        },
        activate=True,
    )
    assert active["status"] == "active" and active["verify_before_use"] is False
    imported = import_legacy({"records": [{"id": "old"}]}, mode="shadow")
    assert imported["read_only"] is True and imported["write_performed"] is False
    assert imported["migration_id"].startswith("sips-migration-")


def test_promotion_helper_rejects_type_confused_or_embedded_activation() -> None:
    with pytest.raises(ValueError, match="activate must be a boolean"):
        promote_lesson(
            {"text": "must remain a candidate"},
            activate="false",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="lesson.activate is not allowed"):
        promote_lesson({"text": "must remain a candidate", "activate": "false"})


def test_api_read_write_dispatch_validation_and_idempotency():
    api = RuntimeAPI(controller=False)
    assert api.dispatch("write", {"op": "create"})["error"] == "idempotency_key_required"
    first = api.dispatch({"mode": "write", "op": "create", "idempotency_key": "k", "expected_revision": 0})
    assert first["ok"] is True
    assert api.dispatch("write", {"op": "create", "idempotency_key": "k", "expected_revision": 0}) == first
    assert api.dispatch("write", {"op": "create", "idempotency_key": "k", "expected_revision": 1})["error"] == "idempotency_conflict"
    assert api.dispatch("read", {"op": "status"})["ok"] is True


@pytest.mark.parametrize("expected_revision", [True, False, 1.0, "1", -1])
def test_api_rejects_non_exact_nonnegative_expected_revision(expected_revision):
    api = RuntimeAPI(controller=False)
    response = api.write(
        "create",
        {"idempotency_key": f"invalid-{expected_revision!r}", "expected_revision": expected_revision},
    )
    assert response == {
        "ok": False,
        "error": "expected_revision_invalid",
        "operation": "create",
    }
    assert api.read("status")["revision"] == 0


@pytest.mark.parametrize(
    "field,value",
    [("include_untrusted", "false"), ("token_budget", "bad")],
)
def test_api_frontier_surfaces_type_errors_instead_of_fallback_success(
    field, value
):
    response = RuntimeAPI(controller=False).read(
        "frontier",
        {"scope": "project/frontier", "query": "needle", field: value},
    )
    assert response["ok"] is False
    assert response["operation"] == "frontier"
    assert response["error_type"] == "TypeError"


def test_api_rejects_type_confused_promotion_activation() -> None:
    response = RuntimeAPI(controller=False).write(
        "promote",
        {
            "run_id": "run",
            "idempotency_key": "promote",
            "expected_revision": 0,
            "activate": "false",
            "lesson": {"text": "candidate only"},
        },
    )
    assert response == {
        "ok": False,
        "error": "activate_invalid",
        "operation": "promote",
    }


@pytest.mark.parametrize("idempotency_key", [5, True, " key ", ""])
def test_api_rejects_non_exact_idempotency_keys(idempotency_key) -> None:
    response = RuntimeAPI(controller=False).write(
        "create",
        {"idempotency_key": idempotency_key, "expected_revision": 0},
    )
    assert response["ok"] is False
    assert response["error"] == "idempotency_key_required"


@pytest.mark.parametrize("owner", [5, True, " worker ", ""])
def test_api_does_not_coerce_lease_owner_identity(owner) -> None:
    response = RuntimeAPI(controller=False).write(
        "lease",
        {
            "run_id": "run",
            "owner": owner,
            "idempotency_key": "lease",
            "expected_revision": 0,
        },
    )
    assert response == {
        "ok": False,
        "error": "owner_invalid",
        "operation": "lease",
    }


class _UnexpectedControllerCall:
    def __getattr__(self, name):
        raise AssertionError(f"controller discovery/call happened: {name}")


@pytest.mark.parametrize("run_id", [True, False, 5, "bad/id", " run ", "run id"])
@pytest.mark.parametrize(
    "controller", [False, _UnexpectedControllerCall()], ids=["fallback", "normal"]
)
def test_api_rejects_unsafe_create_run_ids_before_controller_or_fallback(
    run_id, controller
) -> None:
    api = RuntimeAPI(controller=controller)
    response = api.write(
        "create",
        {
            "run_id": run_id,
            "idempotency_key": f"create-{run_id!r}",
            "expected_revision": 0,
        },
    )
    assert response == {
        "ok": False,
        "error": "run_id_invalid",
        "operation": "create",
    }


@pytest.mark.parametrize("run_id", [True, False, 5, "bad/id", " run ", "run id"])
@pytest.mark.parametrize(
    "controller", [False, _UnexpectedControllerCall()], ids=["fallback", "normal"]
)
def test_api_rejects_unsafe_non_create_run_ids_before_controller_or_fallback(
    run_id, controller
) -> None:
    api = RuntimeAPI(controller=controller)
    response = api.write(
        "submit",
        {
            "run_id": run_id,
            "idempotency_key": f"submit-{run_id!r}",
            "expected_revision": 0,
        },
    )
    assert response == {
        "ok": False,
        "error": "run_id_invalid",
        "operation": "submit",
    }


@pytest.mark.parametrize("run_id_location", ["top-level", "nested"])
def test_api_rejects_unsafe_nested_create_run_id(run_id_location) -> None:
    request = {
        "idempotency_key": "nested-create",
        "expected_revision": 0,
    }
    if run_id_location == "top-level":
        request["run_id"] = "bad/id"
    else:
        request["request"] = {"run_id": "bad/id"}
    response = RuntimeAPI(controller=False).write("create", request)
    assert response == {
        "ok": False,
        "error": "run_id_invalid",
        "operation": "create",
    }


def test_api_idempotency_identity_distinguishes_nested_bool_and_int() -> None:
    api = RuntimeAPI(controller=False)
    first = api.write(
        "create",
        {
            "request": {"metadata": {"value": 1}},
            "idempotency_key": "nested-types",
            "expected_revision": 0,
        },
    )
    conflict = api.write(
        "create",
        {
            "request": {"metadata": {"value": True}},
            "idempotency_key": "nested-types",
            "expected_revision": 0,
        },
    )
    assert first["ok"] is True
    assert conflict == {
        "ok": False,
        "operation": "create",
        "error": "idempotency_conflict",
    }


def test_api_idempotency_identity_distinguishes_nested_int_and_float() -> None:
    api = RuntimeAPI(controller=False)
    first = api.write(
        "create",
        {
            "request": {"metadata": {"value": 1}},
            "idempotency_key": "nested-number-types",
            "expected_revision": 0,
        },
    )
    conflict = api.write(
        "create",
        {
            "request": {"metadata": {"value": 1.0}},
            "idempotency_key": "nested-number-types",
            "expected_revision": 0,
        },
    )
    assert first["ok"] is True
    assert conflict == {
        "ok": False,
        "operation": "create",
        "error": "idempotency_conflict",
    }
