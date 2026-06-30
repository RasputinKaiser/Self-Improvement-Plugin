from __future__ import annotations
from pathlib import Path
from typing import Any


CLAIM_BOUNDARY = (
    "Cache sync writes a versioned local cache copy. "
    "It does not prove current-thread live MCP exposure."
)


def sync_preflight(
    source: dict[str, Any],
    marketplace: dict[str, Any],
    target: Path,
    version: str,
) -> dict[str, Any]:
    reasons = sync_blockers(source, marketplace, target, version)
    return {
        "can_sync": not reasons,
        "reasons": reasons,
        "target_exists": target.exists(),
        "source_version": version,
    }


def sync_blockers(
    source: dict[str, Any],
    marketplace: dict[str, Any],
    target: Path,
    version: str,
) -> list[str]:
    checks = [
        (not source.get("ok"), "source_invalid"),
        (not marketplace.get("ok"), "marketplace_not_pointing_to_source"),
        (not version, "missing_source_version"),
        (target.exists(), "target_already_exists"),
    ]
    return [reason for blocked, reason in checks if blocked]


def sync_result(
    executed: bool,
    source_root: Path,
    target: Path,
    source: dict[str, Any],
    marketplace: dict[str, Any],
    preflight: dict[str, Any],
    copied: dict[str, Any] | None = None,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": sync_ok(executed, preflight, cache),
        "status": sync_status(executed, preflight),
        "executed": executed,
        "source_root": str(source_root),
        "target": str(target),
        "source": source,
        "marketplace": marketplace,
        "preflight": preflight,
        "copied": copied or {},
        "cache": cache or {},
        "claim_boundary": CLAIM_BOUNDARY,
    }


def sync_ok(executed: bool, preflight: dict[str, Any], cache: dict[str, Any] | None) -> bool:
    return bool((executed or preflight.get("idempotent")) and cache and cache.get("ok"))


def sync_status(executed: bool, preflight: dict[str, Any]) -> str:
    if preflight.get("idempotent"):
        return "already_synced"
    if preflight["reasons"]:
        return "blocked"
    return "synced" if executed else "dry_run"
