from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import harness_homebase_mcp as homebase_mcp


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


def run_mcp_jsonl_with_home(message: dict, home: Path) -> dict:
    env = dict(os.environ)
    env["HOME"] = str(home)
    proc = subprocess.run(
        ["python3", str(HOMEBASE_MCP)],
        input=json.dumps(message) + "\n",
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_tools_list_exposes_homebase_status_and_verify():
    response = run_mcp_jsonl({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    names = {tool["name"] for tool in response["result"]["tools"]}

    assert "homebase_status" in names
    assert "homebase_verify" in names
    assert "homebase_mcp_freshness" in names
    assert "homebase_record" in names
    assert "homebase_selfloop" in names
    assert "sips_runtime_read" in names
    assert "sips_runtime_write" in names


def test_initialize_reports_manifest_version():
    response = run_mcp_jsonl({"jsonrpc": "2.0", "id": 4, "method": "initialize", "params": {}})
    expected_version = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())["version"]

    assert response["result"]["serverInfo"] == {"name": "sips-homebase", "version": expected_version}


def test_cache_root_tracks_manifest_version(tmp_path, monkeypatch):
    version = "9.8.7"
    expected = tmp_path / ".codex" / "plugins" / "cache" / "harness-local" / "harness-self-improvement" / version
    expected.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(homebase_mcp, "plugin_version", lambda: version)

    assert homebase_mcp.sips_cache_root() == expected


def test_mcp_freshness_flags_child_tool_missing_from_explicit_allowlist(tmp_path, monkeypatch):
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    cache_script = cache / "scripts" / "harness_homebase_mcp.py"
    config = tmp_path / ".codex" / "config.toml"

    source.mkdir()
    cache_script.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    (source / ".mcp.json").write_text('{"mcpServers":{"sips-homebase":{}}}')
    (cache / ".mcp.json").write_text('{"mcpServers":{"sips-homebase":{}}}')
    cache_script.write_text(
        "import json, sys\n"
        "json.loads(sys.stdin.readline())\n"
        "print(json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {'tools': ["
        "{'name': 'homebase_status'}, {'name': 'homebase_selfloop'}]}}))\n"
    )
    config.write_text(
        '\n'.join([
            '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]',
            'enabled = true',
            'enabled_tools = ["homebase_status"]',
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(homebase_mcp, "sips_cache_root", lambda: cache)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    payload = homebase_mcp.mcp_freshness_payload(source)

    assert payload["status"] == "attention"
    assert payload["checks"]["codex_config_allows_child_tools"] is False
    assert payload["configured_tools"] == ["homebase_status"]
    assert payload["missing_enabled_tools"] == ["homebase_selfloop"]


def test_fresh_local_install_can_still_be_absent_from_complete_task_inventory(tmp_path, monkeypatch):
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    cache_script = cache / "scripts" / "harness_homebase_mcp.py"
    config = tmp_path / ".codex" / "config.toml"
    expected_tools = sorted(tool["name"] for tool in homebase_mcp.TOOLS)

    source.mkdir()
    cache_script.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    (source / ".mcp.json").write_text('{"mcpServers":{"sips-homebase":{}}}')
    (cache / ".mcp.json").write_text('{"mcpServers":{"sips-homebase":{}}}')
    cache_script.write_text(
        "import json, sys\n"
        "json.loads(sys.stdin.readline())\n"
        f"tools = {expected_tools!r}\n"
        "print(json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': "
        "{'tools': [{'name': name} for name in tools]}}))\n"
    )
    config.write_text(
        '\n'.join([
            '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]',
            'enabled = true',
            f'enabled_tools = {json.dumps(expected_tools)}',
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(homebase_mcp, "sips_cache_root", lambda: cache)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    unproven = homebase_mcp.mcp_freshness_payload(source)
    absent = homebase_mcp.mcp_freshness_payload(
        source,
        task_advertised_tools=[],
        task_inventory_complete=True,
    )

    assert unproven["status"] == "fresh"
    assert unproven["overall_status"] == "task_tools_unproven"
    assert unproven["task_exposure"]["status"] == "unproven"
    assert absent["status"] == "fresh"
    assert absent["overall_status"] == "task_tools_missing"
    assert absent["task_exposure"]["tool_exposure_checked"] is True
    assert absent["task_exposure"]["present_tools"] == []
    assert absent["task_exposure"]["missing_tools"] == expected_tools


def test_task_exposure_accepts_namespaced_homebase_tool_names():
    expected_tools = sorted(tool["name"] for tool in homebase_mcp.TOOLS)
    task_tools = [f"mcp__sips_homebase__{name}" for name in expected_tools]

    receipt = homebase_mcp.task_exposure_payload(
        expected_tools,
        task_tools,
        task_inventory_complete=True,
    )

    assert receipt["status"] == "advertised"
    assert receipt["present_tools"] == expected_tools
    assert receipt["missing_tools"] == []
    assert receipt["callability_status"] == "unproven"


def test_task_exposure_rejects_foreign_mcp_namespace_suffix_matches():
    expected_tools = sorted(tool["name"] for tool in homebase_mcp.TOOLS)
    foreign_tools = [f"mcp__other_server__{name}" for name in expected_tools]

    receipt = homebase_mcp.task_exposure_payload(
        expected_tools,
        foreign_tools,
        task_inventory_complete=True,
    )

    assert receipt["status"] == "missing_tools"
    assert receipt["present_tools"] == []
    assert receipt["missing_tools"] == expected_tools


def test_task_exposure_requires_invocation_before_callability_is_verified():
    expected_tools = sorted(tool["name"] for tool in homebase_mcp.TOOLS)
    task_tools = [f"mcp__sips-homebase__{name}" for name in expected_tools]

    advertised = homebase_mcp.task_exposure_payload(
        expected_tools,
        task_tools,
        task_inventory_complete=True,
    )
    invoked = homebase_mcp.task_exposure_payload(
        expected_tools,
        task_tools,
        task_inventory_complete=True,
        task_invoked_tools=["mcp__sips-homebase__homebase_status"],
    )

    assert advertised["status"] == "advertised"
    assert advertised["callability_status"] == "unproven"
    assert invoked["status"] == "advertised"
    assert invoked["callability_status"] == "verified"
    assert invoked["invoked_tools"] == ["homebase_status"]


def test_truncated_complete_inventory_remains_unproven():
    expected_tools = sorted(tool["name"] for tool in homebase_mcp.TOOLS)

    receipt = homebase_mcp.task_exposure_payload(
        expected_tools,
        [],
        task_inventory_complete=True,
        task_surface_truncated=True,
    )

    assert receipt["status"] == "unproven"
    assert receipt["tool_exposure_checked"] is False
    assert receipt["missing_tools"] == []
    assert receipt["callability_status"] == "unproven"


def test_truncated_inventory_is_not_reported_as_a_jsonrpc_tool_error(monkeypatch):
    captured: dict = {}

    def fake_freshness(root, task_advertised_tools, **kwargs):
        captured["task_advertised_tools"] = task_advertised_tools
        captured.update(kwargs)
        return {
            "schema": "homebase.mcp_freshness.v1",
            "root": str(root),
            "status": "fresh",
            "overall_status": "task_tools_unproven",
            "tools": ["homebase_status"],
            "task_exposure": {
                "status": "unproven",
                "callability_status": "unproven",
                "coverage": "unproven",
                "present_tools": [],
                "inventory_complete": True,
                "surface_truncated": True,
            },
        }

    monkeypatch.setattr(homebase_mcp, "mcp_freshness_payload", fake_freshness)
    response = homebase_mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "homebase_mcp_freshness",
                "arguments": {
                    "root": str(ROOT),
                    "task_advertised_tools": [],
                    "task_inventory_complete": True,
                    "task_surface_truncated": True,
                },
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    assert response["result"]["structuredContent"]["overall_status"] == "task_tools_unproven"
    assert captured["task_advertised_tools"] == []
    assert captured["task_inventory_complete"] is True
    assert captured["task_surface_truncated"] is True


def test_perception_plan_separates_plugin_ui_enumeration_from_task_callability():
    payload = homebase_mcp.perception_plan_payload(
        ROOT,
        "app",
        "ChatGPT plugin MCP connection",
        ["SIPS Homebase and sips-homebase are visible"],
    )

    assert payload["schema"] == "homebase.perception_plan.v2"
    assert payload["proof_layers"]["ui_enumeration"] == "visual_only"
    assert payload["proof_layers"]["task_tool_exposure"] == "requires_complete_task_inventory"
    assert payload["proof_layers"]["task_tool_callability"] == "requires_successful_task_invocation"
    assert "does not prove current-task callability" in payload["claim_boundary"]
    assert "enumeration/configuration" not in payload["claim_boundary"]
    assert "invoke a named tool from the current task" in payload["checks"]


def test_perception_plan_does_not_treat_generic_connection_as_plugin_surface():
    payload = homebase_mcp.perception_plan_payload(
        ROOT,
        "app",
        "Database connection settings",
        ["Database is connected"],
    )

    assert "ui_enumeration" not in payload["proof_layers"]
    assert "child_tool_advertisement" not in payload["proof_layers"]
    assert "invoke a named tool from the current task" not in payload["checks"]


def test_homebase_perception_plan_renders_list_checks_over_jsonl():
    response = run_mcp_jsonl(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "homebase_perception_plan",
                "arguments": {
                    "root": str(ROOT),
                    "surface": "app",
                    "target": "ChatGPT plugin MCP connection",
                    "expected_visible_state": ["SIPS Homebase is visible"],
                },
            },
        }
    )

    structured = response["result"]["structuredContent"]
    assert structured["schema"] == "homebase.perception_plan.v2"
    assert "## Checks" in response["result"]["content"][0]["text"]
    assert "capture screenshot" in response["result"]["content"][0]["text"]


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
    assert "sips_runtime_read" in structured["surfaces"]["mcp_tools"]


def test_cache_root_reports_a_versioned_install_candidate():
    response = run_mcp_jsonl(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "homebase_mcp_freshness", "arguments": {"root": str(ROOT)}},
        }
    )

    structured = response["result"]["structuredContent"]

    cache_root = Path(structured["cache_root"])
    assert cache_root.parent.name == "harness-self-improvement"
    assert cache_root.name


def test_homebase_status_does_not_claim_uninspected_config_or_host_transport():
    payload = homebase_mcp.status_payload(ROOT)

    assert payload["status"] == "inspected"
    assert payload["proof_layers"]["repo_source"] == "inspected"
    assert payload["proof_layers"]["worktree"] == "inspected"
    for layer in (
        "installed_cache",
        "host_config",
        "task_advertisement",
        "task_callability",
        "transport",
    ):
        assert payload["proof_layers"][layer] == "not_inspected"
    assert "repo-local source" in payload["claim_boundary"]
    assert "task callability" in payload["claim_boundary"]


def test_homebase_status_marks_missing_source_and_worktree_unavailable(tmp_path):
    payload = homebase_mcp.status_payload(tmp_path / "missing")

    assert payload["status"] == "source_not_found"
    assert payload["proof_layers"]["repo_source"] == "not_found"
    assert payload["proof_layers"]["worktree"] == "not_found"


def test_mcp_manifest_launches_homebase_via_plugin_root():
    manifest_path = ROOT / ".mcp.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    server = manifest["mcpServers"]["sips-homebase"]

    assert server["args"] == ["${CLAUDE_PLUGIN_ROOT}/scripts/harness_homebase_mcp.py"]
    assert "${PLUGIN_ROOT}" not in manifest_path.read_text(encoding="utf-8")


def test_control_plane_skill_labels_direct_mcp_fallback_as_exec_subprocess():
    skill = (ROOT / "skills" / "sips-control-plane" / "SKILL.md").read_text(encoding="utf-8")
    skill_words = " ".join(skill.lower().split())

    assert "use `tool_search`" in skill_words
    assert "initial tool list" in skill_words
    assert "do not declare the mcp unavailable" in skill_words
    assert "repo-local source subprocess" in skill
    assert "inner source-subprocess `tools/call` succeeded" in skill_words
    assert "native task mcp callability remains unproven" in skill_words
    assert "observed outer host transport conditionally" in skill_words
    assert "outer host call was `exec`" in skill
    assert "do not say that the mcp tool was called from the task" in skill_words
    assert "task_invoked_tools" in skill


def test_homebase_record_proxies_local_memory_fabric_with_sips_provenance(tmp_path):
    store = tmp_path / "memory.jsonl"
    response = run_mcp_jsonl(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "homebase_record",
                "arguments": {
                    "root": str(ROOT),
                    "tier": "learning",
                    "title": "retry lesson",
                    "body": "Use the local CLI when the Memory Fabric MCP is unavailable.",
                    "scope": str(ROOT),
                    "tags": "lesson,retry",
                    "store": str(store),
                },
            },
        }
    )

    structured = response["result"]["structuredContent"]
    record = structured["record"]["record"]

    assert structured["status"] == "passed"
    assert structured["provenance_type"] == "source_backed_agent_run"
    assert "SIPS homebase_record" in structured["provenance"]
    assert record["tier"] == "learning"
    assert record["provenance"]["type"] == "source_backed_agent_run"
    assert json.loads(store.read_text().strip())["id"] == record["id"]


def test_homebase_selfloop_starts_and_records_cycle(tmp_path):
    started = run_mcp_jsonl_with_home(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "homebase_selfloop",
                "arguments": {"root": str(ROOT), "action": "start", "focus": "tool reliability"},
            },
        },
        tmp_path,
    )
    started_state = started["result"]["structuredContent"]["state"]
    assert started_state["mode"] == "selfloop"
    assert started_state["focus"] == "tool reliability"

    recorded = run_mcp_jsonl_with_home(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "homebase_selfloop",
                "arguments": {
                    "root": str(ROOT),
                    "action": "record",
                    "outcome": "improved",
                    "summary": "snapshot regression suite now passes 18/18",
                },
            },
        },
        tmp_path,
    )
    recorded_state = recorded["result"]["structuredContent"]["state"]
    assert recorded_state["cycleCount"] == 1
    assert recorded_state["cycle"]["outcome"] == "improved"


def test_host_audit_flags_stale_hook_rows_and_retired_marketplace(tmp_path):
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        '\n'.join([
            '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]',
            'enabled = true',
            '',
            '[hooks.state."harness-self-improvement@harness-local:hooks/hooks.json:post_tool_use:99:0"]',
            'trusted_hash = "sha256:stale"',
            '',
            '[marketplaces.openai-bundled]',
            'source_type = "local"',
            'source = "/Applications/Codex.app/Contents/Resources/plugins/openai-bundled"',
        ]),
        encoding="utf-8",
    )
    response = run_mcp_jsonl_with_home(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "homebase_host_audit", "arguments": {"root": str(ROOT)}},
        },
        tmp_path,
    )

    findings = [item["detail"] for item in response["result"]["structuredContent"]["findings"]]

    assert any("stale hook trust row" in detail for detail in findings)
    assert any("retired standalone Codex app" in detail for detail in findings)


def test_host_audit_rejects_live_modified_hook_even_when_config_rows_match(tmp_path, monkeypatch):
    source = tmp_path / "source"
    hooks_path = source / "hooks" / "hooks.json"
    config = tmp_path / ".codex" / "config.toml"
    hook_key = "harness-self-improvement@harness-local:hooks/hooks.json:post_tool_use:0:0"
    hooks_path.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"command": "noop"}]}]}}),
        encoding="utf-8",
    )
    config.write_text(
        '\n'.join([
            '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]',
            'enabled = true',
            '',
            f'[hooks.state."{hook_key}"]',
            'trusted_hash = "sha256:configured"',
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    payload = homebase_mcp.host_audit_payload(
        source,
        runtime_catalog={
            "status": "inspected",
            "hooks": [
                {
                    "key": hook_key,
                    "pluginId": "harness-self-improvement@harness-local",
                    "enabled": True,
                    "trustStatus": "modified",
                    "currentHash": "sha256:live",
                }
            ],
            "warnings": [],
            "errors": [],
            "stderr": [],
        },
    )

    assert payload["status"] == "attention"
    assert payload["runtime_hooks"]["status"] == "inspected"
    assert any("not trusted" in item["detail"] for item in payload["findings"])


def test_runtime_hook_audit_fails_closed_when_live_catalog_is_unavailable():
    hook_key = "harness-self-improvement@harness-local:hooks/hooks.json:session_start:0:0"

    findings, receipt = homebase_mcp.runtime_hook_findings(
        {hook_key},
        {"status": "unavailable", "hooks": [], "error": "codex executable missing"},
    )

    assert receipt["status"] == "unavailable"
    assert any("could not be inspected" in item["detail"] for item in findings)


def test_runtime_hook_audit_accepts_exact_enabled_trusted_hashed_catalog():
    hook_key = "harness-self-improvement@harness-local:hooks/hooks.json:session_start:0:0"

    findings, receipt = homebase_mcp.runtime_hook_findings(
        {hook_key},
        {
            "status": "inspected",
            "hooks": [
                {
                    "key": hook_key,
                    "pluginId": "harness-self-improvement@harness-local",
                    "enabled": True,
                    "trustStatus": "trusted",
                    "currentHash": "sha256:live",
                },
                {
                    "key": "etsyhero@ralto-local:hooks/hooks.json:session_start:0:0",
                    "pluginId": "etsyhero@ralto-local",
                    "enabled": True,
                    "trustStatus": "modified",
                    "currentHash": "sha256:other",
                },
            ],
            "warnings": [],
            "errors": [],
            "error": "",
        },
    )

    assert findings == []
    assert receipt["observed_count"] == 1
    assert receipt["duplicate_count"] == 0


def test_host_audit_markdown_compacts_live_hook_receipts_without_losing_counts():
    hooks = [
        {
            "key": f"harness-self-improvement@harness-local:hooks/hooks.json:session_start:0:{index}",
            "pluginId": "harness-self-improvement@harness-local",
            "enabled": True,
            "trustStatus": "trusted",
            "currentHash": f"sha256:{index:064x}",
        }
        for index in range(19)
    ]
    payload = {
        "schema": "homebase.host_audit.v2",
        "root": str(ROOT),
        "config": str(Path.home() / ".codex" / "config.toml"),
        "status": "passed",
        "findings": [],
        "runtime_hooks": {
            "status": "inspected",
            "expected_count": 19,
            "observed_count": 19,
            "duplicate_count": 0,
            "hooks": hooks,
            "warnings": [],
            "errors": [],
            "error": "",
        },
        "claim_boundary": "Fresh app-server proof; already-open task rediscovery remains separate.",
    }

    markdown = homebase_mcp.render(payload, "SIPS Host Audit")

    assert "## Runtime Hooks" in markdown
    assert "observed / expected** `19 / 19`" in markdown
    assert "currentHash" not in markdown
    assert "already-open task rediscovery remains separate" in markdown


def test_generic_receipt_markdown_bounds_raw_stdout_without_changing_payload():
    stdout = "raw receipt payload " * 200
    payload = {
        "schema": "homebase.recall.v1",
        "receipt": {
            "command": ["python3", "memory_fabric.py", "search"],
            "returncode": 0,
            "ok": True,
            "stdout": stdout,
            "stderr": "",
        },
    }

    markdown = homebase_mcp.render(payload, "Harness Homebase Recall")

    assert "## Receipt" in markdown
    assert f"stdout chars** `{len(stdout)}`" in markdown
    assert stdout not in markdown
    assert payload["receipt"]["stdout"] == stdout


def test_state_markdown_bounds_history_without_changing_payload():
    history = [{"cycle": index, "summary": "history " * 200} for index in range(12)]
    payload = {
        "schema": "homebase.selfloop.v1",
        "state": {
            "status": "active",
            "mode": "selfloop",
            "focus": "bounded state rendering",
            "cycleCount": 12,
            "cycleHistory": history,
            "cycle": {"cycle": 12, "outcome": "improved", "summary": "current " * 200},
        },
    }

    markdown = homebase_mcp.render(payload, "SIPS Selfloop")

    assert "## State" in markdown
    assert "cycle history entries** `12`" in markdown
    assert "current cycle** `12` outcome=`improved`" in markdown
    assert len(markdown) < 1200
    assert payload["state"]["cycleHistory"] == history


def test_surfaces_markdown_bounds_large_lists_without_changing_payload():
    scripts = [f"script_{index}.py" for index in range(200)]
    payload = {"schema": "homebase.status.v1", "surfaces": {"scripts": scripts}}

    markdown = homebase_mcp.render(payload, "Harness Homebase Status")

    assert "scripts** count=`200`" in markdown
    assert "script_0.py" in markdown
    assert "script_199.py" not in markdown
    assert len(markdown) < 500
    assert payload["surfaces"]["scripts"] == scripts
    assert len(markdown) < 1000
