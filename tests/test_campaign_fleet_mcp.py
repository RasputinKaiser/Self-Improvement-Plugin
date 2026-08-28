from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "scripts" / "harness_homebase_mcp.py"


def call_tool(name: str, arguments: dict, home: Path) -> dict:
    env = dict(os.environ)
    env["SIPS_HOME"] = str(home)
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    proc = subprocess.run(
        ["python3", str(MCP)],
        input=json.dumps(message) + "\n",
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_tools_list_and_campaign_fleet_mcp_round_trip(tmp_path):
    listing_proc = subprocess.run(
        ["python3", str(MCP)],
        input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n",
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert listing_proc.returncode == 0, listing_proc.stderr
    tools = json.loads(listing_proc.stdout)["result"]["tools"]
    names = {item["name"] for item in tools}
    assert "homebase_campaign_fleet_read" in names
    assert "homebase_campaign_fleet_write" in names

    created = call_tool(
        "homebase_campaign_fleet_write",
        {
            "operation": "create",
            "request_json": json.dumps({
                "campaign_id": "campaign-mcp",
                "objective": "Organize child threads",
                "contract": {"proof_target": "event chain"},
                "idempotency_key": "mcp-create",
            }),
        },
        tmp_path,
    )
    assert created["result"]["structuredContent"]["data"]["campaign_id"] == "campaign-mcp"

    attached = call_tool(
        "homebase_campaign_fleet_write",
        {
            "operation": "attach",
            "request_json": json.dumps({
                "campaign_id": "campaign-mcp",
                "child_id": "child-mcp",
                "title": "Archive-aware worker",
                "role": "Worker",
                "thread_id": "thread-mcp",
            }),
        },
        tmp_path,
    )
    assert attached["result"]["structuredContent"]["data"]["children"][0]["thread_id"] == "thread-mcp"

    read = call_tool(
        "homebase_campaign_fleet_read",
        {"operation": "campaign", "campaign_id": "campaign-mcp"},
        tmp_path,
    )
    result = read["result"]
    assert result["structuredContent"]["data"]["child_count"] == 1
    assert "## Child fleet" in result["content"][0]["text"]

    searched = call_tool(
        "homebase_campaign_fleet_read",
        {"operation": "search", "query": "thread-mcp"},
        tmp_path,
    )
    assert searched["result"]["structuredContent"]["data"][0]["campaign_id"] == "campaign-mcp"
