from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from sips_runtime.campaign_fleet import CampaignExists, CampaignFleet
from sips_runtime.events import IdempotencyConflict, RevisionConflict


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sips_campaign_fleet.py"


def test_campaign_fleet_rebuilds_archiveable_child_projection(tmp_path):
    fleet = CampaignFleet(tmp_path)
    created = fleet.create(
        "Improve thread organization",
        campaign_id="campaign-test",
        contract={"success_criteria": ["archive children without losing receipts"]},
        parent_thread_id="parent-thread",
        tags=["sips", "clonk"],
        idempotency_key="create-campaign-test",
    )
    assert created["schema"] == "sips.runtime.campaign.v1"
    assert created["revision"] == 1

    attached = fleet.attach_child(
        "campaign-test",
        child_id="child-scout",
        title="Scout thread fleet behavior",
        role="Scout",
        thread_id="thread-scout",
        task_id="scout-1",
    )
    fleet.attach_child(
        "campaign-test",
        child_id="child-worker",
        title="Implement campaign spine",
        role="Worker",
        thread_id="thread-worker",
        task_id="worker-1",
    )
    assert attached["foreground_child_id"] == "child-scout"
    initial_scout = next(item for item in attached["children"] if item["id"] == "child-scout")
    fleet.set_child_status("campaign-test", "child-scout", "active")
    fleet.set_child_status(
        "campaign-test",
        "child-scout",
        "completed",
        receipt_id="receipt-scout",
    )
    archived = fleet.archive_child("campaign-test", "child-scout")

    assert archived["archived_child_count"] == 1
    assert archived["counts"] == {"archived": 1, "planned": 1}
    archived_child = next(item for item in archived["children"] if item["id"] == "child-scout")
    assert archived_child["status"] == "archived"
    assert archived_child["receipt_id"] == "receipt-scout"
    assert archived["activity"][-1]["event_type"] == "child.archived"
    assert archived["digest"]

    hidden = fleet.read("campaign-test", include_archived=False)
    assert [item["id"] for item in hidden["children"]] == ["child-worker"]
    assert hidden["archived_child_count"] == 1

    reopened = fleet.reopen_child("campaign-test", "child-scout", reason="inspect archived receipt")
    reopened_scout = next(item for item in reopened["children"] if item["id"] == "child-scout")
    assert reopened_scout["status"] == "active"
    assert reopened_scout["child_instance_id"] != initial_scout["child_instance_id"]
    assert reopened_scout["thread_id"] == ""
    assert reopened_scout["incarnation_count"] == 2
    assert any(item.get("thread_id") == "thread-scout" for item in reopened_scout["incarnations"])
    assert reopened["archived_child_count"] == 0
    assert fleet.search("thread-scout")[0]["campaign_id"] == "campaign-test"

    fleet._store("campaign-test", require_existing=True).verify()
    projection = json.loads((tmp_path / "runtime" / "v1" / "campaigns" / "campaign-test" / "projection.json").read_text())
    assert projection["digest"] == reopened["digest"]


def test_campaign_fleet_searches_archived_thread_metadata(tmp_path):
    fleet = CampaignFleet(tmp_path)
    fleet.create("Searchable campaign", campaign_id="campaign-search", idempotency_key="create-search")
    fleet.attach_child(
        "campaign-search",
        child_id="child-archived",
        title="Archive me",
        role="Judge",
        thread_id="thread-searchable",
    )
    fleet.set_child_status("campaign-search", "child-archived", "completed")
    fleet.archive_child("campaign-search", "child-archived")

    assert fleet.search("thread-searchable")[0]["campaign_id"] == "campaign-search"
    assert fleet.list(include_archived=False)[0]["campaign_id"] == "campaign-search"
    assert fleet.list(status="archived") == []


def test_campaign_fleet_rejects_stale_revision_and_duplicate_thread(tmp_path):
    fleet = CampaignFleet(tmp_path)
    fleet.create("Concurrency", campaign_id="campaign-concurrency", idempotency_key="create-concurrency")
    fleet.attach_child("campaign-concurrency", child_id="child-one", title="One", thread_id="thread-one")

    with pytest.raises(ValueError, match="cannot archive"):
        fleet.archive_child("campaign-concurrency", "child-one")

    with pytest.raises(RevisionConflict):
        fleet.attach_child(
            "campaign-concurrency",
            child_id="child-two",
            title="Two",
            thread_id="thread-two",
            expected_revision=1,
        )
    with pytest.raises(CampaignExists):
        fleet.attach_child(
            "campaign-concurrency",
            child_id="child-two",
            title="Two",
            thread_id="thread-one",
        )


def test_campaign_create_idempotency_rejects_changed_request(tmp_path):
    fleet = CampaignFleet(tmp_path)
    first = fleet.create(
        "Stable objective",
        campaign_id="campaign-idempotency",
        contract={"acceptance": ["same request replays"]},
        tags=["one"],
        idempotency_key="create-idempotency",
    )
    replay = fleet.create(
        "Stable objective",
        campaign_id="campaign-idempotency",
        contract={"acceptance": ["same request replays"]},
        tags=["one"],
        idempotency_key="create-idempotency",
    )
    assert replay["digest"] == first["digest"]

    with pytest.raises(IdempotencyConflict):
        fleet.create(
            "Changed objective",
            campaign_id="campaign-idempotency",
            contract={"acceptance": ["same request replays"]},
            tags=["one"],
            idempotency_key="create-idempotency",
        )
def test_campaign_fleet_cli_round_trip(tmp_path):
    env = dict(os.environ)
    env["SIPS_HOME"] = str(tmp_path)

    create = subprocess.run(
        ["python3", str(CLI), "create", "CLI campaign", "--campaign-id", "campaign-cli"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert create.returncode == 0, create.stderr
    fleet = json.loads(create.stdout)
    assert fleet["campaign_id"] == "campaign-cli"

    attach = subprocess.run(
        ["python3", str(CLI), "attach", "campaign-cli", "--child-id", "child-cli", "--title", "CLI worker", "--thread-id", "thread-cli"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert attach.returncode == 0, attach.stderr

    search = subprocess.run(
        ["python3", str(CLI), "search", "thread-cli"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert search.returncode == 0, search.stderr
    assert json.loads(search.stdout)["campaigns"][0]["campaign_id"] == "campaign-cli"
