#!/usr/bin/env python3
"""CLI for the graph-runtime API.

Examples:
  python scripts/sips_runtime.py read --op status
  python scripts/sips_runtime.py write --op create --json '{"idempotency_key":"x","expected_revision":0}'
  printf '%s' '{"idempotency_key":"x","expected_revision":0}' | python scripts/sips_runtime.py write --op create --stdin
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from sips_runtime.api import RuntimeAPI
except ModuleNotFoundError:
    # ``scripts/sips_runtime.py`` shares its basename with the package.  Add
    # the package directory for direct script execution before importing API.
    sys.path.insert(0, str(Path(__file__).with_name("sips_runtime")))
    from api import RuntimeAPI  # type: ignore


def _payload(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.json
    if args.stdin:
        raw = sys.stdin.read()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError("JSON payload must be an object")
    return dict(value)


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    compact = {key: result[key] for key in ("ok", "operation", "error", "revision") if key in result}
    data = result.get("data")
    if isinstance(data, Mapping):
        for key in ("status", "task_id", "run_id", "accepted", "count", "revision"):
            if key in data:
                compact[key] = data[key]
        if "tasks" in data and isinstance(data["tasks"], list):
            compact["task_count"] = len(data["tasks"])
        if "events" in data and isinstance(data["events"], list):
            compact["event_count"] = len(data["events"])
    elif data is not None:
        compact["data"] = data
    return compact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sips_runtime.py", description="Graph runtime API dispatcher")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("read", "write"):
        sub = subparsers.add_parser(mode)
        sub.add_argument("--op", required=True, help="operation name")
        sub.add_argument("--json", default="", help="JSON object payload")
        sub.add_argument("--stdin", action="store_true", help="read JSON object payload from stdin")
        sub.add_argument("--detail", choices=("compact", "full"), default="compact")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _payload(args)
        result = RuntimeAPI().dispatch(args.op, payload)
    except ValueError as exc:
        result = {"ok": False, "error": str(exc)}
    output = result if args.detail == "full" else _compact(result)
    sys.stdout.write(json.dumps(output, sort_keys=True, ensure_ascii=False) + "\n")
    return 0 if result.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
