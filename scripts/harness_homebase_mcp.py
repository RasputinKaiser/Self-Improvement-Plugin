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
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


PLUGIN_VERSION = "0.2.0"
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
        "name": "homebase_goal",
        "title": "SIPS Homebase Goal",
        "description": "Inspect the harness goal state without mutating it.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
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
        "description": "Check source, cache, config, and child-process MCP exposure for SIPS.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "homebase_host_audit",
        "title": "SIPS Host Audit",
        "description": "Audit Codex config and cache wiring for SIPS host visibility.",
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
    manifest = read_json(root / ".codex-plugin" / "plugin.json")
    hooks = read_json(root / "hooks" / "hooks.json")
    mcp = read_json(root / ".mcp.json")
    return {
        "schema": "homebase.status.v1",
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
        "git": git_summary(root),
        "claim_boundary": "Status is local source/config proof. It does not prove an already-open host has refreshed this MCP server.",
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


def goal_payload(root: Path) -> dict[str, Any]:
    candidates = [
        Path.home() / ".ncode" / "goal_state.json",
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


def routes_payload(root: Path) -> dict[str, Any]:
    routes = [
        {"route": "status", "mcp_tool": "homebase_status", "fallback": "python3 scripts/validate_harness.py"},
        {"route": "verify", "mcp_tool": "homebase_verify", "fallback": "python3 scripts/validate_v2.py && python3 scripts/run_tests.py"},
        {"route": "workflow", "mcp_tool": "homebase_route", "fallback": "/improve or /escalate"},
        {"route": "repo-map", "mcp_tool": "homebase_repo_map", "fallback": "git status --short && find/rg"},
        {"route": "context-scan", "mcp_tool": "homebase_context_scan", "fallback": "bounded rg/sed reads"},
        {"route": "recall", "mcp_tool": "homebase_recall", "fallback": "python3 scripts/recall_ranker.py --query ..."},
        {"route": "goal", "mcp_tool": "homebase_goal", "fallback": "python3 scripts/goal_state.py status"},
        {"route": "host-audit", "mcp_tool": "homebase_host_audit", "fallback": "inspect ~/.codex/config.toml and cache .mcp.json"},
        {"route": "mcp-freshness", "mcp_tool": "homebase_mcp_freshness", "fallback": "child tools/list smoke"},
        {"route": "distill", "mcp_tool": "homebase_distill_context", "fallback": "sed -n bounded ranges"},
        {"route": "repro", "mcp_tool": "homebase_execution_repro", "fallback": "scripts/run_tests.py <suite>"},
        {"route": "perception", "mcp_tool": "homebase_perception_plan", "fallback": "screenshot/browser/app visual QA"},
        {"route": "tool-factory", "mcp_tool": "homebase_tool_factory", "fallback": "python3 scripts/tool_factory.py"},
    ]
    return {"schema": "homebase.routes.v1", "root": str(root), "routes": routes}


def sips_cache_root() -> Path:
    return Path.home() / ".codex" / "plugins" / "cache" / "harness-local" / "harness-self-improvement" / "0.2.0"


def mcp_freshness_payload(root: Path) -> dict[str, Any]:
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
    checks = {
        "source_mcp_declares_sips": "sips-homebase" in json.dumps(source_mcp),
        "cache_mcp_declares_sips": "sips-homebase" in json.dumps(cache_mcp),
        "cache_script_exists": cache_script.exists(),
        "codex_config_enables_sips": "sips-homebase" in config_text and "homebase_status" in config_text,
        "child_tools_list_ok": bool(tools_smoke["ok"]),
    }
    return {
        "schema": "homebase.mcp_freshness.v1",
        "root": str(root),
        "cache_root": str(cache),
        "config": str(config),
        "status": "fresh" if all(checks.values()) else "attention",
        "checks": checks,
        "tools": tools_smoke["tools"],
        "smoke": tools_smoke,
        "claim_boundary": "Fresh here means source/cache/config/child-process proof. Already-open Codex sessions still need host rediscovery after restart.",
    }


def host_audit_payload(root: Path) -> dict[str, Any]:
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
    return {
        "schema": "homebase.host_audit.v1",
        "root": str(root),
        "config": str(config),
        "status": "passed" if not findings else "attention",
        "findings": findings,
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
    return {"schema": "homebase.perception_plan.v1", "root": str(root), "surface": surface, "target": target, "expected_visible_state": expected, "checks": checks}


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


def render(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if key in {"receipts", "files", "risks", "records", "surfaces", "git", "routes", "findings", "sources", "checks", "verification_commands", "repro_steps"}:
            continue
        lines.append(f"- **{key}** `{value}`")
    if "checks" in payload:
        lines.append("")
        lines.append("## Checks")
        for key, value in payload["checks"].items():
            lines.append(f"- **{key}** `{value}`")
    if "surfaces" in payload:
        lines.append("")
        lines.append("## Surfaces")
        for key, value in payload["surfaces"].items():
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
        return tool_result(payload, render(payload, "Harness Homebase Status"))
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
    if name == "homebase_goal":
        payload = goal_payload(root)
        return tool_result(payload, render(payload, "Harness Homebase Goal"))
    if name == "homebase_routes":
        payload = routes_payload(root)
        return tool_result(payload, render(payload, "SIPS Homebase Routes"))
    if name == "homebase_mcp_freshness":
        payload = mcp_freshness_payload(root)
        return tool_result(payload, render(payload, "SIPS MCP Freshness"), is_error=payload["status"] != "fresh")
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
    raise JsonRpcError(-32601, f"Unknown tool: {name}")


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    try:
        if method == "initialize":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            result = {
                "protocolVersion": params.get("protocolVersion", "2025-03-26"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sips-homebase", "version": PLUGIN_VERSION},
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
