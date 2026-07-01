from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOMEBASE_MCP = ROOT / "scripts" / "harness_homebase_mcp.py"


def run_mcp_jsonl(message: dict) -> dict:
    proc = subprocess.run(
        ["python3", str(HOMEBASE_MCP)],
        input=json.dumps(message) + "\n",
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_tools_list_exposes_homebase_status_and_verify():
    response = run_mcp_jsonl({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    names = {tool["name"] for tool in response["result"]["tools"]}

    assert "homebase_status" in names
    assert "homebase_verify" in names
    assert "homebase_mcp_freshness" in names


def test_homebase_status_reports_manifest_and_mcp_surface():
    response = run_mcp_jsonl(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "homebase_status", "arguments": {"root": str(ROOT)}},
        }
    )

    structured = response["result"]["structuredContent"]

    assert structured["manifest"]["name"] == "harness-self-improvement"
    assert structured["manifest"]["has_mcp_servers"] is True
    assert "homebase_status" in structured["surfaces"]["mcp_tools"]
