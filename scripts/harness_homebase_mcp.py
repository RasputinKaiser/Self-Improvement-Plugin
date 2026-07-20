#!/usr/bin/env python3
"""SIPS Homebase MCP server for the Self-Improvement harness.

This is the public harness repo's native MCP surface. It intentionally exposes
portable homebase_* tools instead of harness-specific names so Codex, NCode, and
future harnesses can all use the same control plane.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from sips_paths import goal_state_path

UNKNOWN_PLUGIN_VERSION = "0.0.0"
SIPS_PLUGIN_ID = "harness-self-improvement@harness-local"
STDIO_MODE = "framed"
MAX_FILE_BYTES = 3_000_000
DEFAULT_SCAN_PATTERNS = ["*.py", "*.md", "*.json", "*.yaml", "*.yml", "*.toml"]
IGNORE_DIRS = {
    ".git",
    ".codex",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


class JsonRpcError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def plugin_version() -> str:
    manifest = read_json(plugin_root() / ".codex-plugin" / "plugin.json")
    version = manifest.get("version")
    return str(version) if version else UNKNOWN_PLUGIN_VERSION


def scripts_dir() -> Path:
    return plugin_root() / "scripts"


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def array_schema(item_schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item_schema}


ROOT_PROPERTY = {
    "type": "string",
    "description": "Workspace/repo root to inspect. Defaults to the current working directory.",
}
TEXT_PROPERTY = {"type": "string", "description": "Short text input for the action."}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "homebase_status",
        "title": "SIPS Homebase Status",
        "description": "Inspect the public harness home-base manifest, commands, agents, hooks, MCP surface, and git state.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_verify",
        "title": "SIPS Homebase Verify",
        "description": "Run manifest validation and optional regression tests for the home-base harness.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "suite": {"type": "string", "description": "Optional run_tests.py suite. Defaults to no full regression run."},
                "run_tests": {"type": "boolean", "description": "Run run_tests.py. Defaults to false."},
            }
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_route",
        "title": "SIPS Homebase Route",
        "description": "Choose the best home-base command, agent, script, or MCP path for a task across Codex/NCode/generic harnesses.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "task": TEXT_PROPERTY,
                "harness": {
                    "type": "string",
                    "description": "Target harness: codex, ncode, generic, or auto. Defaults to auto.",
                },
                "mode": {"type": "string", "description": "read-only, plan, or edit. Defaults to read-only."},
            },
            required=["task"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_repo_map",
        "title": "SIPS Homebase Repo Map",
        "description": "Map a repo's files, likely test commands, git state, and planned write-scope before editing.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "write_set": array_schema({"type": "string", "description": "Path planned for editing."}),
            }
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_context_scan",
        "title": "SIPS Homebase Context Scan",
        "description": "Find oversized files and context-drain risks with bounded read advice.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "patterns": array_schema({"type": "string", "description": "Optional glob patterns."}),
                "limit": {"type": "integer", "description": "Maximum risky files. Defaults to 20."},
                "max_bytes": {"type": "integer", "description": "Risk byte threshold. Defaults to 3MB."},
            }
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_recall",
        "title": "SIPS Homebase Recall",
        "description": "Search the SIPS Memory Fabric subsystem for scoped prior lessons relevant to a query.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "query": TEXT_PROPERTY,
                "limit": {"type": "integer", "description": "Maximum records to return. Defaults to 4."},
            },
            required=["query"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_record",
        "title": "SIPS Homebase Record",
        "description": "Record a SIPS-owned Memory Fabric lesson through the local memory_fabric_record-compatible CLI.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "tier": {"type": "string", "description": "Memory tier: work, knowledge, or learning."},
                "title": {"type": "string", "description": "Short record title."},
                "body": {"type": "string", "description": "The lesson or observation to retain."},
                "scope": {"type": "string", "description": "Repo/file scope. Defaults to root."},
                "tags": {"type": "string", "description": "Comma-separated tags."},
                "confidence": {"type": "string", "description": "Record confidence. Defaults to medium."},
                "status": {"type": "string", "description": "Record status. Defaults to active."},
                "verify_before_use": {"type": "boolean", "description": "Require verification before recall use."},
                "evidence_path": {"type": "string", "description": "Optional evidence path."},
                "provenance": {"type": "string", "description": "Optional detail appended to the SIPS provenance."},
                "store": {"type": "string", "description": "Optional Memory Fabric JSONL store override."},
            },
            required=["tier", "title", "body"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_goal",
        "title": "SIPS Homebase Goal",
        "description": "Inspect the harness goal state without mutating it.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_selfloop",
        "title": "SIPS Selfloop",
        "description": "Start or control a persistent goal dedicated only to iterative SIPS and agent self-improvement.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "action": {
                    "type": "string",
                    "enum": ["start", "status", "pause", "resume", "complete", "clear", "record"],
                    "description": "Selfloop action.",
                },
                "focus": {"type": "string", "description": "Optional self-improvement focus for start."},
                "outcome": {
                    "type": "string",
                    "enum": ["improved", "plateau", "blocked"],
                    "description": "Cycle outcome for record.",
                },
                "summary": {"type": "string", "description": "Proof-bearing cycle summary for record."},
            },
            required=["action"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_routes",
        "title": "SIPS Homebase Routes",
        "description": "List SIPS command routes and their MCP, script, command, or agent equivalents.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_mcp_freshness",
        "title": "SIPS MCP Freshness",
        "description": "Check source, cache, config, child-process, and optional current-task MCP exposure for SIPS.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "task_advertised_tools": array_schema(
                    {
                        "type": "string",
                        "description": "SIPS/Homebase tool names found in the current task; unrelated names may be omitted only after inspecting the complete inventory.",
                    }
                ),
                "task_inventory_complete": {
                    "type": "boolean",
                    "description": "True only when task_advertised_tools came from a complete current-task inventory.",
                },
                "task_invoked_tools": array_schema(
                    {
                        "type": "string",
                        "description": "SIPS/Homebase tool names successfully invoked from the current task, not through a child-process fallback.",
                    }
                ),
                "task_surface_truncated": {
                    "type": "boolean",
                    "description": "True when the host may have truncated the task tool surface; absence then remains unproven.",
                },
            }
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_host_audit",
        "title": "SIPS Host Audit",
        "description": "Audit SIPS config rows plus live Codex hook presence, enablement, trust, and hash receipts.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_distill_context",
        "title": "SIPS Context Distiller",
        "description": "Extract bounded, source-linked excerpts from files without reading huge files wholesale.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "inputs": array_schema({"type": "string", "description": "File path relative to root, or absolute path."}),
                "query": TEXT_PROPERTY,
                "max_lines": {"type": "integer", "description": "Maximum lines per file. Defaults to 20."},
                "max_chars": {"type": "integer", "description": "Maximum chars per file. Defaults to 4000."},
            },
            required=["inputs"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_execution_repro",
        "title": "SIPS Execution Repro",
        "description": "Turn symptoms, logs, and failing tests into a compact repro and verification plan.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "goal": TEXT_PROPERTY,
                "symptoms": array_schema({"type": "string"}),
                "logs": array_schema({"type": "string"}),
                "failing_tests": array_schema({"type": "string"}),
            }
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_perception_plan",
        "title": "SIPS Perception Plan",
        "description": "Plan visual, screenshot, browser, app, or UI checks for a surface.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "surface": {"type": "string", "description": "browser, game, document, macos, or app."},
                "target": TEXT_PROPERTY,
                "expected_visible_state": array_schema({"type": "string"}),
            }
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_tool_factory",
        "title": "SIPS Tool Factory",
        "description": "Decide whether to reuse, improve, or scaffold a deterministic helper.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "task": TEXT_PROPERTY,
                "desired_tool": TEXT_PROPERTY,
                "existing_script": TEXT_PROPERTY,
                "force_new": {"type": "boolean", "description": "Recommend a new helper even if a likely existing script exists."},
            },
            required=["task"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "sips_runtime_read",
        "title": "SIPS Graph Runtime Read",
        "description": "Read bounded task-DAG, receipt, event, or memory-frontier state without changing it.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "operation": {
                    "type": "string",
                    "enum": ["status", "plan", "events", "receipt", "frontier"],
                    "description": "Read operation.",
                },
                "request_json": {
                    "type": "string",
                    "description": "Compact JSON object for the operation. Defaults to {}.",
                },
            },
            required=["operation"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "sips_runtime_write",
        "title": "SIPS Graph Runtime Write",
        "description": "Apply one revision-checked, idempotent graph-runtime transition.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "operation": {
                    "type": "string",
                    "enum": ["create", "submit", "lease", "advance", "cancel", "promote"],
                    "description": "Write operation.",
                },
                "request_json": {
                    "type": "string",
                    "description": "JSON object including idempotency_key and expected_revision.",
                },
            },
            required=["operation", "request_json"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
]


def write_message(payload: dict[str, Any]) -> None:
    if STDIO_MODE == "jsonl":
        sys.stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def read_message() -> dict[str, Any] | None:
    global STDIO_MODE
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        stripped = line.strip()
        if stripped.startswith(b"{"):
            STDIO_MODE = "jsonl"
            return json.loads(stripped.decode("utf-8"))
        STDIO_MODE = "framed"
        decoded = line.decode("ascii", errors="replace")
        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def workspace_root(value: Any) -> Path:
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser().resolve()
    return Path(os.getcwd()).resolve()


def safe_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float)) and str(item).strip()]


def run(command: Sequence[str], cwd: Path, *, timeout: int = 120) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "command": list(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "ok": completed.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "returncode": None,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {timeout}s",
            "ok": False,
        }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel_files(root: Path, pattern: str) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(path.relative_to(root)) for path in root.glob(pattern) if path.is_file())


def git_summary(root: Path) -> dict[str, Any]:
    if not (root / ".git").exists():
        return {"is_git": False}
    return {
        "is_git": True,
        "branch": run(("git", "branch", "--show-current"), root, timeout=15).get("stdout", ""),
        "status_short": run(("git", "status", "--short"), root, timeout=15).get("stdout", ""),
        "remote_origin": run(("git", "remote", "get-url", "origin"), root, timeout=15).get("stdout", ""),
    }


def status_payload(root: Path) -> dict[str, Any]:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    hooks_path = root / "hooks" / "hooks.json"
    mcp_path = root / ".mcp.json"
    manifest = read_json(manifest_path)
    hooks = read_json(hooks_path)
    mcp = read_json(mcp_path)
    source_available = manifest_path.is_file() and mcp_path.is_file()
    worktree_available = (root / ".git").exists()
    return {
        "schema": "homebase.status.v1",
        "status": "inspected" if source_available else "source_not_found",
        "root": str(root),
        "plugin_root": str(plugin_root()),
        "manifest": {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "description": manifest.get("description"),
            "has_hooks": bool(manifest.get("hooks")),
            "has_agents": bool(manifest.get("agents")),
            "has_commands": bool(manifest.get("commands")),
            "has_mcp_servers": bool(manifest.get("mcpServers")),
        },
        "surfaces": {
            "commands": [Path(item).stem for item in rel_files(root, "commands/*.md")],
            "agents": [Path(item).stem for item in rel_files(root, "agents/*.md")],
            "scripts": [Path(item).name for item in rel_files(root, "scripts/*.py")],
            "hook_events": sorted((hooks.get("hooks") or {}).keys()),
            "mcp_servers": sorted((mcp.get("mcpServers") or {}).keys()),
            "mcp_tools": [tool["name"] for tool in TOOLS],
        },
        "proof_layers": {
            "repo_source": "inspected" if source_available else "not_found",
            "worktree": "inspected" if worktree_available else "not_found",
            "installed_cache": "not_inspected",
            "host_config": "not_inspected",
            "task_advertisement": "not_inspected",
            "task_callability": "not_inspected",
            "transport": "not_inspected",
        },
        "git": git_summary(root),
        "claim_boundary": (
            "Status proves repo-local source and worktree inspection only. It does not inspect installed cache, "
            "host config, task advertisement, task callability, or the transport used to obtain this payload."
        ),
    }


def verify_payload(root: Path, *, run_tests: bool, suite: str) -> dict[str, Any]:
    commands = [
        ("validate_harness", ("python3", str(root / "scripts" / "validate_harness.py"))),
        ("validate_v2", ("python3", str(root / "scripts" / "validate_v2.py"))),
    ]
    if run_tests or suite:
        test_command = ["python3", str(root / "scripts" / "run_tests.py")]
        if suite:
            test_command.append(suite)
        commands.append(("run_tests", tuple(test_command)))
    receipts = []
    for label, command in commands:
        receipt = run(command, root, timeout=240 if label == "run_tests" else 120)
        receipt["label"] = label
        receipts.append(receipt)
    return {
        "schema": "homebase.verify.v1",
        "root": str(root),
        "status": "passed" if all(item["ok"] for item in receipts) else "failed",
        "receipts": receipts,
        "claim_boundary": "Verification proves source checks in this checkout. Host MCP rediscovery and downstream harness installs remain separate proof layers.",
    }


def route_payload(root: Path, task: str, harness: str, mode: str) -> dict[str, Any]:
    lowered = task.lower()
    selected: list[str] = []
    commands: list[str] = []
    agents: list[str] = []
    scripts: list[str] = []
    notes: list[str] = []

    if any(phrase in lowered for phrase in ["selfloop", "self loop", "improve yourself", "self-improve"]):
        selected.append("selfloop")
        commands.extend(["homebase_selfloop", "/selfloop"])
        scripts.append("scripts/goal_state.py")
    if any(word in lowered for word in ["context", "large file", "token", "budget"]):
        selected.append("context-scan")
        commands.append("homebase_context_scan")
    if any(word in lowered for word in ["remember", "recall", "memory", "lesson", "prior"]):
        selected.append("recall")
        commands.append("homebase_recall")
        scripts.append("scripts/recall_ranker.py")
    if any(word in lowered for word in ["stuck", "blocked", "escalate", "delegate"]):
        selected.append("delegation")
        agents.append("escalate")
        commands.append("/escalate")
    if any(word in lowered for word in ["test", "verify", "validation", "regression"]):
        selected.append("verification")
        commands.append("homebase_verify")
        scripts.append("scripts/run_tests.py")
    if any(word in lowered for word in ["goal", "state", "subtask", "ralph"]):
        selected.append("goal")
        commands.append("homebase_goal")
        scripts.append("scripts/goal_state.py")
    if any(word in lowered for word in ["repo", "map", "forensics", "inspect"]):
        selected.append("repo-map")
        commands.append("homebase_repo_map")
    if any(word in lowered for word in ["codex", "mcp", "plugin", "host"]):
        selected.append("codex-homebase")
        commands.append("homebase_status")
        notes.append("For Codex, source/cache/live MCP exposure are separate; verify with homebase_status, then host tool list after refresh.")

    if not selected:
        selected = ["homebase-status", "repo-map"]
        commands = ["homebase_status", "homebase_repo_map"]

    return {
        "schema": "homebase.route.v1",
        "root": str(root),
        "task": task,
        "harness": harness or "auto",
        "mode": mode or "read-only",
        "selected_routes": selected,
        "mcp_tools": sorted(set(commands)),
        "slash_commands": sorted(item for item in set(commands) if item.startswith("/")),
        "agents": sorted(set(agents)),
        "scripts": sorted(set(scripts)),
        "notes": notes,
    }


def repo_map_payload(root: Path, write_set: list[str]) -> dict[str, Any]:
    files = []
    for pattern in ["*.py", "scripts/*.py", "tests/*.py", "*.md", "commands/*.md", "agents/*.md"]:
        files.extend(rel_files(root, pattern))
    package = read_json(root / "package.json")
    test_commands = []
    if (root / "scripts" / "run_tests.py").exists():
        test_commands.append("python3 scripts/run_tests.py")
    if (root / "scripts" / "validate_v2.py").exists():
        test_commands.append("python3 scripts/validate_v2.py")
    if package.get("scripts", {}).get("test"):
        test_commands.append("npm test")
    return {
        "schema": "homebase.repo_map.v1",
        "root": str(root),
        "git": git_summary(root),
        "file_count_sampled": len(set(files)),
        "files": sorted(set(files))[:120],
        "write_set": write_set,
        "test_commands": test_commands,
        "risk_notes": ["working tree has existing changes" if git_summary(root).get("status_short") else "working tree appears clean"],
    }


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def context_scan_payload(root: Path, patterns: list[str], limit: int, max_bytes: int) -> dict[str, Any]:
    patterns = patterns or DEFAULT_SCAN_PATTERNS
    risky = []
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file() or should_ignore(path.relative_to(root)):
                continue
            rel = str(path.relative_to(root))
            if not any(fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel, pattern) for pattern in patterns):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size >= max_bytes:
                risky.append(
                    {
                        "path": rel,
                        "bytes": size,
                        "estimated_tokens": int(size / 4),
                        "bounded_read": f"sed -n '1,160p' {rel}",
                    }
                )
    risky.sort(key=lambda item: item["bytes"], reverse=True)
    return {
        "schema": "homebase.context_scan.v1",
        "root": str(root),
        "patterns": patterns,
        "max_bytes": max_bytes,
        "risk_count": len(risky),
        "risks": risky[: max(1, limit)],
    }


def recall_payload(root: Path, query: str, limit: int) -> dict[str, Any]:
    import recall_ranker

    mf = recall_ranker.find_cli()
    if not mf:
        return {
            "schema": "homebase.recall.v1",
            "root": str(root),
            "query": query,
            "status": "memory_fabric_unavailable",
            "records": [],
        }
    scope = root
    receipt = run(("python3", mf, "search", "--query", query, "--scope", str(scope), "--limit", str(limit)), root, timeout=15)
    records: list[dict[str, Any]] = []
    if receipt["ok"] and receipt["stdout"]:
        try:
            records = json.loads(receipt["stdout"]).get("records") or []
        except json.JSONDecodeError:
            records = []
    return {
        "schema": "homebase.recall.v1",
        "root": str(root),
        "query": query,
        "status": "passed" if receipt["ok"] else "failed",
        "records": records,
        "receipt": receipt,
        "claim_boundary": "Recall is advisory memory retrieval; verify recalled claims before relying on them.",
    }


def record_payload(
    root: Path,
    tier: str,
    title: str,
    body: str,
    scope: str,
    tags: str,
    confidence: str,
    status: str,
    verify_before_use: bool,
    evidence_path: str,
    provenance: str,
    store: str,
) -> dict[str, Any]:
    from sips_memory_fabric import find_memory_fabric_cli

    mf = find_memory_fabric_cli()
    provenance_detail = "SIPS homebase_record via harness-self-improvement"
    if provenance.strip():
        provenance_detail += f": {provenance.strip()}"
    if not mf:
        return {
            "schema": "homebase.record.v1",
            "root": str(root),
            "status": "memory_fabric_unavailable",
            "provenance_type": "source_backed_agent_run",
            "provenance": provenance_detail,
            "record": None,
        }

    command = ["python3", mf]
    if store.strip():
        command.extend(["--store", store.strip()])
    command.extend(
        [
            "record",
            "--tier", tier,
            "--title", title,
            "--body", body,
            "--scope", scope.strip() or str(root),
            "--tags", tags.strip() or "lesson,sips,homebase",
            "--provenance-type", "source_backed_agent_run",
            "--provenance", provenance_detail,
            "--evidence-path", evidence_path.strip(),
            "--confidence", confidence.strip() or "medium",
            "--status", status.strip() or "active",
        ]
    )
    if verify_before_use:
        command.append("--verify-before-use")
    receipt = run(command, root, timeout=15)
    record = None
    if receipt["ok"] and receipt["stdout"]:
        try:
            record = json.loads(receipt["stdout"])
        except json.JSONDecodeError:
            record = None
    return {
        "schema": "homebase.record.v1",
        "root": str(root),
        "status": "passed" if receipt["ok"] and record is not None else "failed",
        "provenance_type": "source_backed_agent_run",
        "provenance": provenance_detail,
        "record": record,
        "receipt": receipt,
        "claim_boundary": "Record proves a local SIPS Memory Fabric append; it does not prove host MCP rediscovery.",
    }


def goal_payload(root: Path) -> dict[str, Any]:
    candidates = [
        goal_state_path(),
        root / "state.yaml",
    ]
    states = []
    for path in candidates:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            states.append({"path": str(path), "bytes": len(text.encode("utf-8")), "preview": text[:1200]})
    return {
        "schema": "homebase.goal.v1",
        "root": str(root),
        "states": states,
        "status": "found" if states else "missing",
    }


def selfloop_payload(
    root: Path,
    action: str,
    focus: str,
    outcome: str,
    summary: str,
) -> dict[str, Any]:
    script = scripts_dir() / "goal_state.py"
    if action == "start":
        command = ("python3", str(script), "selfloop-set", focus)
    elif action == "record":
        if outcome not in {"improved", "plateau", "blocked"}:
            raise JsonRpcError(-32602, "record requires outcome: improved, plateau, or blocked")
        if not summary.strip():
            raise JsonRpcError(-32602, "record requires a proof-bearing summary")
        command = ("python3", str(script), "selfloop-record", outcome, summary)
    elif action in {"status", "pause", "resume", "complete", "clear"}:
        command = ("python3", str(script), action)
    else:
        raise JsonRpcError(-32602, f"unknown selfloop action: {action}")

    receipt = run(command, plugin_root(), timeout=15)
    state: dict[str, Any] = {}
    if receipt["stdout"]:
        try:
            state = json.loads(receipt["stdout"])
        except json.JSONDecodeError:
            state = {}
    return {
        "schema": "homebase.selfloop.v1",
        "root": str(root),
        "action": action,
        "status": "passed" if receipt["ok"] and state.get("ok") is not False else "failed",
        "state": state,
        "receipt": receipt,
        "protocol": "baseline -> select one evidence-backed weakness -> checkpoint -> improve -> verify delta -> record -> continue",
        "claim_boundary": "The tool persists loop state; the agent must still execute and verify each improvement cycle.",
    }


def routes_payload(root: Path) -> dict[str, Any]:
    routes = [
        {"route": "status", "mcp_tool": "homebase_status", "fallback": "python3 scripts/validate_harness.py"},
        {"route": "verify", "mcp_tool": "homebase_verify", "fallback": "python3 scripts/validate_v2.py && python3 scripts/run_tests.py"},
        {"route": "workflow", "mcp_tool": "homebase_route", "fallback": "/improve or /escalate"},
        {"route": "repo-map", "mcp_tool": "homebase_repo_map", "fallback": "git status --short && find/rg"},
        {"route": "context-scan", "mcp_tool": "homebase_context_scan", "fallback": "bounded rg/sed reads"},
        {"route": "recall", "mcp_tool": "homebase_recall", "fallback": "python3 scripts/recall_ranker.py --query ..."},
        {"route": "record", "mcp_tool": "homebase_record", "fallback": "python3 scripts/memory_fabric.py record ..."},
        {"route": "goal", "mcp_tool": "homebase_goal", "fallback": "python3 scripts/goal_state.py status"},
        {"route": "selfloop", "mcp_tool": "homebase_selfloop", "fallback": "/selfloop or python3 scripts/goal_state.py selfloop-set"},
        {"route": "host-audit", "mcp_tool": "homebase_host_audit", "fallback": "inspect ~/.codex/config.toml and codex app-server hooks/list"},
        {"route": "mcp-freshness", "mcp_tool": "homebase_mcp_freshness", "fallback": "child tools/list smoke"},
        {"route": "distill", "mcp_tool": "homebase_distill_context", "fallback": "sed -n bounded ranges"},
        {"route": "repro", "mcp_tool": "homebase_execution_repro", "fallback": "scripts/run_tests.py <suite>"},
        {"route": "perception", "mcp_tool": "homebase_perception_plan", "fallback": "screenshot/browser/app visual QA"},
        {"route": "tool-factory", "mcp_tool": "homebase_tool_factory", "fallback": "python3 scripts/tool_factory.py"},
        {"route": "runtime-read", "mcp_tool": "sips_runtime_read", "fallback": "python3 scripts/sips_runtime.py read --op ..."},
        {"route": "runtime-write", "mcp_tool": "sips_runtime_write", "fallback": "python3 scripts/sips_runtime.py write --op ..."},
    ]
    return {"schema": "homebase.routes.v1", "root": str(root), "routes": routes}


def sips_cache_root() -> Path:
    base = Path.home() / ".codex" / "plugins" / "cache" / "harness-local" / "harness-self-improvement"
    versioned = base / plugin_version()
    if versioned.exists():
        return versioned
    candidates = [path for path in base.iterdir() if path.is_dir()] if base.exists() else []
    if candidates:
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]
    return versioned


def configured_sips_mcp(config_text: str) -> dict[str, Any]:
    """Read the SIPS plugin MCP enablement and optional tool allowlist."""
    header = '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]'
    match = re.search(
        rf"^{re.escape(header)}\s*$(.*?)(?=^\[|\Z)",
        config_text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return {
            "section_present": False,
            "enabled": False,
            "allowlist_declared": False,
            "enabled_tools": [],
        }

    body = match.group(1)
    enabled_match = re.search(r"^enabled\s*=\s*(true|false)\s*$", body, re.MULTILINE)
    tools_match = re.search(r"^enabled_tools\s*=\s*\[(.*?)\]", body, re.MULTILINE | re.DOTALL)
    enabled_tools = re.findall(r'"([^"]+)"', tools_match.group(1)) if tools_match else []
    return {
        "section_present": True,
        "enabled": bool(enabled_match and enabled_match.group(1) == "true"),
        "allowlist_declared": tools_match is not None,
        "enabled_tools": enabled_tools,
    }


def _task_tool_is_present(expected: str, observed: str) -> bool:
    if observed == expected:
        return True
    return bool(
        re.fullmatch(
            rf"(?:mcp__)?sips[_-]homebase(?:__|[./:]){re.escape(expected)}",
            observed,
        )
    )


def task_exposure_payload(
    expected_tools: list[str],
    task_advertised_tools: list[str] | None,
    *,
    task_inventory_complete: bool = False,
    task_surface_truncated: bool = False,
    task_invoked_tools: list[str] | None = None,
) -> dict[str, Any]:
    supplied = task_advertised_tools is not None
    observed = sorted(set(task_advertised_tools or []))
    expected = sorted(set(expected_tools))
    present = [
        tool
        for tool in expected
        if any(_task_tool_is_present(tool, candidate) for candidate in observed)
    ]
    invoked_observed = sorted(set(task_invoked_tools or []))
    invoked = [
        tool
        for tool in expected
        if any(_task_tool_is_present(tool, candidate) for candidate in invoked_observed)
    ]
    inventory_usable = supplied and task_inventory_complete and not task_surface_truncated
    missing = [tool for tool in expected if tool not in present] if inventory_usable else []
    status = "unproven"
    if inventory_usable:
        status = "advertised" if not missing else "missing_tools"
    return {
        "status": status,
        "callability_status": "verified" if invoked else "unproven",
        "tool_exposure_checked": inventory_usable,
        "inventory_supplied": supplied,
        "inventory_complete": bool(task_inventory_complete),
        "surface_truncated": bool(task_surface_truncated),
        "observed_tool_count": len(observed),
        "present_tools": present,
        "missing_tools": missing,
        "invoked_tools": invoked,
        "coverage": (
            "unproven"
            if not inventory_usable
            else "complete"
            if not missing
            else "none"
            if not present
            else "partial"
        ),
        "claim_boundary": (
            "A plugin or MCP server listed in app UI proves host enumeration only. A complete, non-truncated "
            "task inventory proves advertisement or absence; successful task-local invocation proves callability."
        ),
    }


def mcp_freshness_payload(
    root: Path,
    task_advertised_tools: list[str] | None = None,
    *,
    task_inventory_complete: bool = False,
    task_surface_truncated: bool = False,
    task_invoked_tools: list[str] | None = None,
) -> dict[str, Any]:
    cache = sips_cache_root()
    config = Path.home() / ".codex" / "config.toml"
    cache_script = cache / "scripts" / "harness_homebase_mcp.py"
    cache_mcp = read_json(cache / ".mcp.json")
    source_mcp = read_json(root / ".mcp.json")
    tools_smoke = {"ok": False, "tools": [], "stderr": ""}
    if cache_script.exists():
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n"
        try:
            completed = subprocess.run(
                ["/usr/bin/python3", str(cache_script)],
                input=request,
                cwd=cache,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
            tools_smoke = {
                "ok": completed.returncode == 0 and "result" in payload,
                "tools": [tool.get("name") for tool in payload.get("result", {}).get("tools", [])],
                "stderr": completed.stderr.strip(),
            }
        except Exception as exc:
            tools_smoke = {"ok": False, "tools": [], "stderr": str(exc)}
    config_text = config.read_text(encoding="utf-8", errors="replace") if config.exists() else ""
    config_state = configured_sips_mcp(config_text)
    configured_tools = sorted(set(config_state["enabled_tools"]))
    advertised_tools = sorted(set(tools_smoke["tools"]))
    missing_enabled_tools = (
        sorted(set(advertised_tools) - set(configured_tools))
        if config_state["allowlist_declared"]
        else []
    )
    checks = {
        "source_mcp_declares_sips": "sips-homebase" in json.dumps(source_mcp),
        "cache_mcp_declares_sips": "sips-homebase" in json.dumps(cache_mcp),
        "cache_script_exists": cache_script.exists(),
        "codex_config_enables_sips": bool(
            config_state["section_present"] and config_state["enabled"]
        ),
        "codex_config_allows_child_tools": bool(
            config_state["enabled"] and not missing_enabled_tools
        ),
        "child_tools_list_ok": bool(tools_smoke["ok"]),
    }
    local_status = "fresh" if all(checks.values()) else "attention"
    task_exposure = task_exposure_payload(
        advertised_tools,
        task_advertised_tools,
        task_inventory_complete=task_inventory_complete,
        task_surface_truncated=task_surface_truncated,
        task_invoked_tools=task_invoked_tools,
    )
    if local_status != "fresh":
        overall_status = "local_attention"
    elif task_exposure["status"] == "missing_tools" and task_exposure["callability_status"] == "verified":
        overall_status = "task_evidence_conflict"
    elif task_exposure["status"] == "missing_tools":
        overall_status = "task_tools_missing"
    elif task_exposure["callability_status"] == "verified":
        overall_status = "fresh"
    elif task_exposure["status"] == "advertised":
        overall_status = "task_tools_advertised_callability_unproven"
    else:
        overall_status = "task_tools_unproven"
    return {
        "schema": "homebase.mcp_freshness.v1",
        "root": str(root),
        "cache_root": str(cache),
        "config": str(config),
        "status": local_status,
        "overall_status": overall_status,
        "checks": checks,
        "tools": tools_smoke["tools"],
        "configured_tools": configured_tools,
        "missing_enabled_tools": missing_enabled_tools,
        "smoke": tools_smoke,
        "task_exposure": task_exposure,
        "claim_boundary": (
            "Local status covers source/cache/config/child-process proof. App UI listing proves host "
            "enumeration only. A complete task inventory proves advertisement; successful task-local invocation "
            "is required before overall_status claims callability."
        ),
    }


def _read_app_server_response(
    process: subprocess.Popen[str], request_id: int, timeout_seconds: float
) -> dict[str, Any]:
    if process.stdout is None:
        raise RuntimeError("Codex app-server stdout is unavailable")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        ready, _, _ = select.select([process.stdout], [], [], min(0.25, remaining))
        if not ready:
            continue
        line = process.stdout.readline()
        if not line:
            break
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if message.get("error"):
            raise RuntimeError(f"Codex app-server request {request_id} failed: {message['error']}")
        return message
    raise TimeoutError(f"Codex app-server request {request_id} timed out")


def codex_hooks_catalog(root: Path, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Inspect the live Codex hook catalog without trusting config rows alone."""
    process: subprocess.Popen[str] | None = None
    result: dict[str, Any]
    try:
        process = subprocess.Popen(
            ["codex", "app-server"],
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if process.stdin is None:
            raise RuntimeError("Codex app-server stdin is unavailable")
        initialize = {
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "sips-host-audit",
                    "title": "SIPS Host Audit",
                    "version": "0.1.0",
                }
            },
        }
        process.stdin.write(json.dumps(initialize) + "\n")
        process.stdin.flush()
        _read_app_server_response(process, 1, timeout_seconds)
        process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
        process.stdin.write(json.dumps({"id": 2, "method": "hooks/list", "params": {}}) + "\n")
        process.stdin.flush()
        response = _read_app_server_response(process, 2, timeout_seconds)
        groups = response.get("result", {}).get("data")
        if not isinstance(groups, list):
            raise RuntimeError("Codex app-server hooks/list returned no data array")
        resolved_root = root.resolve()
        matching_groups = [
            group
            for group in groups
            if isinstance(group, dict)
            and group.get("cwd")
            and Path(str(group["cwd"])).resolve() == resolved_root
        ]
        if len(matching_groups) != 1:
            raise RuntimeError(
                f"Codex app-server returned {len(matching_groups)} hook groups for {resolved_root}"
            )
        group = matching_groups[0]
        hooks = [
            {
                "key": str(hook.get("key") or ""),
                "pluginId": str(hook.get("pluginId") or ""),
                "enabled": hook.get("enabled"),
                "trustStatus": str(hook.get("trustStatus") or "unknown"),
                "currentHash": str(hook.get("currentHash") or ""),
            }
            for hook in (group.get("hooks") or [])
            if isinstance(hook, dict) and hook.get("pluginId") == SIPS_PLUGIN_ID
        ]
        result = {
            "status": "inspected",
            "hooks": hooks,
            "warnings": [str(item) for item in (group.get("warnings") or [])],
            "errors": [str(item) for item in (group.get("errors") or [])],
            "error": "",
        }
    except (FileNotFoundError, OSError, RuntimeError, TimeoutError) as exc:
        result = {"status": "unavailable", "hooks": [], "error": str(exc)}
    finally:
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
    return result


def runtime_hook_findings(
    expected_hook_rows: set[str], catalog: dict[str, Any]
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    status = str(catalog.get("status") or "unavailable")
    hooks = [
        item
        for item in (catalog.get("hooks") or [])
        if isinstance(item, dict) and item.get("pluginId") == SIPS_PLUGIN_ID
    ]
    if status != "inspected":
        error = str(catalog.get("error") or "unknown error")
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex hook catalog could not be inspected: {error}",
        })
        return findings, {
            "status": status,
            "expected_count": len(expected_hook_rows),
            "observed_count": 0,
            "hooks": [],
            "error": error,
        }

    keys = [str(item.get("key") or "") for item in hooks if item.get("key")]
    by_key = {str(item.get("key") or ""): item for item in hooks if item.get("key")}
    runtime_rows = set(by_key)
    duplicate_rows = sorted({key for key in keys if keys.count(key) > 1})
    missing_rows = sorted(expected_hook_rows - runtime_rows)
    stale_rows = sorted(runtime_rows - expected_hook_rows)
    catalog_errors = [str(item) for item in (catalog.get("errors") or [])]
    catalog_warnings = [str(item) for item in (catalog.get("warnings") or [])]
    if catalog_errors:
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex hook catalog reported errors: {'; '.join(catalog_errors)}",
        })
    if catalog_warnings:
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex hook catalog reported warnings: {'; '.join(catalog_warnings)}",
        })
    if duplicate_rows:
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex exposes duplicate SIPS hook key(s): {', '.join(duplicate_rows)}",
        })
    if missing_rows:
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex is missing {len(missing_rows)} expected SIPS hook(s): {', '.join(missing_rows)}",
        })
    if stale_rows:
        findings.append({
            "severity": "warning",
            "detail": f"Live Codex exposes {len(stale_rows)} stale SIPS hook(s): {', '.join(stale_rows)}",
        })
    for key in sorted(expected_hook_rows & runtime_rows):
        hook = by_key[key]
        if hook.get("enabled") is not True:
            findings.append({
                "severity": "warning",
                "detail": f"Live SIPS hook is disabled: {key}",
            })
        trust_status = str(hook.get("trustStatus") or "unknown")
        if trust_status != "trusted":
            findings.append({
                "severity": "warning",
                "detail": f"Live SIPS hook is not trusted ({trust_status}): {key}",
            })
        if not hook.get("currentHash"):
            findings.append({
                "severity": "warning",
                "detail": f"Live SIPS hook has no current hash receipt: {key}",
            })
    return findings, {
        "status": status,
        "expected_count": len(expected_hook_rows),
        "observed_count": len(runtime_rows),
        "duplicate_count": len(duplicate_rows),
        "hooks": [by_key[key] for key in sorted(runtime_rows)],
        "warnings": catalog_warnings,
        "errors": catalog_errors,
        "error": str(catalog.get("error") or ""),
    }


def expected_sips_hook_rows(root: Path) -> set[str]:
    hooks = read_json(root / "hooks" / "hooks.json").get("hooks") or {}
    hook_prefix = f"{SIPS_PLUGIN_ID}:hooks/hooks.json:"
    return {
        f"{hook_prefix}{re.sub(r'(?<!^)(?=[A-Z])', '_', event).lower()}:{group_index}:{hook_index}"
        for event, groups in hooks.items()
        for group_index, group in enumerate(groups)
        for hook_index, _ in enumerate(group.get("hooks") or [])
    }


def host_audit_payload(
    root: Path, runtime_catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    config = Path.home() / ".codex" / "config.toml"
    text = config.read_text(encoding="utf-8", errors="replace") if config.exists() else ""
    legacy_name = "codex-" + "self-improvement"
    legacy_plugin_header = f"[plugins.\"{legacy_name}@ralto-local\"]"
    legacy_mcp_header = f"[mcp_servers.{legacy_name}]"
    legacy_memory_header = "[plugins.\"codex-memory-fabric@ralto-local\"]"
    old_active = legacy_plugin_header in text and "enabled = true" in text.split(legacy_plugin_header, 1)[1].split("[plugins.", 1)[0]
    old_standalone_active = legacy_mcp_header in text and "enabled = true" in text.split(legacy_mcp_header, 1)[1].split("[mcp_servers.", 1)[0]
    old_memory_active = legacy_memory_header in text and "enabled = true" in text.split(legacy_memory_header, 1)[1].split("[plugins.", 1)[0]
    findings = []
    if old_active:
        findings.append({"severity": "warning", "detail": "Legacy self-improvement plugin block is still enabled."})
    if old_standalone_active:
        findings.append({"severity": "warning", "detail": "Legacy standalone self-improvement MCP block is still enabled."})
    if old_memory_active:
        findings.append({"severity": "warning", "detail": "Standalone Memory Fabric plugin block is still enabled; SIPS should own Memory Fabric locally."})
    if "sips-homebase" not in text:
        findings.append({"severity": "error", "detail": "SIPS sips-homebase MCP block is missing from Codex config."})

    hook_prefix = f"{SIPS_PLUGIN_ID}:hooks/hooks.json:"
    expected_hook_rows = expected_sips_hook_rows(root)
    configured_hook_rows = {
        match.group(1)
        for match in re.finditer(r'^\[hooks\.state\."([^"]+)"\]$', text, re.MULTILINE)
        if match.group(1).startswith(hook_prefix)
    }
    stale_hook_rows = sorted(configured_hook_rows - expected_hook_rows)
    missing_hook_rows = sorted(expected_hook_rows - configured_hook_rows)
    if stale_hook_rows:
        findings.append({
            "severity": "warning",
            "detail": f"SIPS has {len(stale_hook_rows)} stale hook trust row(s): {', '.join(stale_hook_rows)}",
        })
    if missing_hook_rows:
        findings.append({
            "severity": "warning",
            "detail": f"SIPS has {len(missing_hook_rows)} hook row(s) missing from host trust state.",
        })

    runtime_findings, runtime_hooks = runtime_hook_findings(
        expected_hook_rows,
        runtime_catalog if runtime_catalog is not None else codex_hooks_catalog(root),
    )
    findings.extend(runtime_findings)

    for match in re.finditer(r'^\[marketplaces\.([^\]]+)\]\s*$(.*?)(?=^\[|\Z)', text, re.MULTILINE | re.DOTALL):
        name, body = match.groups()
        source_type = re.search(r'^source_type\s*=\s*"([^"]+)"', body, re.MULTILINE)
        source = re.search(r'^source\s*=\s*"([^"]+)"', body, re.MULTILINE)
        if not source or not source_type or source_type.group(1) != "local":
            continue
        source_path = Path(source.group(1)).expanduser()
        if not source_path.exists():
            findings.append({
                "severity": "warning",
                "detail": f"Local marketplace {name} points at missing path: {source_path}",
            })
        if name == "openai-bundled" and "/Codex.app/" in source.group(1):
            findings.append({
                "severity": "warning",
                "detail": "openai-bundled still points at the retired standalone Codex app instead of the merged ChatGPT runtime.",
            })
    return {
        "schema": "homebase.host_audit.v2",
        "root": str(root),
        "config": str(config),
        "status": "passed" if not findings else "attention",
        "findings": findings,
        "runtime_hooks": runtime_hooks,
        "claim_boundary": "Passed proves a freshly spawned Codex app-server catalog for this root has every expected SIPS hook present, enabled, trusted, and hashed. An already-open task can still retain stale dispatcher state until host rediscovery.",
    }


def resolve_input_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def distill_payload(root: Path, inputs: list[str], query: str, max_lines: int, max_chars: int) -> dict[str, Any]:
    excerpts = []
    query_words = {word.lower() for word in query.split() if len(word) > 2}
    for value in inputs:
        path = resolve_input_path(root, value)
        item: dict[str, Any] = {"input": value, "path": str(path), "exists": path.exists(), "excerpts": []}
        if path.exists() and path.is_file():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                selected = []
                for index, line in enumerate(lines, 1):
                    if not query_words or any(word in line.lower() for word in query_words):
                        selected.append((index, line))
                    if len(selected) >= max_lines:
                        break
                if not selected:
                    selected = list(enumerate(lines[:max_lines], 1))
                text = "\n".join(f"{line_no}: {line}" for line_no, line in selected)[:max_chars]
                item["excerpts"].append(text)
            except OSError as exc:
                item["error"] = str(exc)
        excerpts.append(item)
    return {"schema": "homebase.distill_context.v1", "root": str(root), "query": query, "sources": excerpts}


def execution_repro_payload(root: Path, goal: str, symptoms: list[str], logs: list[str], failing_tests: list[str]) -> dict[str, Any]:
    commands = []
    if failing_tests:
        commands.extend(failing_tests)
    elif (root / "scripts" / "run_tests.py").exists():
        commands.append("python3 scripts/run_tests.py")
    if (root / "scripts" / "validate_v2.py").exists():
        commands.append("python3 scripts/validate_v2.py")
    return {
        "schema": "homebase.execution_repro.v1",
        "root": str(root),
        "goal": goal,
        "symptoms": symptoms,
        "logs": logs[-5:],
        "repro_steps": [
            "Confirm the exact failing command or visible symptom.",
            "Run the smallest validation command listed below.",
            "Inspect only touched files and adjacent tests.",
            "Rerun the same validation command after the fix.",
        ],
        "verification_commands": commands,
    }


def perception_plan_payload(root: Path, surface: str, target: str, expected: list[str]) -> dict[str, Any]:
    checks = ["capture screenshot", "inspect visible text", "verify no overlap/clipping", "exercise primary interaction"]
    if surface in {"browser", "game"}:
        checks.extend(["check console errors", "verify canvas/image is nonblank"])
    plugin_surface = any(token in target.lower() for token in ("plugin", "mcp"))
    proof_layers = {
        "visible_state": "visual_only",
        "runtime_interaction": "requires_direct_interaction",
    }
    claim_boundary = "A screenshot proves only the visible state captured in that image."
    if plugin_surface:
        checks.extend(
            [
                "verify the plugin or MCP server is enumerated in the host UI",
                "verify config and child tools/list separately",
                "invoke a named tool from the current task",
            ]
        )
        proof_layers.update(
            {
                "ui_enumeration": "visual_only",
                "host_configuration": "requires_config_or_host_catalog",
                "child_tool_advertisement": "requires_child_tools_list",
                "task_tool_exposure": "requires_complete_task_inventory",
                "task_tool_callability": "requires_successful_task_invocation",
            }
        )
        claim_boundary = (
            "A plugin or MCP server listed in app UI proves enumeration only; it does not "
            "prove current-task callability. Verify the task tool inventory or invoke a named tool."
        )
    return {
        "schema": "homebase.perception_plan.v2",
        "root": str(root),
        "surface": surface,
        "target": target,
        "expected_visible_state": expected,
        "checks": checks,
        "proof_layers": proof_layers,
        "claim_boundary": claim_boundary,
    }


def tool_factory_payload(root: Path, task: str, desired_tool: str, existing_script: str, force_new: bool) -> dict[str, Any]:
    scripts = [path.name for path in (root / "scripts").glob("*.py")] if (root / "scripts").exists() else []
    lowered = f"{task} {desired_tool} {existing_script}".lower()
    candidates = [name for name in scripts if any(part and part in name.lower() for part in lowered.replace("_", " ").replace("-", " ").split())]
    decision = "scaffold" if force_new or not candidates else "reuse_or_improve"
    return {
        "schema": "homebase.tool_factory.v1",
        "root": str(root),
        "task": task,
        "desired_tool": desired_tool,
        "existing_script": existing_script,
        "decision": decision,
        "candidate_scripts": candidates[:10],
        "next_command": f"python3 scripts/tool_factory.py scaffold {desired_tool or 'new_helper'} --dry-run" if decision == "scaffold" else f"python3 scripts/tool_factory.py validate {candidates[0].removesuffix('.py')}" if candidates else "",
    }


def tool_result(payload: dict[str, Any], markdown: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": markdown}],
        "structuredContent": payload,
        "isError": is_error,
    }


def runtime_tool_payload(root: Path, operation: str, request_json: str, *, write: bool) -> dict[str, Any]:
    try:
        request = json.loads(request_json or "{}")
    except json.JSONDecodeError as exc:
        raise JsonRpcError(-32602, f"request_json is invalid JSON: {exc.msg}") from exc
    if not isinstance(request, dict):
        raise JsonRpcError(-32602, "request_json must contain a JSON object")
    request.setdefault("workspace_root", str(root))
    try:
        from sips_runtime.api import RuntimeAPI
    except (ImportError, ModuleNotFoundError) as exc:
        raise JsonRpcError(-32000, f"SIPS graph runtime unavailable: {exc}") from exc
    api = RuntimeAPI()
    result = api.write(operation, request) if write else api.read(operation, request)
    return dict(result)


def runtime_markdown(payload: dict[str, Any], title: str) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        markdown = data.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            return markdown[:8000]
    return render(payload, title)[:8000]


def render(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if key in {"receipt", "receipts", "state", "files", "risks", "records", "surfaces", "git", "routes", "findings", "sources", "checks", "verification_commands", "repro_steps", "runtime_hooks", "task_exposure", "proof_layers"}:
            continue
        lines.append(f"- **{key}** `{value}`")
    if "runtime_hooks" in payload:
        runtime = payload["runtime_hooks"] if isinstance(payload["runtime_hooks"], dict) else {}
        hooks = [item for item in (runtime.get("hooks") or []) if isinstance(item, dict)]
        lines.append("")
        lines.append("## Runtime Hooks")
        lines.append(f"- **status** `{runtime.get('status', 'unknown')}`")
        lines.append(
            f"- **observed / expected** `{runtime.get('observed_count', 0)} / {runtime.get('expected_count', 0)}`"
        )
        lines.append(f"- **duplicates** `{runtime.get('duplicate_count', 0)}`")
        lines.append(f"- **disabled** `{sum(item.get('enabled') is not True for item in hooks)}`")
        lines.append(f"- **untrusted** `{sum(item.get('trustStatus') != 'trusted' for item in hooks)}`")
        lines.append(f"- **unhashed** `{sum(not item.get('currentHash') for item in hooks)}`")
        lines.append(f"- **catalog warnings / errors** `{len(runtime.get('warnings') or [])} / {len(runtime.get('errors') or [])}`")
        if runtime.get("error"):
            lines.append(f"- **probe error** `{runtime['error']}`")
    if "receipt" in payload:
        receipt = payload["receipt"] if isinstance(payload["receipt"], dict) else {}
        lines.append("")
        lines.append("## Receipt")
        for key in ("ok", "returncode", "timed_out"):
            if key in receipt:
                lines.append(f"- **{key}** `{receipt[key]}`")
        command = receipt.get("command")
        if isinstance(command, list):
            lines.append(f"- **command** `{command}`")
        stdout = receipt.get("stdout")
        if isinstance(stdout, str):
            lines.append(f"- **stdout chars** `{len(stdout)}`")
        stderr = receipt.get("stderr")
        if isinstance(stderr, str) and stderr:
            lines.append(f"- **stderr** `{stderr[:240]}`")
    if "state" in payload:
        state = payload["state"] if isinstance(payload["state"], dict) else {}
        lines.append("")
        lines.append("## State")
        for key in ("status", "mode", "focus", "objective", "turnCount", "cycleCount", "plateauStreak"):
            value = state.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                value = value[:320]
            lines.append(f"- **{key}** `{value}`")
        cycle = state.get("cycle")
        if isinstance(cycle, dict):
            lines.append(f"- **current cycle** `{cycle.get('cycle', '?')}` outcome=`{cycle.get('outcome', '?')}`")
            summary = cycle.get("summary")
            if isinstance(summary, str) and summary:
                lines.append(f"- **current cycle summary** `{summary[:320]}`")
        history = state.get("cycleHistory")
        if isinstance(history, list):
            lines.append(f"- **cycle history entries** `{len(history)}`")
    if "checks" in payload:
        lines.append("")
        lines.append("## Checks")
        checks = payload["checks"]
        if isinstance(checks, dict):
            for key, value in checks.items():
                lines.append(f"- **{key}** `{value}`")
        else:
            for item in checks if isinstance(checks, list) else []:
                lines.append(f"- `{item}`")
    if "task_exposure" in payload:
        task = payload["task_exposure"] if isinstance(payload["task_exposure"], dict) else {}
        lines.append("")
        lines.append("## Current Task Exposure")
        lines.append(f"- **status** `{task.get('status', 'unproven')}`")
        lines.append(f"- **callability** `{task.get('callability_status', 'unproven')}`")
        lines.append(f"- **coverage** `{task.get('coverage', 'unproven')}`")
        lines.append(f"- **present / expected** `{len(task.get('present_tools') or [])} / {len(payload.get('tools') or [])}`")
        lines.append(f"- **inventory complete** `{task.get('inventory_complete', False)}`")
        lines.append(f"- **surface truncated** `{task.get('surface_truncated', False)}`")
    if "proof_layers" in payload:
        lines.append("")
        lines.append("## Proof Layers")
        for key, value in payload["proof_layers"].items():
            lines.append(f"- **{key}** `{value}`")
    if "surfaces" in payload:
        lines.append("")
        lines.append("## Surfaces")
        for key, value in payload["surfaces"].items():
            if isinstance(value, list):
                sample = value[:12]
                suffix = " ..." if len(value) > len(sample) else ""
                lines.append(f"- **{key}** count=`{len(value)}` sample=`{sample}{suffix}`")
            else:
                lines.append(f"- **{key}** `{value}`")
    if "git" in payload:
        lines.append("")
        lines.append("## Git")
        for key, value in payload["git"].items():
            lines.append(f"- **{key}** `{value}`")
    if "receipts" in payload:
        lines.append("")
        lines.append("## Receipts")
        for item in payload["receipts"]:
            lines.append(f"- `{item.get('label')}` rc=`{item.get('returncode')}` ok=`{item.get('ok')}`")
    if "risks" in payload:
        lines.append("")
        lines.append("## Context Risks")
        for item in payload["risks"]:
            lines.append(f"- `{item['path']}` bytes=`{item['bytes']}` read=`{item['bounded_read']}`")
    if "routes" in payload:
        lines.append("")
        lines.append("## Routes")
        for item in payload["routes"]:
            lines.append(f"- **{item['route']}** `{item['mcp_tool']}` fallback=`{item['fallback']}`")
    if "findings" in payload:
        lines.append("")
        lines.append("## Findings")
        if not payload["findings"]:
            lines.append("- none")
        for item in payload["findings"]:
            lines.append(f"- `{item.get('severity', 'info')}` {item.get('detail', '')}")
    if "sources" in payload:
        lines.append("")
        lines.append("## Sources")
        for item in payload["sources"]:
            lines.append(f"### `{item.get('input')}`")
            for excerpt in item.get("excerpts", []):
                lines.extend(["```text", excerpt, "```"])
    if "repro_steps" in payload:
        lines.append("")
        lines.append("## Repro Steps")
        for step in payload["repro_steps"]:
            lines.append(f"- {step}")
    if "verification_commands" in payload:
        lines.append("")
        lines.append("## Verification Commands")
        for command in payload["verification_commands"]:
            lines.append(f"- `{command}`")
    if "records" in payload:
        lines.append("")
        lines.append("## Records")
        for item in payload["records"][:10]:
            title_value = item.get("title") or item.get("id") or "record"
            body = str(item.get("body") or "").replace("\n", " ")[:180]
            lines.append(f"- `{title_value}` {body}")
    return "\n".join(lines).rstrip() + "\n"


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    root = workspace_root(arguments.get("root")) if arguments.get("root") else plugin_root()
    if name == "homebase_status":
        payload = status_payload(root)
        return tool_result(
            payload,
            render(payload, "Harness Homebase Status"),
            is_error=payload["status"] != "inspected",
        )
    if name == "homebase_verify":
        suite = str(arguments.get("suite") or "").strip()
        payload = verify_payload(root, run_tests=bool(arguments.get("run_tests")), suite=suite)
        return tool_result(payload, render(payload, "Harness Homebase Verify"), is_error=payload["status"] != "passed")
    if name == "homebase_route":
        task = str(arguments.get("task") or "").strip()
        if not task:
            raise JsonRpcError(-32602, "task is required")
        payload = route_payload(root, task, str(arguments.get("harness") or "auto"), str(arguments.get("mode") or "read-only"))
        return tool_result(payload, render(payload, "Harness Homebase Route"))
    if name == "homebase_repo_map":
        payload = repo_map_payload(root, safe_strings(arguments.get("write_set")))
        return tool_result(payload, render(payload, "Harness Homebase Repo Map"))
    if name == "homebase_context_scan":
        payload = context_scan_payload(
            root,
            safe_strings(arguments.get("patterns")),
            int(arguments.get("limit") or 20),
            int(arguments.get("max_bytes") or MAX_FILE_BYTES),
        )
        return tool_result(payload, render(payload, "Harness Homebase Context Scan"))
    if name == "homebase_recall":
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise JsonRpcError(-32602, "query is required")
        payload = recall_payload(root, query, int(arguments.get("limit") or 4))
        return tool_result(payload, render(payload, "Harness Homebase Recall"), is_error=payload["status"] == "failed")
    if name == "homebase_record":
        tier = str(arguments.get("tier") or "").strip()
        title = str(arguments.get("title") or "").strip()
        body = str(arguments.get("body") or "").strip()
        if not tier or not title or not body:
            raise JsonRpcError(-32602, "tier, title, and body are required")
        payload = record_payload(
            root,
            tier,
            title,
            body,
            str(arguments.get("scope") or ""),
            str(arguments.get("tags") or ""),
            str(arguments.get("confidence") or "medium"),
            str(arguments.get("status") or "active"),
            bool(arguments.get("verify_before_use")),
            str(arguments.get("evidence_path") or ""),
            str(arguments.get("provenance") or ""),
            str(arguments.get("store") or ""),
        )
        return tool_result(payload, render(payload, "SIPS Homebase Record"), is_error=payload["status"] == "failed")
    if name == "homebase_goal":
        payload = goal_payload(root)
        return tool_result(payload, render(payload, "Harness Homebase Goal"))
    if name == "homebase_selfloop":
        action = str(arguments.get("action") or "").strip()
        if not action:
            raise JsonRpcError(-32602, "action is required")
        payload = selfloop_payload(
            root,
            action,
            str(arguments.get("focus") or ""),
            str(arguments.get("outcome") or ""),
            str(arguments.get("summary") or ""),
        )
        return tool_result(payload, render(payload, "SIPS Selfloop"), is_error=payload["status"] != "passed")
    if name == "homebase_routes":
        payload = routes_payload(root)
        return tool_result(payload, render(payload, "SIPS Homebase Routes"))
    if name == "homebase_mcp_freshness":
        task_advertised_tools = (
            safe_strings(arguments.get("task_advertised_tools"))
            if "task_advertised_tools" in arguments
            else None
        )
        payload = mcp_freshness_payload(
            root,
            task_advertised_tools,
            task_inventory_complete=bool(arguments.get("task_inventory_complete")),
            task_surface_truncated=bool(arguments.get("task_surface_truncated")),
            task_invoked_tools=safe_strings(arguments.get("task_invoked_tools")),
        )
        is_error = payload["status"] != "fresh" or payload["overall_status"] in {
            "task_tools_missing",
            "task_evidence_conflict",
        }
        return tool_result(payload, render(payload, "SIPS MCP Freshness"), is_error=is_error)
    if name == "homebase_host_audit":
        payload = host_audit_payload(root)
        return tool_result(payload, render(payload, "SIPS Host Audit"), is_error=payload["status"] != "passed")
    if name == "homebase_distill_context":
        inputs = safe_strings(arguments.get("inputs"))
        if not inputs:
            raise JsonRpcError(-32602, "inputs is required")
        payload = distill_payload(
            root,
            inputs,
            str(arguments.get("query") or ""),
            int(arguments.get("max_lines") or 20),
            int(arguments.get("max_chars") or 4000),
        )
        return tool_result(payload, render(payload, "SIPS Context Distiller"))
    if name == "homebase_execution_repro":
        payload = execution_repro_payload(
            root,
            str(arguments.get("goal") or ""),
            safe_strings(arguments.get("symptoms")),
            safe_strings(arguments.get("logs")),
            safe_strings(arguments.get("failing_tests")),
        )
        return tool_result(payload, render(payload, "SIPS Execution Repro"))
    if name == "homebase_perception_plan":
        payload = perception_plan_payload(
            root,
            str(arguments.get("surface") or "app"),
            str(arguments.get("target") or "current surface"),
            safe_strings(arguments.get("expected_visible_state")),
        )
        return tool_result(payload, render(payload, "SIPS Perception Plan"))
    if name == "homebase_tool_factory":
        task = str(arguments.get("task") or "").strip()
        if not task:
            raise JsonRpcError(-32602, "task is required")
        payload = tool_factory_payload(
            root,
            task,
            str(arguments.get("desired_tool") or ""),
            str(arguments.get("existing_script") or ""),
            bool(arguments.get("force_new")),
        )
        return tool_result(payload, render(payload, "SIPS Tool Factory"))
    if name == "sips_runtime_read":
        operation = str(arguments.get("operation") or "").strip().lower()
        payload = runtime_tool_payload(
            root,
            operation,
            str(arguments.get("request_json") or "{}"),
            write=False,
        )
        return tool_result(
            payload,
            runtime_markdown(payload, "SIPS Graph Runtime Read"),
            is_error=payload.get("ok") is not True,
        )
    if name == "sips_runtime_write":
        operation = str(arguments.get("operation") or "").strip().lower()
        payload = runtime_tool_payload(
            root,
            operation,
            str(arguments.get("request_json") or "{}"),
            write=True,
        )
        return tool_result(
            payload,
            runtime_markdown(payload, "SIPS Graph Runtime Write"),
            is_error=payload.get("ok") is not True,
        )
    raise JsonRpcError(-32601, f"Unknown tool: {name}")


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    try:
        if method == "initialize":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            result = {
                "protocolVersion": params.get("protocolVersion", "2025-03-26"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sips-homebase", "version": plugin_version()},
                "instructions": "Use homebase_* tools as the SIPS shared harness control plane across Codex, NCode, and future harnesses.",
            }
        elif method == "notifications/initialized":
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            result = call_tool(name, arguments)
        else:
            raise JsonRpcError(-32601, f"Unsupported method: {method}")
        if "id" not in message:
            return None
        return {"jsonrpc": "2.0", "id": message["id"], "result": result}
    except JsonRpcError as exc:
        if "id" not in message:
            return None
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        if "id" not in message:
            return None
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32000, "message": str(exc)}}


def main() -> None:
    while True:
        message = read_message()
        if message is None:
            break
        response = handle_request(message)
        if response is not None:
            write_message(response)


if __name__ == "__main__":
    main()
