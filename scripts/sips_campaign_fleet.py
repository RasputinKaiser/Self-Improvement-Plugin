#!/usr/bin/env python3
"""CLI for the SIPS campaign/thread fleet.

The fleet records campaign and external child-thread metadata.  It does not
create, archive, or mutate host conversations; callers attach the host's
thread handle and use the lifecycle commands to keep campaign evidence tidy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sips_runtime.campaign_fleet import CampaignFleet, campaign_markdown


def _tags(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _contract(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("--contract-json must be an object")
    return value


def _print(value: Any, *, markdown: bool = False) -> None:
    if markdown and isinstance(value, dict):
        print(campaign_markdown(value))
    else:
        print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sips_campaign_fleet.py", description="Campaign spine and child-thread fleet registry")
    parser.add_argument("--home", default=None, help="SIPS home override; defaults to SIPS_HOME or ~/.codex/sips")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a campaign spine")
    create.add_argument("objective")
    create.add_argument("--campaign-id")
    create.add_argument("--contract-json", default="")
    create.add_argument("--parent-thread-id", default="")
    create.add_argument("--runtime-run-id", default="")
    create.add_argument("--workspace-root", default="")
    create.add_argument("--tags", default="")
    create.add_argument("--idempotency-key")

    attach = sub.add_parser("attach", help="attach one external child thread")
    attach.add_argument("campaign_id")
    attach.add_argument("--title", required=True)
    attach.add_argument("--role", default="Worker")
    attach.add_argument("--child-id")
    attach.add_argument("--thread-id", default="")
    attach.add_argument("--task-id", default="")
    attach.add_argument("--objective", default="")
    attach.add_argument("--summary", default="")
    attach.add_argument("--tags", default="")
    attach.add_argument("--expected-revision", type=int)
    attach.add_argument("--idempotency-key")

    status = sub.add_parser("status", help="read one campaign")
    status.add_argument("campaign_id")
    status.add_argument("--hide-archived", action="store_true")
    status.add_argument("--markdown", action="store_true")

    listing = sub.add_parser("list", help="list campaign spines")
    listing.add_argument("--query", default="")
    listing.add_argument("--status", default="")
    listing.add_argument("--include-archived", action="store_true")
    listing.add_argument("--limit", type=int, default=50)

    search = sub.add_parser("search", help="search campaigns and child thread metadata")
    search.add_argument("query")
    search.add_argument("--include-archived", action="store_true")
    search.add_argument("--limit", type=int, default=50)

    child_status = sub.add_parser("set-child-status", help="advance one child lifecycle state")
    child_status.add_argument("campaign_id")
    child_status.add_argument("child_id")
    child_status.add_argument("status", choices=("planned", "active", "waiting", "blocked", "completed", "failed", "canceled", "abandoned"))
    child_status.add_argument("--reason", default="")
    child_status.add_argument("--summary", default="")
    child_status.add_argument("--receipt-id", default="")
    child_status.add_argument("--expected-revision", type=int)
    child_status.add_argument("--idempotency-key")

    archive = sub.add_parser("archive", help="archive a child in the campaign projection")
    archive.add_argument("campaign_id")
    archive.add_argument("child_id")
    archive.add_argument("--reason", default="completed child archived")
    archive.add_argument("--expected-revision", type=int)
    archive.add_argument("--idempotency-key")

    reopen = sub.add_parser("reopen", help="reopen an archived/completed child")
    reopen.add_argument("campaign_id")
    reopen.add_argument("child_id")
    reopen.add_argument("--reason", default="reopened from campaign fleet")
    reopen.add_argument("--thread-id", default="", help="new host thread handle; blank means a new binding is still pending")
    reopen.add_argument("--task-id", default="", help="new runtime task handle")
    reopen.add_argument("--expected-revision", type=int)
    reopen.add_argument("--idempotency-key")

    campaign_status = sub.add_parser("set-status", help="advance campaign lifecycle state")
    campaign_status.add_argument("campaign_id")
    campaign_status.add_argument("status", choices=("active", "completed", "archived", "abandoned"))
    campaign_status.add_argument("--reason", default="")
    campaign_status.add_argument("--expected-revision", type=int)
    campaign_status.add_argument("--idempotency-key")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fleet = CampaignFleet(args.home)
    try:
        if args.command == "create":
            _print(fleet.create(
                args.objective,
                campaign_id=args.campaign_id,
                contract=_contract(args.contract_json),
                parent_thread_id=args.parent_thread_id,
                runtime_run_id=args.runtime_run_id,
                workspace_root=args.workspace_root,
                tags=_tags(args.tags),
                idempotency_key=args.idempotency_key,
            ))
        elif args.command == "attach":
            _print(fleet.attach_child(
                args.campaign_id,
                title=args.title,
                role=args.role,
                child_id=args.child_id,
                thread_id=args.thread_id,
                task_id=args.task_id,
                objective=args.objective,
                summary=args.summary,
                tags=_tags(args.tags),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
            ))
        elif args.command == "status":
            _print(fleet.read(args.campaign_id, include_archived=not args.hide_archived), markdown=args.markdown)
        elif args.command == "list":
            _print({"ok": True, "campaigns": fleet.list(query=args.query, status=args.status, include_archived=args.include_archived, limit=args.limit)})
        elif args.command == "search":
            _print({"ok": True, "query": args.query, "campaigns": fleet.search(args.query, include_archived=args.include_archived, limit=args.limit)})
        elif args.command == "set-child-status":
            _print(fleet.set_child_status(args.campaign_id, args.child_id, args.status, reason=args.reason, summary=args.summary, receipt_id=args.receipt_id, expected_revision=args.expected_revision, idempotency_key=args.idempotency_key))
        elif args.command == "archive":
            _print(fleet.archive_child(args.campaign_id, args.child_id, reason=args.reason, expected_revision=args.expected_revision, idempotency_key=args.idempotency_key))
        elif args.command == "reopen":
            _print(fleet.reopen_child(args.campaign_id, args.child_id, reason=args.reason, thread_id=args.thread_id, task_id=args.task_id, expected_revision=args.expected_revision, idempotency_key=args.idempotency_key))
        elif args.command == "set-status":
            _print(fleet.set_campaign_status(args.campaign_id, args.status, reason=args.reason, expected_revision=args.expected_revision, idempotency_key=args.idempotency_key))
        return 0
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
