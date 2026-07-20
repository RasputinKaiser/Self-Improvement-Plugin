"""Compact JSON API dispatcher for graph-runtime reads and writes."""
from __future__ import annotations

import importlib
import threading
from typing import Any, Mapping

try:  # package import (normal tests)
    from .canonical import canonical_hash
    from .contracts import validate_safe_identifier
    from .projection import GraphReceipt, project_receipt
    from .promotion import promote_lesson
except ImportError:  # direct sibling import when the CLI shadows the package name
    from canonical import canonical_hash  # type: ignore
    from contracts import validate_safe_identifier  # type: ignore
    from projection import GraphReceipt, project_receipt  # type: ignore
    from promotion import promote_lesson  # type: ignore


READ_OPS = {"status", "plan", "events", "receipt", "frontier"}
WRITE_OPS = {"create", "submit", "lease", "advance", "cancel", "promote"}
_IDENTIFIER_FIELDS = {
    "task_id": "task_id",
    "taskId": "task_id",
    "slice_id": "slice_id",
    "sliceId": "slice_id",
}


def _validate_task_identifiers(value: Any, operation: str) -> dict[str, Any] | None:
    """Reject task/slice identity fields before controller coercion or fallback."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            label = _IDENTIFIER_FIELDS.get(key)
            if label is not None:
                try:
                    validate_safe_identifier(item, label=label)
                except ValueError:
                    return {"ok": False, "error": f"{label}_invalid", "operation": operation}
            invalid = _validate_task_identifiers(item, operation)
            if invalid is not None:
                return invalid
    elif isinstance(value, (list, tuple)):
        for item in value:
            invalid = _validate_task_identifiers(item, operation)
            if invalid is not None:
                return invalid
    return None


def _dump(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    if hasattr(value, "to_dict"):
        return _dump(value.to_dict())
    if hasattr(value, "model_dump"):
        return _dump(value.model_dump())
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _dump(vars(value))
    return value


def _controller_default() -> Any:
    for module_name in ("sips_runtime.controller", "scripts.sips_runtime.controller", "scripts.sips_runtime.core", "sips_runtime.core", "scripts.sips_runtime"):
        try:
            module = importlib.import_module(module_name)
            for name in ("controller", "get_controller", "RuntimeController", "RunController"):
                value = getattr(module, name, None)
                if value is None:
                    continue
                if callable(value) and name in {"get_controller", "RuntimeController", "RunController"}:
                    try:
                        return value()
                    except TypeError:
                        continue
                return value
        except Exception:
            continue
    return None


class RuntimeAPI:
    """Controller adapter with a deterministic in-memory fallback.

    The fallback is intentionally process-local: callers can inject the core
    controller when durable state is required.  This keeps API validation and
    idempotency testable without creating files or stores as a side effect.
    """

    def __init__(self, controller: Any = None) -> None:
        self.controller = controller if controller is not None else _controller_default()
        self._lock = threading.RLock()
        self._revision = 0
        self._state: dict[str, Any] = {"status": "idle", "tasks": [], "events": [], "leases": {}, "receipt": None}
        self._idempotency: dict[str, dict[str, Any]] = {}
        self._idempotency_inputs: dict[str, str] = {}

    def _controller_call(self, operation: str, payload: Mapping[str, Any]) -> Any:
        if operation == "frontier":
            allowed = {
                "scope",
                "query",
                "store",
                "include_untrusted",
                "seed_limit",
                "fanout",
                "max_depth",
                "max_nodes",
                "max_edges",
                "max_paths",
                "token_budget",
            }
            frontier_payload = {key: value for key, value in payload.items() if key in allowed}
            for module_name in ("sips_runtime.memory_frontier", "scripts.sips_runtime.memory_frontier", "memory_frontier"):
                try:
                    module = importlib.import_module(module_name)
                    function = getattr(module, "query_frontier", None)
                    if callable(function):
                        return function(**frontier_payload)
                except ImportError:
                    continue
        if self.controller is None:
            return None
        if operation in {"status", "plan", "events", "receipt"} and not payload.get("run_id"):
            return None
        candidates = {
            "create": ("create", "create_run", "create_graph"),
            "submit": ("submit", "submit_result", "record_result"),
            "lease": ("lease", "acquire_lease"),
            "advance": ("advance", "advance_run", "tick"),
            "cancel": ("cancel", "cancel_run"),
            "status": ("status", "get_status", "read_status"),
            "plan": ("plan", "get_plan", "read_plan"),
            "events": ("events", "get_events", "read_events"),
            "frontier": ("frontier", "get_frontier"),
            "receipt": ("receipt", "get_receipt", "read_receipt"),
        }.get(operation, (operation,))
        for name in candidates:
            method = getattr(self.controller, name, None)
            if callable(method):
                if operation == "create":
                    request = payload.get("request", payload)
                    if not isinstance(request, Mapping):
                        request = {"tasks": request}
                    request = {key: value for key, value in dict(request).items() if key not in {"idempotency_key", "expected_revision", "request"}}
                    return method(
                        request,
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                    )
                if operation in {"status", "plan", "events", "receipt"}:
                    return method(str(payload["run_id"]))
                if operation == "submit":
                    body = payload.get("payload", payload.get("submission", {}))
                    if not isinstance(body, Mapping):
                        body = {"value": body}
                    return method(
                        str(payload.get("run_id", "")),
                        dict(body),
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                    )
                if operation == "lease":
                    return method(
                        str(payload.get("run_id", "")),
                        payload.get("owner", payload.get("worker_id", "")),
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                        task_id=payload.get("task_id"),
                    )
                if operation == "advance":
                    body = payload.get("payload")
                    if body is None:
                        body = {
                            key: value
                            for key, value in payload.items()
                            if key
                            not in {
                                "run_id",
                                "idempotency_key",
                                "expected_revision",
                                "workspace_root",
                            }
                        }
                    if not isinstance(body, Mapping):
                        body = {"result": body}
                    body = {
                        key: value
                        for key, value in dict(body).items()
                        if key not in {"idempotency_key", "expected_revision", "workspace_root"}
                    }
                    return method(
                        str(payload.get("run_id", body.get("run_id", ""))),
                        body,
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                    )
                if operation == "cancel":
                    return method(
                        str(payload.get("run_id", "")),
                        reason=str(payload.get("reason", "")),
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                    )
                if operation == "promote":
                    lesson = payload.get("lesson", {})
                    if not isinstance(lesson, Mapping):
                        lesson = {"text": str(lesson)}
                    return method(
                        str(payload.get("run_id", "")),
                        dict(lesson),
                        activate=payload.get("activate", False),
                        memory_store=payload.get("memory_store"),
                        idempotency_key=payload.get("idempotency_key"),
                        expected_revision=payload.get("expected_revision"),
                    )
        return None

    def read(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        operation = str(operation).strip().lower()
        if operation not in READ_OPS:
            return {"ok": False, "error": "invalid_read_operation", "operation": operation, "allowed": sorted(READ_OPS)}
        values = dict(payload or {})
        if operation == "frontier" and (not values.get("scope") or not values.get("query")):
            return {"ok": False, "error": "scope_and_query_required", "operation": operation}
        if operation in {"status", "plan", "events", "receipt"} and "run_id" in values:
            raw_run_id = values["run_id"]
            if raw_run_id is not None and raw_run_id != "":
                try:
                    validate_safe_identifier(raw_run_id, label="run_id")
                except ValueError:
                    return {"ok": False, "error": "run_id_invalid", "operation": operation}
        with self._lock:
            try:
                result = self._controller_call(operation, values)
            except Exception as exc:
                return {"ok": False, "operation": operation, "error": str(exc), "error_type": type(exc).__name__}
            if result is None:
                if operation == "status":
                    result = {"status": self._state.get("status", "idle"), "revision": self._revision}
                elif operation == "plan":
                    result = {"tasks": list(self._state.get("tasks", [])), "revision": self._revision}
                elif operation == "events":
                    result = {"events": list(self._state.get("events", [])), "revision": self._revision}
                elif operation == "receipt":
                    result = self._state.get("receipt") or {"status": self._state.get("status", "idle"), "revision": self._revision}
                else:
                    result = {"tasks": list(self._state.get("tasks", [])), "leases": dict(self._state.get("leases", {})), "revision": self._revision}
            if operation == "receipt":
                if not (
                    isinstance(result, Mapping)
                    and {"structured", "markdown", "digest"}.issubset(result)
                ):
                    try:
                        result = project_receipt(result, run_id=str(values.get("run_id", ""))).to_dict()
                    except (TypeError, ValueError):
                        pass
            response_revision = self._revision
            if isinstance(result, Mapping) and result.get("revision") is not None:
                try:
                    response_revision = int(result["revision"])
                    self._revision = max(self._revision, response_revision)
                except (TypeError, ValueError):
                    pass
            return {"ok": True, "operation": operation, "revision": response_revision, "data": _dump(result)}

    def write(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        operation = str(operation).strip().lower()
        if operation not in WRITE_OPS:
            return {"ok": False, "error": "invalid_write_operation", "operation": operation, "allowed": sorted(WRITE_OPS)}
        values = dict(payload or {})
        raw_key = values.get("idempotency_key")
        if (
            not isinstance(raw_key, str)
            or not raw_key.strip()
            or raw_key != raw_key.strip()
        ):
            return {"ok": False, "error": "idempotency_key_required", "operation": operation}
        key = raw_key
        if "expected_revision" not in values:
            return {"ok": False, "error": "expected_revision_required", "operation": operation}
        expected_value = values["expected_revision"]
        if type(expected_value) is not int or expected_value < 0:
            return {"ok": False, "error": "expected_revision_invalid", "operation": operation}
        expected = expected_value
        if (
            operation == "promote"
            and "activate" in values
            and type(values["activate"]) is not bool
        ):
            return {"ok": False, "error": "activate_invalid", "operation": operation}
        with self._lock:
            # Validate IDs before constructing an idempotency key or touching
            # a controller.  ``create`` may omit an ID so the controller can
            # generate one, but every supplied top-level or nested ID still
            # has to be a safe single path component.
            raw_run_key = values.get("run_id", "")
            nested_request = values.get("request")
            nested_run_id_supplied = isinstance(nested_request, Mapping) and "run_id" in nested_request
            run_id_candidates: list[Any] = []
            if "run_id" in values:
                run_id_candidates.append(raw_run_key)
            if nested_run_id_supplied:
                run_id_candidates.append(nested_request["run_id"])
            for candidate in run_id_candidates:
                if candidate is None or candidate == "":
                    continue
                try:
                    validate_safe_identifier(candidate, label="run_id")
                except ValueError:
                    return {"ok": False, "error": "run_id_invalid", "operation": operation}
            if operation != "create":
                if raw_run_key is None or raw_run_key == "":
                    return {"ok": False, "error": "run_id_required", "operation": operation}
                try:
                    run_key = validate_safe_identifier(raw_run_key, label="run_id")
                except ValueError:
                    return {"ok": False, "error": "run_id_invalid", "operation": operation}
            else:
                # The nested request is the effective payload for controller
                # creates; use its ID for cache scoping when present.
                effective_run_id = (
                    nested_request["run_id"]
                    if nested_run_id_supplied
                    else raw_run_key
                )
                run_key = effective_run_id if isinstance(effective_run_id, str) else ""
            invalid_task_id = _validate_task_identifiers(values, operation)
            if invalid_task_id is not None:
                return invalid_task_id
            if operation == "lease":
                owner_aliases = [
                    values[key] for key in ("owner", "worker_id") if key in values
                ]
                owner_value = owner_aliases[0] if owner_aliases else None
                if (
                    not owner_aliases
                    or not isinstance(owner_value, str)
                    or not owner_value.strip()
                    or owner_value != owner_value.strip()
                    or any(value != owner_value for value in owner_aliases[1:])
                ):
                    return {"ok": False, "error": "owner_invalid", "operation": operation}
            cache_key = f"{run_key}\0{operation}\0{key}"
            try:
                request_identity = canonical_hash(values)
            except ValueError:
                return {"ok": False, "error": "idempotency_input_invalid", "operation": operation}
            if cache_key in self._idempotency:
                if self._idempotency_inputs.get(cache_key) != request_identity:
                    return {"ok": False, "operation": operation, "error": "idempotency_conflict"}
                return dict(self._idempotency[cache_key])
            if operation != "create" and not run_key:
                return {"ok": False, "error": "run_id_required", "operation": operation}
            current_revision = 0 if operation == "create" else self._revision
            run_id = values.get("run_id")
            if self.controller is not None and run_id and operation != "create":
                try:
                    current = self._controller_call("status", {"run_id": run_id})
                    if isinstance(current, Mapping) and current.get("revision") is not None:
                        current_revision = int(current["revision"])
                        self._revision = current_revision
                except Exception:
                    pass
            durable_controller = self.controller is not None and self.controller is not False
            if not durable_controller and expected != current_revision:
                return {"ok": False, "error": "revision_conflict", "expected_revision": expected, "revision": current_revision}
            try:
                result = self._controller_call(operation, values)
            except Exception as exc:
                if type(exc).__name__ == "RevisionConflict":
                    return {
                        "ok": False,
                        "operation": operation,
                        "error": "revision_conflict",
                        "expected_revision": expected,
                        "revision": current_revision,
                    }
                return {"ok": False, "operation": operation, "error": str(exc), "error_type": type(exc).__name__}
            controller_result = result is not None
            if operation == "promote" and result is None:
                result = promote_lesson(
                    values.get("lesson", values),
                    activate=values.get("activate", False),
                )
            if result is None:
                result = {"operation": operation, "accepted": True, "payload": values}
                if operation == "create":
                    self._state["status"] = "created"
                elif operation == "cancel":
                    self._state["status"] = "cancelled"
                elif operation == "submit":
                    self._state["status"] = "submitted"
                elif operation == "advance":
                    self._state["status"] = "running"
                elif operation == "lease":
                    lease_id = str(values.get("lease_id", values.get("task_id", "lease")))
                    self._state["leases"][lease_id] = dict(values)
                self._state["events"].append({"operation": operation, "payload": values})
            if controller_result and isinstance(result, Mapping) and result.get("revision") is not None:
                try:
                    self._revision = int(result["revision"])
                except (TypeError, ValueError):
                    self._revision += 1
            else:
                self._revision += 1
            response_ok = not (
                operation == "promote"
                and isinstance(result, Mapping)
                and isinstance(result.get("promotion"), Mapping)
                and result["promotion"].get("ok") is False
            )
            response = {"ok": response_ok, "operation": operation, "revision": self._revision, "data": _dump(result)}
            self._idempotency[cache_key] = dict(response)
            self._idempotency_inputs[cache_key] = request_identity
            return response

    def dispatch(self, request: Mapping[str, Any] | str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if isinstance(request, Mapping):
            operation = str(request.get("operation", request.get("op", request.get("action", ""))))
            values = request.get("payload", request.get("data", {}))
            values = dict(values) if isinstance(values, Mapping) else {}
            # Top-level fields are accepted for compact CLI/API calls.
            values.update({key: value for key, value in request.items() if key not in {"operation", "op", "action", "mode", "payload", "data"}})
        else:
            operation = str(request)
            values = dict(payload or {})
        if operation.strip().lower() in {"read", "write"}:
            mode = operation.strip().lower()
            nested = values.pop("operation", values.pop("op", values.pop("action", "")))
            operation = str(nested)
            if not operation:
                return {"ok": False, "error": "operation_required", "mode": mode}
        operation = operation.strip().lower()
        if operation in READ_OPS:
            return self.read(operation, values)
        if operation in WRITE_OPS:
            return self.write(operation, values)
        return {"ok": False, "error": "operation_required", "allowed": sorted(READ_OPS | WRITE_OPS)}


_DEFAULT_API = RuntimeAPI()


def dispatch(request: Mapping[str, Any] | str, payload: Mapping[str, Any] | None = None, *, controller: Any = None) -> dict[str, Any]:
    api = RuntimeAPI(controller) if controller is not None else _DEFAULT_API
    return api.dispatch(request, payload)


api_dispatch = dispatch


def read(operation: str, request: Mapping[str, Any] | None = None, *, controller: Any = None) -> dict[str, Any]:
    api = RuntimeAPI(controller) if controller is not None else _DEFAULT_API
    return api.read(operation, request)


def write(operation: str, request: Mapping[str, Any] | None = None, *, controller: Any = None) -> dict[str, Any]:
    api = RuntimeAPI(controller) if controller is not None else _DEFAULT_API
    return api.write(operation, request)


sips_runtime_read = read
sips_runtime_write = write

__all__ = ["READ_OPS", "WRITE_OPS", "RuntimeAPI", "dispatch", "api_dispatch", "read", "write", "sips_runtime_read", "sips_runtime_write"]
