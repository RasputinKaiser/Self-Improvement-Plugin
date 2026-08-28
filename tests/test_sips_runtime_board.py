from __future__ import annotations

import json

import goal_state
from sips_runtime.api import RuntimeAPI
from sips_runtime.board import build_board
from sips_runtime.campaign_fleet import CampaignFleet
from sips_runtime.controller import RuntimeController
from brainstorm import make_idea_cards


def _controller(tmp_path):
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "board-test",
            "objective": "Improve the harness",
            "workspace_root": str(tmp_path),
            "tasks": [
                {"id": "scout", "objective": "Scout evidence", "metadata": {"role": "Scout"}},
                {
                    "id": "worker",
                    "objective": "Implement one change",
                    "depends_on": ["scout"],
                    "metadata": {"role": "Worker"},
                },
            ],
        },
        idempotency_key="board-create",
        expected_revision=0,
    )
    return controller


def test_board_is_read_only_and_selects_one_foreground_task(tmp_path):
    controller = _controller(tmp_path)
    result = RuntimeAPI(controller=controller).read("board", {"run_id": "board-test"})

    assert result["ok"] is True
    board = result["data"]
    assert board["schema"] == "sips.runtime.campaign-board.v1"
    assert board["authority"] == "runtime-events"
    assert board["read_only"] is True
    assert board["foreground_task_id"] == "scout"
    assert board["tasks"][0]["role"] == "Scout"
    assert board["counts"] == {"queued": 1, "waiting_for_child": 1}
    assert board["digest"]
    assert controller.read_status("board-test")["revision"] == 1
    assert board["recommendation"]["phase"] == "observe"
    assert "dependencies" in board["recommendation"]["why"]
    assert board["plan"]["next_phase"] == "observe"
    phases = {item["id"]: item for item in board["plan"]["phases"]}
    assert phases["observe"]["status"] == "next"
    assert phases["execute"]["status"] == "waiting"


def test_board_surfaces_idea_cards_and_plan_proof():
    board = build_board(
        {
            "run_id": "ideas",
            "objective": "Improve SIPS",
            "revision": 0,
            "tasks": {},
            "metadata": {
                "idea_cards": [{
                    "id": "idea-001",
                    "title": "Live progress",
                    "recommended_next": "scout_then_plan",
                }],
            },
        },
        run_id="ideas",
    )

    assert board["recommendation"]["kind"] == "idea_review"
    assert board["recommendation"]["idea_id"] == "idea-001"
    assert board["idea_cards"][0]["recommended_next"] == "scout_then_plan"
    assert board["plan"]["proof_boundary"].startswith("Plan phases")


def test_legacy_goal_board_exposes_actionable_titles_and_provenance(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(goal_state, "STATE_PATH", tmp_path / "goal_state.json")
    goal_state.cmd_set("Improve SIPS")
    goal_state.cmd_add_subtask("Inspect the board after restart")

    capsys.readouterr()
    goal_state.cmd_board()
    board = json.loads(capsys.readouterr().out)

    assert board["tasks"][0]["title"] == "Inspect the board after restart"
    assert board["provenance"]["source"] == "sips_goal_state"
    assert board["provenance"]["restart_safe"] is True
    assert board["provenance"]["task_exposure"] == "separate_host_proof"

    goal_state.cmd_complete_subtask("st-1")
    capsys.readouterr()
    goal_state.cmd_board()
    board = json.loads(capsys.readouterr().out)
    assert "st-1" not in board["ready_task_ids"]
    assert board["foreground_task_id"] is None


def test_runtime_board_joins_campaign_spine_from_run_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("SIPS_HOME", str(tmp_path))
    CampaignFleet(tmp_path).create(
        "Keep child threads organized",
        campaign_id="campaign-board-runtime",
        idempotency_key="create-board-runtime",
    )
    controller = RuntimeController(tmp_path)
    controller.create(
        {
            "run_id": "board-campaign-runtime",
            "objective": "Keep child threads organized",
            "workspace_root": str(tmp_path),
            "metadata": {"campaign_id": "campaign-board-runtime"},
            "tasks": [{"id": "scout", "objective": "Inspect the fleet", "metadata": {"role": "Scout"}}],
        },
        idempotency_key="create-board-campaign-runtime",
        expected_revision=0,
    )

    board = RuntimeAPI(controller=controller).read("board", {"run_id": "board-campaign-runtime"})["data"]

    assert board["campaign_id"] == "campaign-board-runtime"
    assert board["campaign"]["campaign_id"] == "campaign-board-runtime"
    assert board["campaign"]["claim_boundary"].startswith("Campaign metadata is event-backed")


def test_board_returns_bounded_revision_deltas(tmp_path):
    controller = _controller(tmp_path)
    controller.submit("board-test", idempotency_key="board-submit", expected_revision=1)
    result = RuntimeAPI(controller=controller).read(
        "board", {"run_id": "board-test", "since_revision": 1, "max_changes": 1}
    )

    board = result["data"]
    assert board["revision"] == 2
    assert len(board["changes"]) == 1
    assert board["changes"][0]["revision"] == 2
    assert board["changes"][0]["event_type"] == "run.submitted"


def test_board_rejects_unbounded_poll_arguments():
    api = RuntimeAPI(controller=False)
    assert api.read("board", {"since_revision": -1})["error"] == "since_revision_invalid"
    assert api.read("board", {"max_changes": 101})["error"] == "max_changes_invalid"


def test_brainstorm_idea_cards_are_suggestions_with_plan_proof():
    cards = make_idea_cards([{
        "name": "Live progress",
        "tier": "Tier 3",
        "area": "Observation",
        "leverage": 8,
        "effort": "medium",
    }])
    assert cards[0]["id"] == "idea-001"
    assert cards[0]["status"] == "suggested"
    assert cards[0]["recommended_next"] == "scout_then_plan"
    assert cards[0]["plan"]["steps"][-1].startswith("Worker implements")
    assert cards[0]["plan"]["proof"]
