"""Validation and deterministic fan-in of graph slice results."""
from __future__ import annotations

import posixpath
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

from .canonical import canonical_hash, canonical_json as strict_canonical_json


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    for method in ("to_dict", "model_dump"):
        if hasattr(value, method):
            result = getattr(value, method)()
            if isinstance(result, Mapping):
                return dict(result)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {"value": value}


def _get(value: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return default


def canonical_json(value: Any) -> str:
    return strict_canonical_json(value)


def digest(value: Any) -> str:
    """Stable SHA-256 digest for claims/artifacts used in dedupe and conflict detection."""
    return canonical_hash(value)


def _path_set(paths: Any) -> set[str]:
    if paths is None:
        return set()
    if isinstance(paths, str):
        return {paths}
    return {str(path) for path in paths}


def _path_within(path: str, roots: set[str]) -> bool:
    value = str(path).replace("\\", "/")
    normalized = posixpath.normpath(value)
    if normalized == ".." or normalized.startswith("../"):
        return False
    for root in roots:
        root_value = posixpath.normpath(str(root).replace("\\", "/")).rstrip("/")
        if root_value in {"", "."}:
            return True
        if normalized == root_value or normalized.startswith(root_value + "/"):
            return True
    return False


def _path_safe(path: str) -> bool:
    value = str(path).replace("\\", "/")
    normalized = posixpath.normpath(value)
    if normalized in {".."} or normalized.startswith("../"):
        return False
    return "/../" not in f"/{value.strip('/')}/" and not value.endswith("/..")


def _lease_active(result: Mapping[str, Any], active_lease: Any = None) -> bool:
    lease = _get(result, "lease", "active_lease", default=active_lease)
    if lease is None:
        # Results without lease metadata are accepted for legacy/read-only
        # ingestion; callers requiring fencing should provide a hook.
        return True
    data = _dict(lease)
    if not data:
        return False
    if data.get("active") is False or data.get("valid") is False or data.get("expired") is True:
        return False
    expires_at = data.get("expires_at", data.get("expiresAt"))
    if expires_at is not None:
        try:
            expiry = float(expires_at)
            # Epoch leases can be checked locally. Monotonic-shaped values
            # have no trustworthy clock origin in a detached result, so they
            # fail closed unless the caller omits expiry and supplies an
            # authoritative fence hook instead.
            if expiry <= 100_000_000 or time.time() >= expiry:
                return False
        except (TypeError, ValueError):
            return False
    status = str(data.get("status", "active")).lower()
    return status not in {"expired", "revoked", "released", "invalid", "stale"}


def validate_slice_result(
    result: Any,
    *,
    allowed_paths: Iterable[str] | None = None,
    active_lease: Any = None,
    lease_manager: Any = None,
    fence_hook: Callable[..., Any] | None = None,
    require_lease: bool = True,
    legacy: bool = False,
) -> dict[str, Any]:
    """Validate a result without mutating it.

    The fence hook is called with the normalized result and may return a bool,
    mapping with ``ok``, or raise.  A changed path must be inside the declared
    allowed set; this check is independent from any core controller policy.
    """
    if type(legacy) is not bool:
        raise TypeError("legacy must be a boolean")
    if type(require_lease) is not bool:
        raise TypeError("require_lease must be a boolean")
    value = _dict(result)
    errors: list[str] = []
    task_id = str(_get(value, "task_id", "taskId", "slice_id", "sliceId", "id", default=""))
    status = str(_get(value, "status", default="missing")).lower()
    if not task_id:
        errors.append("task_id_required")
    if status not in {"pending", "running", "done", "complete", "completed", "succeeded", "blocked", "failed", "missing", "cancelled", "canceled"}:
        errors.append("invalid_status")

    changed = _get(value, "changed_paths", "changedPaths", default=[])
    changed_paths = _path_set(changed)
    allowed = _path_set(allowed_paths if allowed_paths is not None else _get(value, "allowed_paths", "allowedPaths", "write_roots", "writeRoots", "write_set", "writeSet", default=[]))
    # Only the trusted adapter call site may opt into legacy parsing. Worker
    # payload fields can never disable runtime lease/path validation.
    explicit_legacy = legacy is True
    if not explicit_legacy:
        if changed_paths and not allowed:
            errors.append("changed_paths_scope_required")
        elif allowed and not all(_path_within(path, allowed) for path in changed_paths):
            errors.append("changed_paths_outside_scope")
        if any(not _path_safe(path) for path in changed_paths):
            errors.append("changed_path_escape")

    if not explicit_legacy:
        required_ids = {
            "run_id": ("run_id", "runId"),
            "attempt_id": ("attempt_id", "attemptId"),
            "lease_id": ("lease_id", "leaseId"),
            "owner": ("owner", "lease_owner"),
            "fence_token": ("fencing_token", "fence_token", "fenceToken", "fence"),
            "plan_id": ("plan_digest", "plan_id", "planId"),
            "context_id": ("context_digest", "context_id", "contextId"),
        }
        for label, keys in required_ids.items():
            if _get(value, *keys, default=None) in (None, ""):
                errors.append(f"{label}_required")

    lease_value = _get(value, "lease", "active_lease", default=active_lease)
    lease_present = lease_value is not None and bool(_dict(lease_value))
    if not explicit_legacy and require_lease and not lease_present:
        errors.append("active_lease_required")
    if not explicit_legacy and lease_present and not _lease_active(value, active_lease):
        errors.append("lease_inactive")
    if not explicit_legacy and lease_present:
        lease_data = _dict(lease_value)
        for flag in ("active", "valid", "expired"):
            if flag in lease_data and type(lease_data[flag]) is not bool:
                errors.append(f"lease_{flag}_invalid")
        result_token = _get(value, "fencing_token", "fence_token", "token", default=None)
        lease_token = _get(lease_data, "fencing_token", "fence_token", "token", default=None)
        result_token_valid = (
            isinstance(result_token, int)
            and not isinstance(result_token, bool)
            and result_token > 0
        )
        lease_token_valid = (
            isinstance(lease_token, int)
            and not isinstance(lease_token, bool)
            and lease_token > 0
        )
        if not result_token_valid:
            errors.append("fence_token_invalid")
        if not lease_token_valid:
            errors.append("lease_fence_token_invalid")
        if not result_token_valid or not lease_token_valid or result_token != lease_token:
            errors.append("fence_mismatch")
        result_owner = _get(value, "owner", "lease_owner", default="")
        lease_owner = _get(lease_data, "owner", default="")
        result_owner_valid = (
            isinstance(result_owner, str)
            and bool(result_owner.strip())
            and result_owner == result_owner.strip()
        )
        lease_owner_valid = (
            isinstance(lease_owner, str)
            and bool(lease_owner.strip())
            and lease_owner == lease_owner.strip()
        )
        if not result_owner_valid:
            errors.append("owner_invalid")
        if not lease_owner_valid:
            errors.append("lease_owner_required")
        elif not result_owner_valid or result_owner != lease_owner:
            errors.append("lease_owner_mismatch")

    if lease_manager is not None and fence_hook is None:
        for method in ("validate_fence", "check_fence", "is_active", "valid"):
            candidate = getattr(lease_manager, method, None)
            if callable(candidate):
                fence_hook = candidate
                break
    if fence_hook is not None and not explicit_legacy:
        try:
            try:
                fence = fence_hook(value)
            except TypeError:
                try:
                    fence = fence_hook(task_id, value)
                except TypeError:
                    lease_data = _dict(_get(value, "lease", "active_lease", default={}))
                    owner = str(_get(value, "owner", "lease_owner", default=_get(lease_data, "owner", default="")))
                    token = _get(value, "fencing_token", "fence_token", "token", default=None)
                    fence = fence_hook(task_id, owner, token)
            if isinstance(fence, Mapping):
                fence_ok = fence.get("ok", fence.get("active", False)) is True
            else:
                fence_ok = fence is True
            if not fence_ok:
                errors.append("fence_rejected")
        except Exception as exc:  # hooks must not make validation crash
            errors.append(f"fence_error:{type(exc).__name__}")

    normalized = dict(value)
    normalized["task_id"] = task_id
    normalized["status"] = status
    normalized["changed_paths"] = sorted(changed_paths)
    normalized["validation_errors"] = errors
    return {"ok": not errors, "result": normalized, "errors": errors}


def _items(result: Mapping[str, Any], *names: str) -> list[dict[str, Any]]:
    for name in names:
        value = result.get(name)
        if value is not None:
            if isinstance(value, Mapping):
                return [dict(value)]
            return [_dict(item) for item in value]
    return []


def _item_id(item: Mapping[str, Any], fallback: str, index: int) -> str:
    value = _get(item, "id", "claim_id", "claimId", "artifact_id", "artifactId", default="")
    return str(value) if value not in (None, "") else f"{fallback}-{digest(item)[:16]}"


def _with_digest(item: Mapping[str, Any], fallback: str, index: int) -> dict[str, Any]:
    value = dict(item)
    value["id"] = _item_id(value, fallback, index)
    content = {
        key: val
        for key, val in value.items()
        if key not in {"content_digest", "merge_digest"}
    }
    value["content_digest"] = digest(content)
    # Preserve an externally meaningful artifact digest, but never trust it
    # for merge identity or contradiction detection.
    value.setdefault("digest", value["content_digest"])
    return value


def _merge_items(items: Sequence[dict[str, Any]], kind: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_digest: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for item in items:
        iid = str(item["id"])
        idigest = str(item["content_digest"])
        prior = by_id.get(iid)
        if prior is not None and prior.get("content_digest") != idigest:
            conflict_items = sorted(
                [prior, item],
                key=lambda value: (
                    str(value.get("content_digest", "")),
                    canonical_json(value),
                ),
            )
            conflicts.append(
                {
                    "kind": kind,
                    "id": iid,
                    "digests": sorted(
                        {str(prior["content_digest"]), idigest}
                    ),
                    "items": conflict_items,
                }
            )
            continue
        if idigest in by_digest:
            duplicates.append({"kind": kind, "id": iid, "digest": idigest})
            continue
        by_id[iid] = item
        by_digest[idigest] = item
    merged = sorted(
        by_digest.values(),
        key=lambda value: (
            str(value.get("id", "")),
            str(value.get("content_digest", "")),
        ),
    )
    conflicts.sort(key=lambda value: (value["kind"], value["id"]))
    duplicates.sort(key=lambda value: (value["kind"], value["id"], value["digest"]))
    return merged, conflicts, duplicates


def fan_in(
    results: Iterable[Any],
    *,
    expected_task_ids: Iterable[str] | None = None,
    allowed_paths: Mapping[str, Iterable[str]] | Iterable[str] | None = None,
    active_lease: Any = None,
    lease_manager: Any = None,
    fence_hook: Callable[..., Any] | None = None,
    require_lease: bool = True,
    legacy: bool = False,
) -> dict[str, Any]:
    """Merge slice results deterministically while preserving incompleteness."""
    normalized_inputs = [_dict(value) for value in results]
    validations: list[dict[str, Any]] = []
    valid_results: list[dict[str, Any]] = []
    for value in normalized_inputs:
        task_id = str(_get(value, "task_id", "taskId", "slice_id", "sliceId", "id", default=""))
        task_allowed = allowed_paths.get(task_id, ()) if isinstance(allowed_paths, Mapping) else allowed_paths
        checked = validate_slice_result(value, allowed_paths=task_allowed, active_lease=active_lease, lease_manager=lease_manager, fence_hook=fence_hook, require_lease=require_lease, legacy=legacy)
        validations.append(checked)
        if checked["ok"]:
            valid_results.append(checked["result"])

    expected = {str(item) for item in (expected_task_ids or ())}
    seen = {str(_get(value, "task_id", "taskId", "slice_id", "sliceId", "id", default="")) for value in normalized_inputs}
    missing = sorted(expected - seen)
    blocked = sorted(
        [
            {"task_id": str(_get(value, "task_id", "taskId", "slice_id", "sliceId", "id", default="")), "status": str(value.get("status", "blocked")), "reason": value.get("blocked_reason", value.get("reason", ""))}
            for value in normalized_inputs
            if str(value.get("status", "")).lower() in {"blocked", "failed", "cancelled", "canceled"}
        ],
        key=lambda value: value["task_id"],
    )
    incomplete = sorted(
        [
            {
                "task_id": str(
                    _get(
                        value,
                        "task_id",
                        "taskId",
                        "slice_id",
                        "sliceId",
                        "id",
                        default="",
                    )
                ),
                "status": str(value.get("status", "missing")).lower(),
            }
            for value in normalized_inputs
            if str(value.get("status", "missing")).lower()
            in {"pending", "running", "missing"}
        ],
        key=lambda value: (value["task_id"], value["status"]),
    )
    validations.sort(
        key=lambda item: (
            str(item.get("result", {}).get("task_id", "")),
            digest(item.get("result", {})),
        )
    )
    result_groups: dict[str, dict[str, dict[str, Any]]] = {}
    duplicate_results: list[dict[str, Any]] = []
    for value in valid_results:
        task_id = str(value.get("task_id", ""))
        result_digest = digest(value)
        group = result_groups.setdefault(task_id, {})
        if result_digest in group:
            duplicate_results.append({"kind": "result", "task_id": task_id, "digest": result_digest})
        else:
            group[result_digest] = value
    result_conflicts = [
        {
            "kind": "result",
            "task_id": task_id,
            "digests": sorted(group),
            "items": [group[item_digest] for item_digest in sorted(group)],
        }
        for task_id, group in sorted(result_groups.items())
        if len(group) > 1
    ]
    valid_results = [
        group[item_digest]
        for task_id, group in sorted(result_groups.items())
        for item_digest in sorted(group)
    ]

    claim_items: list[dict[str, Any]] = []
    artifact_items: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    for result in valid_results:
        tid = str(result.get("task_id", "task"))
        for index, claim in enumerate(_items(result, "claims", "claim_results")):
            claim_items.append(_with_digest(claim, f"{tid}-claim", index))
        for index, artifact in enumerate(_items(result, "artifacts", "outputs")):
            artifact_items.append(_with_digest(artifact, f"{tid}-artifact", index))
        for index, evidence in enumerate(_items(result, "evidence", "proof")):
            evidence_items.append(_with_digest(evidence, f"{tid}-evidence", index))
    claims, claim_conflicts, claim_duplicates = _merge_items(claim_items, "claim")
    artifacts, artifact_conflicts, artifact_duplicates = _merge_items(artifact_items, "artifact")
    evidence, evidence_conflicts, evidence_duplicates = _merge_items(evidence_items, "evidence")
    conflicts = sorted(
        claim_conflicts + artifact_conflicts + evidence_conflicts,
        key=lambda value: (value["kind"], value["id"]),
    )
    duplicates = sorted(
        claim_duplicates + artifact_duplicates + evidence_duplicates + duplicate_results,
        key=lambda value: (value["kind"], str(value.get("id", value.get("task_id", ""))), value["digest"]),
    )
    return {
        "ok": not missing
        and not blocked
        and not incomplete
        and not conflicts
        and not result_conflicts
        and all(item["ok"] for item in validations),
        "results": valid_results,
        "validations": validations,
        "claims": claims,
        "artifacts": artifacts,
        "evidence": evidence,
        "missing": missing,
        "blocked": blocked,
        "incomplete": incomplete,
        "conflicts": conflicts,
        "result_conflicts": result_conflicts,
        "duplicates": duplicates,
        "task_ids": sorted(seen),
        "expected_task_ids": sorted(expected),
    }


merge_results = fan_in
deterministic_fan_in = fan_in
validate_result = validate_slice_result

__all__ = ["canonical_json", "digest", "validate_slice_result", "validate_result", "fan_in", "merge_results", "deterministic_fan_in"]
