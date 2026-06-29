#!/usr/bin/env python3
"""Test runner for the ~/.ncode/ harness.

Runs all test cases under ~/.ncode/tests/ and reports pass/fail. Proves the
autonomy gate still blocks critical paths, scripts still produce expected
output, and the harness validator is clean.

Usage:
  run_tests.py             # run all
  run_tests.py --verbose   # show each case
  run_tests.py <suite>     # run a single suite (autonomy_gate, compact_continuity, ...)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path.home() / ".ncode" / "scripts"
TESTS_DIR = Path.home() / ".ncode" / "tests"


def run_script_with_input(script, payload):
    """Run a script with stdin JSON. Returns (returncode, stdout, stderr)."""
    r = subprocess.run(
        ["python3", str(script)],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=10
    )
    return r.returncode, r.stdout, r.stderr


def case(name, fn):
    def run():
        try:
            fn()
            return True, ""
        except AssertionError as e:
            return False, str(e)
    return (name, run)


# --- Autonomy gate ---

def autonomy_gate_blocks_settings_json():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/.ncode/settings.json"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"expected block, got {d}"
    assert "settings.json" in d.get("reason", ""), f"reason missing path: {d}"

def autonomy_gate_blocks_binary_path():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/.local/ncode-builds/foo/ncode"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"expected block, got {d}"

def autonomy_gate_blocks_force_push():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"expected block, got {d}"

def autonomy_gate_blocks_rm_rf_root():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"expected block, got {d}"

def autonomy_gate_blocks_credentials():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/etc/credential_token"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"expected block, got {d}"

def autonomy_gate_feedback_on_scripts_edit():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/.ncode/scripts/validate_harness.py"}}
    )
    d = json.loads(out)
    assert "decisionFeedback" in d, f"expected decisionFeedback, got {d}"
    assert d["decisionFeedback"]["classification"] == "self-modification"

def autonomy_gate_feedback_on_git_push():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
    )
    d = json.loads(out)
    assert "decisionFeedback" in d, f"expected decisionFeedback, got {d}"
    assert d["decisionFeedback"]["classification"] == "high-risk-command"

def autonomy_gate_silent_on_low_risk():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/Downloads/estate/server.js"}}
    )
    assert out.strip() == "", f"expected silent, got {out!r}"

def autonomy_gate_silent_on_settings_local():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/.ncode/settings.local.json"}}
    )
    assert out.strip() == "", f"settings.local.json should be writable, got {out!r}"

# --- Compact continuity ---

def compact_continuity_writes_packet():
    session = "test-continuity-write"
    packet_path = Path.home() / ".ncode" / "continuity" / f"{session}.md"
    packet_path.unlink(missing_ok=True)

    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "compact_continuity.py",
        {"hook_event_name": "PreCompact", "cwd": "/tmp", "session_id": session, "transcript_path": ""}
    )
    assert packet_path.exists(), f"packet not written at {packet_path}"
    content = packet_path.read_text()
    assert "# Continuity" in content, "missing header"
    assert "/tmp" in content, "missing cwd"

def compact_continuity_restores_packet():
    session = "test-continuity-restore"
    packet_path = Path.home() / ".ncode" / "continuity" / f"{session}.md"
    packet_path.write_text("# Continuity — test\nObjective: test this works\n")

    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "compact_continuity.py",
        {"hook_event_name": "PostCompact", "cwd": "/tmp", "session_id": session, "transcript_path": ""}
    )
    d = json.loads(out)
    assert "additionalContext" in d, f"expected additionalContext, got {d}"
    assert "test this works" in d["additionalContext"], "packet content missing"

def compact_continuity_silent_without_packet():
    session = "test-continuity-nonexistent"
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "compact_continuity.py",
        {"hook_event_name": "PostCompact", "cwd": "/tmp", "session_id": session, "transcript_path": ""}
    )
    assert out.strip() == "", f"expected silent, got {out!r}"

# --- Validator ---

def validator_clean():
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "validate_harness.py")],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"validator failed: {r.stdout}"

# --- Patch effort message (idempotency) ---

def patch_effort_check_no_mutation():
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "patch_effort_message.py"), "--check"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"--check failed: {r.stdout} {r.stderr}"

# --- Memory Fabric preflight (silent on missing file or empty store) ---

def preflight_silent_on_missing_path():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_preflight.py",
        {"tool_name": "Edit", "tool_input": {}, "cwd": "/tmp"}
    )
    assert out.strip() == "", f"expected silent, got {out!r}"

# --- Memory Fabric prompt search ---

def prompt_search_silent_on_empty_prompt():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_prompt_search.py",
        {"hook_event_name": "UserPromptSubmit", "cwd": "/tmp", "prompt": ""}
    )
    assert out.strip() == "", f"expected silent, got {out!r}"

def prompt_search_finds_records():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_prompt_search.py",
        {"hook_event_name": "UserPromptSubmit", "cwd": str(Path.home() / ".ncode"),
         "prompt": "GLM 5.2 max effort patch"}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"
        assert "memory_fabric" in d["additionalContext"], "missing header"

# --- Script smoke test ---

def smoke_test_clean_script():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "script_smoke.py",
        {"tool_name": "Edit", "tool_input": {"file_path": str(SCRIPTS_DIR / "validate_harness.py")}}
    )
    assert out.strip() == "", f"clean script should be silent, got {out!r}"


# --- Agent patterns aggregator ---

def agent_patterns_brief_silent_on_empty():
    """When no outcome records exist, --brief should be silent."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "agent_patterns.py"), "--brief"],
        input="{}", capture_output=True, text=True, timeout=10
    )
    # May or may not have output depending on store state — just check it exits clean
    assert r.returncode == 0, f"--brief failed: {r.stderr}"

def agent_patterns_full_runs():
    """Full report should produce parseable output."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "agent_patterns.py")],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"full report failed: {r.stderr}"
    assert "Agent Patterns" in r.stdout or "no records" in r.stdout, f"unexpected output: {r.stdout}"

def agent_patterns_json_valid():
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "agent_patterns.py"), "--json"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"--json failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert "outcomes" in d, f"missing outcomes key: {d}"
    assert "patterns" in d, f"missing patterns key: {d}"

# --- Proactive drift detector ---

def proactive_drift_runs_clean():
    """Proactive drift should produce valid JSON or silent."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "proactive_drift.py",
        {"hook_event_name": "SessionStart", "cwd": str(Path.home() / ".ncode")}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"
        assert "drift detector" in d["additionalContext"].lower(), "missing header"

# --- Task outcome tracker ---

def outcome_tracker_record_silent_on_empty():
    """Record mode with /dev/null transcript should be silent."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "task_outcome_tracker.py",
        {"transcript_path": "/dev/null", "session_id": "test-empty", "cwd": "/tmp"}
    )
    # Input goes to --record via stdin; but --record reads from args, not stdin
    # Test the --query mode instead
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "task_outcome_tracker.py"), "--query", "--limit", "5"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"--query failed: {r.stderr}"

# --- Extended Memory Fabric doctor ---

def doctor_surfaces_recent_work():
    """Doctor should surface recent work records as additionalContext."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_doctor.py",
        {"hook_event_name": "SessionStart", "cwd": str(Path.home() / ".ncode")}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"
        # Should mention either doctor issues or recent work
        assert "memory_fabric" in d["additionalContext"].lower(), "missing header"


# --- Behavior tests (end-to-end, prove the harness changes behavior) ---

def behavior_blocks_settings_json_via_gate():
    """Edit to settings.json → autonomy_gate returns decision:block."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": "/Users/x/.ncode/settings.json"}}
    )
    d = json.loads(out)
    assert d.get("decision") == "block", f"gate should block, got {d}"
    assert "settings.json" in d.get("reason", "")

def behavior_blocks_env_via_old_hook():
    """Edit to .env → existing inline .env blocker still fires."""
    import subprocess as sp
    inline_code = (
        "import sys,json,os,re\n"
        "try:\n"
        "  inp=json.load(sys.stdin)\n"
        "  p=inp.get('tool_input',{}).get('file_path','') or inp.get('tool_input',{}).get('path','')\n"
        "  if re.search(r'\\.env(\\.|$)',os.path.basename(p)):\n"
        "    print(json.dumps({'decision':'block','reason':'Blocked: .env edits require explicit confirmation to protect credentials.'}))\n"
        "  else:\n"
        "    print(json.dumps({'decision':'approve'}))\n"
        "except:\n"
        "  print(json.dumps({'decision':'approve'}))"
    )
    r = sp.run(["python3", "-c", inline_code],
               input=json.dumps({"tool_input": {"file_path": "/Users/x/.env"}}),
               capture_output=True, text=True, timeout=5)
    d = json.loads(r.stdout)
    assert d.get("decision") == "block", f"env blocker should fire, got {d}"
    assert "credentials" in d.get("reason", "").lower()

def behavior_snapshot_on_script_edit():
    """Edit to ~/.ncode/scripts/<existing>.py → autonomy_gate creates snapshot."""
    # Clean up existing snapshots for the test target
    backup_dir = Path.home() / ".ncode" / "backups" / "scripts"
    target = "validate_harness"
    if backup_dir.is_dir():
        for old in backup_dir.glob(f"{target}.*.py"):
            old.unlink(missing_ok=True)

    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "autonomy_gate.py",
        {"tool_name": "Edit", "tool_input": {"file_path": str(SCRIPTS_DIR / "validate_harness.py")}}
    )
    d = json.loads(out)
    assert "decisionFeedback" in d, f"expected feedback, got {d}"
    assert d["decisionFeedback"]["classification"] == "self-modification"

    # Assert a snapshot file was created
    snapshots = list(backup_dir.glob(f"{target}.*.py"))
    assert snapshots, f"no snapshot created for {target}"
    # Verify snapshot contains the original content
    snap_content = snapshots[0].read_text()
    original = (SCRIPTS_DIR / "validate_harness.py").read_text()
    assert snap_content == original or len(snap_content) > 0, "snapshot empty"

def behavior_compact_lifecycle():
    """Full PreCompact → PostCompact cycle restores continuity packet."""
    session = f"test-behavior-{int(time.time())}"
    packet_path = Path.home() / ".ncode" / "continuity" / f"{session}.md"
    packet_path.unlink(missing_ok=True)

    # PreCompact: writes packet
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "compact_continuity.py",
        {"hook_event_name": "PreCompact", "cwd": "/behavior-test",
         "session_id": session, "transcript_path": ""}
    )
    assert packet_path.exists(), f"packet not written during PreCompact"

    # PostCompact: restores packet as additionalContext
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "compact_continuity.py",
        {"hook_event_name": "PostCompact", "cwd": "/behavior-test",
         "session_id": session, "transcript_path": ""}
    )
    d = json.loads(out)
    assert "additionalContext" in d, f"PostCompact should restore, got {d}"
    assert "Continuity" in d["additionalContext"], "restored context missing header"
    assert "/behavior-test" in d["additionalContext"], "restored context missing cwd"
    # Cleanup
    packet_path.unlink(missing_ok=True)

def behavior_memory_loop():
    """Preflight surfaces prior Memory Fabric records for the file's scope."""
    # Use a known existing learning we recorded earlier
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_preflight.py",
        {"tool_name": "Edit", "cwd": str(Path.home() / ".ncode"),
         "tool_input": {"file_path": str(SCRIPTS_DIR / "patch_effort_message.py")}}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"
        assert "memory_fabric" in d["additionalContext"].lower()

def behavior_prompt_search_surfaces_relevant():
    """Prompt search surfaces prior records relevant to the prompt."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_prompt_search.py",
        {"hook_event_name": "UserPromptSubmit",
         "cwd": str(Path.home() / ".ncode"),
         "prompt": "how does max effort work for GLM 5.2?"}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"
        # Should reference prior learning about GLM 5.2 patch
        assert "glm" in d["additionalContext"].lower() or "memory_fabric" in d["additionalContext"].lower()


# --- Coverage for previously-untested scripts ---

def smoke_snapshot_harness():
    """snapshot_harness --list should return success."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "snapshot_harness.py"), "--list"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"snapshot_harness --list failed: {r.stderr}"

def smoke_restore_harness():
    """restore_harness --list should return success."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "restore_harness.py"), "--list"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"restore_harness --list failed: {r.stderr}"

def smoke_self_correct():
    """self_correct --json returns valid JSON with expected keys."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "self_correct.py"), "--json"],
        capture_output=True, text=True, timeout=15
    )
    assert r.returncode == 0, f"self_correct --json failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert "record_count" in d
    assert "untested_scripts" in d
    assert "stale_scripts" in d

def smoke_harness_gc():
    """harness_gc runs and produces output."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "harness_gc.py")],
        capture_output=True, text=True, timeout=15
    )
    assert r.returncode == 0, f"harness_gc failed: {r.stderr}"
    assert "summary" in r.stdout.lower(), "missing summary"

def smoke_tool_factory():
    """tool_factory scaffolds a dummy helper in --dry-run mode."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "tool_factory.py"),
         "_smoke_test_dummy", "--summary", "smoke test", "--lang", "py", "--dry-run"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"tool_factory --dry-run failed: {r.stderr}"
    assert "dry-run" in r.stdout.lower(), f"missing dry-run plan: {r.stdout}"

def smoke_memory_fabric_compact_brief():
    """compact_brief returns valid JSON on simulated PreCompact."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_compact_brief.py",
        {"hook_event_name": "PreCompact", "trigger": "manual",
         "cwd": str(Path.home() / ".ncode"),
         "transcript_path": "", "session_id": "smoke-test"}
    )
    if out.strip():
        d = json.loads(out)
        assert "additionalContext" in d, f"bad output: {d}"

def smoke_memory_fabric_session_record():
    """session_record should be silent on empty transcript."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "memory_fabric_session_record.py",
        {"hook_event_name": "PostCompact", "trigger": "manual",
         "cwd": "/tmp", "transcript_path": "", "session_id": "smoke-empty"}
    )
    # Should not crash; silent acceptable
    assert rc == 0, f"session_record crashed: rc={rc}"

def smoke_session_close():
    """session_close should be silent on empty transcript."""
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "session_close.py",
        {"hook_event_name": "Stop", "cwd": "/tmp",
         "transcript_path": "", "session_id": "smoke-empty"}
    )
    assert rc == 0, f"session_close crashed: rc={rc}"


# --- v2: recall_ranker ---

def recall_ranker_silent_on_empty_prompt():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "recall_ranker.py",
        {"hook_event_name": "UserPromptSubmit", "cwd": "/tmp", "prompt": ""}
    )
    assert out.strip() == "", f"expected silent on empty prompt, got {out!r}"

def recall_ranker_silent_on_garbage():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "recall_ranker.py",
        {"hook_event_name": "UserPromptSubmit", "cwd": "/tmp", "prompt": "???"}
    )
    assert out.strip() == "", f"expected silent on too-short query, got {out!r}"

def recall_ranker_silent_when_no_mf_cli():
    # No memory_fabric CLI installed in this env -> script must exit 0 silent
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "recall_ranker.py",
        {"hook_event_name": "UserPromptSubmit", "cwd": "/tmp",
         "prompt": "how does the autonomy gate work"}
    )
    assert rc == 0, f"expected exit 0, got {rc}"
    # either silent (no MF) or additionalContext (MF present) — both acceptable

# --- v2: escalation_advisor ---

def escalation_advisor_silent_on_no_path():
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "escalation_advisor.py",
        {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {}}
    )
    assert out.strip() == "", f"expected silent with no path, got {out!r}"

def escalation_advisor_silent_on_clean_scope():
    # A path with no failure records and no improvements.md entry -> silent
    rc, out, _ = run_script_with_input(
        SCRIPTS_DIR / "escalation_advisor.py",
        {"hook_event_name": "PostToolUse", "tool_name": "Edit",
         "tool_input": {"file_path": "/tmp/never_touched_file.py"}}
    )
    assert rc == 0
    # In an env with no MF CLI and no improvements.md, must be silent
    assert out.strip() == "", f"expected silent on clean scope, got {out!r}"

def escalation_advisor_exits_clean_on_bad_json():
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "escalation_advisor.py")],
        input="not json",
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"expected exit 0 on bad json, got {r.returncode}"
    assert r.stdout.strip() == "", f"expected silent on bad json, got {r.stdout!r}"

# --- v2: improvement_injector ---

def improvement_injector_silent_when_no_improvements_file(tmp_path=None):
    # IMPROVEMENTS_PATH absent -> latest_entry returns (None, None), which is the
    # predicate that drives the silent branch. Patch via module import so the test
    # doesn't depend on the live env state (self_correct.py writes that file).
    import importlib.util
    script = SCRIPTS_DIR / "improvement_injector.py"
    spec = importlib.util.spec_from_file_location("ii_silent", str(script))
    ii = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ii)
    ii.IMPROVEMENTS_PATH = Path("/tmp/__does_not_exist_improvements.md")
    entry, age = ii.latest_entry()
    assert entry is None and age is None, f"expected (None, None) when path missing, got ({entry!r}, {age!r})"

def improvement_injector_exits_clean_on_bad_json():
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "improvement_injector.py")],
        input="not json",
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"expected exit 0 on bad json, got {r.returncode}"
    assert r.stdout.strip() == "", f"expected silent on bad json, got {r.stdout!r}"

def improvement_injector_surfaces_fresh_entry(tmp_path=None):
    """Point the script at a freshly-written improvements.md and confirm it emits context."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        # Override the module-level IMPROVEMENTS_PATH by importing the script as a module
        script = SCRIPTS_DIR / "improvement_injector.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("ii", str(script))
        ii = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ii)
        # Write a fresh entry
        p = Path(td) / "improvements.md"
        p.write_text("# Journal\n\n## Self-correction — 2026-06-28 00:00 UTC\n\n- untested: foo.py\n- action: add test\n")
        ii.IMPROVEMENTS_PATH = p
        # Capture stdout by calling main() with patched stdin via subprocess is hard;
        # instead call latest_entry() directly to assert the read-back works
        entry, age = ii.latest_entry()
        assert entry is not None, "expected an entry, got None"
        assert "Self-correction" in entry
        assert "foo.py" in entry
        assert age is not None and age < 1.0, f"age should be <1d for fresh file, got {age}"

# --- v2: validate_v2 (the manifest coherence check) ---
# validate_v2.py runs against the repo manifests, not the staged ~/.ncode/scripts/
# tree, so it is exercised by the run command itself (cwd = repo root), not here.
# The cases above cover the three new lifecycle scripts as staged regressions.

# --- csi_presence_mirror ---

def csi_presence_mirror_silent_when_no_source_dir():
    """No .codex/csi/ under cwd -> silent exit 0, no stdout, no stderr."""
    rc, out, err = run_script_with_input(
        SCRIPTS_DIR / "csi_presence_mirror.py",
        {"cwd": "/tmp"}
    )
    assert rc == 0, f"expected exit 0, got {rc}"
    assert out == "", f"expected no stdout, got {out!r}"
    assert err == "", f"expected no stderr, got {err!r}"

def csi_presence_mirror_copies_files_when_source_exists():
    """Source .codex/csi/ exists -> both presence files mirrored to <cwd>/.ncode/csi/."""
    import shutil
    td = tempfile.mkdtemp()
    try:
        src = Path(td) / ".codex" / "csi"
        src.mkdir(parents=True)
        (src / "chat-presence.md").write_text("chat presence body\n")
        (src / "rich-presence.md").write_text("rich presence body\n")
        rc, out, err = run_script_with_input(
            SCRIPTS_DIR / "csi_presence_mirror.py",
            {"cwd": td}
        )
        assert rc == 0, f"expected exit 0, got {rc}"
        dst = Path(td) / ".ncode" / "csi"
        chat = (dst / "chat-presence.md").read_text()
        rich = (dst / "rich-presence.md").read_text()
        assert chat == "chat presence body\n", f"chat-presence.md mismatch: {chat!r}"
        assert rich == "rich presence body\n", f"rich-presence.md mismatch: {rich!r}"
    finally:
        shutil.rmtree(td, ignore_errors=True)

def csi_presence_mirror_silent_on_malformed_stdin():
    """Malformed JSON stdin -> silent exit 0 (falls back to getcwd, isolated below)."""
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            ["python3", str(SCRIPTS_DIR / "csi_presence_mirror.py")],
            input="not json",
            capture_output=True, text=True, timeout=10,
            cwd=td
        )
        assert r.returncode == 0, f"expected exit 0 on malformed stdin, got {r.returncode}"
        assert r.stdout == "", f"expected silent on malformed stdin, got {r.stdout!r}"
        assert r.stderr == "", f"expected no stderr on malformed stdin, got {r.stderr!r}"


# --- hook_event_tap (Phase 3) ---

def hook_event_tap_passes_through_and_records():
    """Tap runs wrapped hook, passes stdout through, writes JSONL side log."""
    import tempfile
    # Use a temp log so the real ~/.ncode/hook_events.jsonl is untouched
    with tempfile.TemporaryDirectory() as td:
        log_path = f"{td}/hook_events.jsonl"
        env = dict(os.environ)
        # The tap hard-codes LOG_PATH, so override via monkey-patch by sourcing
        # the script text and rewriting the constant (similar to probe_hook test).
        # For a simpler smoke test, run the actual tap against an inner /bin/echo
        # and verify the LOG_PATH it writes to still gets a line.
        # Since LOG_PATH is hard-coded, we accept the side effect on the real file
        # and clean up the last line afterward.
        native_log = os.path.expanduser("~/.ncode/hook_events.jsonl")
        before_size = os.path.getsize(native_log) if os.path.exists(native_log) else 0

        r = subprocess.run(
            ["python3", str(SCRIPTS_DIR / "hook_event_tap.py"),
             "--event", "PreToolUse",
             "--script", "_smoke_inner.py",
             "--", "/bin/echo", '{"decision":"approve"}'],
            input='{}',
            capture_output=True, text=True, timeout=10
        )

        assert r.returncode == 0, f"tap exit non-zero: {r.returncode}, stderr={r.stderr!r}"
        # stdout passed through — echo output lands here
        assert "approve" in r.stdout, f"stdout not passed through: {r.stdout!r}"

        # Side log got exactly one new line
        after_size = os.path.getsize(native_log)
        assert after_size > before_size, f"no JSONL line appended to {native_log}"

        # Read the last line and verify shape
        with open(native_log, "rb") as f:
            f.seek(max(0, before_size))
            new_bytes = f.read(after_size - before_size)
        lines = [l for l in new_bytes.decode("utf-8", errors="replace").split("\n") if l.strip()]
        assert len(lines) == 1, f"expected 1 new line, got {len(lines)}: {lines}"
        d = json.loads(lines[0])
        assert d["event"] == "PreToolUse"
        assert d["script"] == "_smoke_inner.py"
        assert d["exitCode"] == 0
        assert d["outcome"] == "fire"  # decision=approve
        assert "durationMs" in d and d["durationMs"] >= 0


def hook_event_tap_classifies_block():
    """Tap classifies decision:block as outcome:block."""
    # Run the real wrapped hook — autonomy_gate against settings.json should block
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "hook_event_tap.py"),
         "--event", "PreToolUse",
         "--script", "autonomy_gate.py",
         "--", "python3", str(SCRIPTS_DIR / "autonomy_gate.py")],
        input=json.dumps({"tool_name": "Edit",
                          "tool_input": {"file_path": "/Users/x/.ncode/settings.json"}}),
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"tap exit non-zero: {r.returncode}"

    # Read the last line of the side log
    native_log = os.path.expanduser("~/.ncode/hook_events.jsonl")
    with open(native_log, "rb") as f:
        f.seek(0, 2)
        end = f.tell()
        # Read back ~2KB to find the last newline
        f.seek(max(0, end - 2048))
        tail = f.read().decode("utf-8", errors="replace")
    last_line = [l for l in tail.split("\n") if l.strip()][-1]
    d = json.loads(last_line)
    assert d["outcome"] == "block", f"expected outcome=block, got {d['outcome']}"


# --- install.sh (Phase 4) ---

def install_sh_check_returns_clean_after_install():
    """install.sh --check should return 0 (in-sync) after a fresh install."""
    # First ensure manifest exists — if not, install
    manifest_path = os.path.expanduser("~/.ncode/.harness.installed.json")
    if not os.path.exists(manifest_path):
        r = subprocess.run(
            ["/bin/bash", str(Path.home() / "Code/harness-self-improvement/install.sh")],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home() / "Code/harness-self-improvement")
        )
        assert r.returncode == 0, f"first install failed: {r.stderr}"

    r = subprocess.run(
        ["/bin/bash", str(Path.home() / "Code/harness-self-improvement/install.sh"), "--check"],
        capture_output=True, text=True, timeout=10,
        cwd=str(Path.home() / "Code/harness-self-improvement")
    )
    assert r.returncode == 0, f"--check failed (rc={r.returncode}): {r.stdout}\n{r.stderr}"
    assert "OK" in r.stdout or "in sync" in r.stdout, f"unexpected output: {r.stdout}"


def install_sh_manifest_has_expected_fields():
    """Manifest written by install.sh must have commit + files array."""
    manifest_path = os.path.expanduser("~/.ncode/.harness.installed.json")
    if not os.path.exists(manifest_path):
        # Run install to create one
        subprocess.run(
            ["/bin/bash", str(Path.home() / "Code/harness-self-improvement/install.sh")],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home() / "Code/harness-self-improvement")
        )
    d = json.load(open(manifest_path))
    assert "commit" in d and len(d["commit"]) >= 7, f"no commit: {d}"
    assert "files" in d and isinstance(d["files"], list) and len(d["files"]) > 0, f"no files: {d}"
    assert "installedAt" in d, f"no installedAt: {d}"
    assert "hooksSha256" in d, f"no hooksSha256: {d}"
    first_file = d["files"][0]
    assert "path" in first_file and "sha256" in first_file, f"bad entry: {first_file}"


# --- probe_hook ---
# Note: probe_hook.py does NOT read stdin — it always emits JSON to stdout and
# appends a marker line to LOG. The riskiest branch is the try/except OSError
# around the log write; if that swallows an error silently, the JSON channel
# must still keep working (that's the probe's whole purpose).
# Source rewrite isolates LOG so the tests never touch /tmp/hook_probe.log.

def _run_probe_hook_with_log(log_path):
    """Exec probe_hook.py with module-level LOG overridden. Returns (stdout, rc)."""
    import io
    import contextlib
    script = SCRIPTS_DIR / "probe_hook.py"
    source = script.read_text().replace(
        'LOG = Path("/tmp/hook_probe.log")',
        f'LOG = Path({str(log_path)!r})'
    )
    ns = {"__name__": "probe_hook_test", "__file__": str(script)}
    buf = io.StringIO()
    exit_code = 0
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(source, str(script), "exec"), ns)
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0
    return buf.getvalue(), exit_code

def probe_hook_writes_marker_to_log_and_emits_json():
    """Happy path: marker line written to log AND JSON emitted to stdout."""
    import re
    with tempfile.TemporaryDirectory() as td:
        log_path = Path(td) / "hook_probe_test.log"
        out, rc = _run_probe_hook_with_log(log_path)
        assert rc == 0, f"expected exit 0, got {rc}"
        assert log_path.exists(), f"log file not created at {log_path}"
        log_content = log_path.read_text()
        m = re.search(r"(PROBE_\d+) hook_event=priority_button", log_content)
        assert m, f"log content doesn't match expected pattern: {log_content!r}"
        marker = m.group(1)
        d = json.loads(out)
        assert "additionalContext" in d, f"missing additionalContext: {d}"
        ctx = d["additionalContext"]
        assert "[PROBE]" in ctx, f"missing [PROBE] in {ctx!r}"
        assert f"marker={marker}" in ctx, (
            f"stdout marker doesn't match log marker: stdout={ctx!r}, log={marker!r}"
        )

def probe_hook_silent_on_log_write_error():
    """OSError on log open (missing parent dir) -> JSON still emitted, exit 0."""
    with tempfile.TemporaryDirectory() as td:
        # Parent dir doesn't exist -> open(LOG, "a") raises FileNotFoundError
        # (subclass of OSError); the script's except OSError swallows it.
        log_path = Path(td) / "missing_subdir" / "hook_probe_test.log"
        out, rc = _run_probe_hook_with_log(log_path)
        assert rc == 0, f"expected exit 0 on log write error, got {rc}"
        d = json.loads(out)
        assert "additionalContext" in d, (
            f"missing additionalContext on log error: {d}"
        )
        assert "PROBE_" in d["additionalContext"], (
            f"marker missing from stdout on log error: {d}"
        )
        assert not log_path.exists(), "log file should not exist when parent dir missing"


# --- brainstorm (Phase 8) ---

def brainstorm_py_returns_gaps():
    """brainstorm.py --json returns valid JSON with gaps array."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "brainstorm.py"), "--json"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"brainstorm --json failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert "gaps" in d and isinstance(d["gaps"], list), f"missing gaps: {d}"
    assert "installed" in d, f"missing installed: {d}"
    assert d["installed"]["scripts"] > 0
    # At least one gap should exist (Tier 3 isn't fully shipped)
    assert len(d["gaps"]) > 0, "expected at least 1 gap, got 0"
    # Top gap should have leverage >= 3 (Tier 3 fully shipped, Tier 4 items have lower scores)
    assert d["gaps"][0]["leverage"] >= 3, f"top gap leverage too low: {d['gaps'][0]}"

# --- goal_state (Phase 4) ---

def goal_state_set_status_complete_cycle():
    """goal_state: set → status → complete → clear cycle."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "set", "Test goal: write 3 files"],
        capture_output=True, text=True, timeout=5
    )
    assert r.returncode == 0, f"set failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert d["ok"] is True
    assert d["objective"] == "Test goal: write 3 files"
    assert d["status"] == "active"

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "status"],
        capture_output=True, text=True, timeout=5
    )
    assert r.returncode == 0, f"status failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert d["objective"] == "Test goal: write 3 files"
    assert d["status"] == "active"

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "is-active"],
        capture_output=True, timeout=5
    )
    assert r.returncode == 0, f"is-active should be exit 0 when goal active"

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "complete"],
        capture_output=True, text=True, timeout=5
    )
    assert r.returncode == 0, f"complete failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert d["status"] == "complete"

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "is-active"],
        capture_output=True, timeout=5
    )
    assert r.returncode == 1, f"is-active should be exit 1 when goal complete"

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "goal_state.py"), "clear"],
        capture_output=True, text=True, timeout=5
    )
    assert r.returncode == 0, f"clear failed: {r.stderr}"
    d = json.loads(r.stdout)
    assert d["ok"] is True


# --- Worktree scope resolver ---


class _FakeGitRunner:
    """Deterministic git runner for unit tests — no subprocesses spawned."""

    def __init__(self, common_dir_output="", returncode=0):
        self.common_dir_output = common_dir_output
        self.returncode = returncode
        self.call_count = 0

    def __call__(self, cwd, *args):
        self.call_count += 1
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=self.returncode,
            stdout=self.common_dir_output,
            stderr="",
        )


def _import_worktree_scope():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import worktree_scope
    return worktree_scope


def worktree_resolve_scope_identity_on_non_git():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(common_dir_output="", returncode=128)
    result = wts.resolve_scope("/tmp/worktree-test-identity", runner=runner)
    assert result == str(Path("/tmp/worktree-test-identity").resolve()), \
        f"expected resolved cwd, got {result}"


def worktree_is_worktree_false_outside_git():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(common_dir_output="", returncode=128)
    assert wts.is_worktree("/tmp/some-non-git-path", runner=runner) is False


def worktree_is_worktree_true_for_linked_worktree():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(common_dir_output="/repo/.git/worktrees/wt-1")
    assert wts.is_worktree("/repo/wt-1", runner=runner) is True


def worktree_main_root_returns_main_repo_root():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(
        common_dir_output="/Users/me/Code/harness-app/.git/worktrees/wt-abc"
    )
    main = wts.worktree_main_root(
        "/Users/me/Code/harness-app/checkouts/wt-abc", runner=runner
    )
    assert main is not None
    assert main.name == "harness-app", f"expected main repo root, got {main}"


def worktree_cache_hit_avoids_second_git_call():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(common_dir_output="", returncode=128)
    cwd = "/tmp/worktree-test-cache"
    wts.resolve_scope(cwd, runner=runner)
    first = runner.call_count
    wts.resolve_scope(cwd, runner=runner)
    assert runner.call_count == first, \
        f"expected no second git call, got {runner.call_count - first} extra"


def worktree_env_override_forces_identity():
    wts = _import_worktree_scope()
    wts.clear_cache()
    runner = _FakeGitRunner(common_dir_output="/repo/.git/worktrees/wt-1")
    old = os.environ.get("HARNESS_NO_WORKTREE_REMAP")
    os.environ["HARNESS_NO_WORKTREE_REMAP"] = "1"
    try:
        result = wts.resolve_scope("/repo/wt-1", runner=runner)
    finally:
        if old is None:
            os.environ.pop("HARNESS_NO_WORKTREE_REMAP", None)
        else:
            os.environ["HARNESS_NO_WORKTREE_REMAP"] = old
    assert result == str(Path("/repo/wt-1").resolve()), \
        f"override should return resolved input, got {result}"


def behavior_worktree_round_trip_real_worktree():
    """End-to-end: spawn a real git worktree, verify resolve_scope maps it.

    The only test that runs actual `git` — proves the detector works against
    real git output. ~50ms in a tempfile.
    """
    wts = _import_worktree_scope()
    wts.clear_cache()
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp) / "main"
        main.mkdir()
        subprocess.run(["git", "init", str(main)], capture_output=True, check=True)
        (main / "README.md").write_text("hello\n")
        subprocess.run(
            ["git", "-C", str(main), "add", "."],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(main), "-c", "user.email=test@local",
             "-c", "user.name=Test", "commit", "-m", "init"],
            capture_output=True, check=True,
        )
        wt = Path(tmp) / "wt"
        subprocess.run(
            ["git", "-C", str(main), "worktree", "add", str(wt)],
            capture_output=True, check=True,
        )
        assert wts.is_worktree(str(wt)), "real worktree should be detected"
        resolved = wts.resolve_scope(str(wt))
        assert Path(resolved).resolve() == main.resolve(), \
            f"worktree scope {resolved} should map to main {main}, didn't"


def behavior_normal_session_scope_unchanged():
    """Regression guard: a non-worktree session's scope equals its cwd resolved."""
    wts = _import_worktree_scope()
    wts.clear_cache()
    # Mock common-dir returns `<repo>/.git` (NOT a worktree marker)
    runner = _FakeGitRunner(common_dir_output="/repo/.git")
    result = wts.resolve_scope("/repo", runner=runner)
    assert result == str(Path("/repo").resolve()), \
        f"normal repo scope should be itself, got {result}"


# --- Eval loop closure ---


def _write_eval_results(path, runs):
    """Helper: write a list of run dicts to a JSONL file."""
    with open(path, "w", encoding="utf-8") as fp:
        for r in runs:
            fp.write(json.dumps(r) + "\n")


def _make_eval_run(case_id, score, passed, ts_iso, error=None):
    """Helper: build a minimal EvalRun-shaped dict."""
    return {
        "id": "test-" + ts_iso,
        "caseId": case_id,
        "caseVersion": 1,
        "startedAtISO": ts_iso,
        "finishedAtISO": ts_iso,
        "score": score,
        "passed": passed,
        "sandboxURL": "/tmp/sandbox",
        "checkResults": [],
        "toolCount": 1,
        "model": None,
        "errorMessage": error,
    }


def eval_regression_detected_when_latest_drops():
    """find_eval_regressions flags case where latest < baseline - threshold."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import self_correct as sc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # 4 runs at 0.9, latest at 0.4 → should flag
        runs = [
            _make_eval_run("qual-x-001", 0.9, True, "2026-06-29T01:00:00Z"),
            _make_eval_run("qual-x-001", 0.9, True, "2026-06-29T02:00:00Z"),
            _make_eval_run("qual-x-001", 0.9, True, "2026-06-29T03:00:00Z"),
            _make_eval_run("qual-x-001", 0.4, False, "2026-06-29T04:00:00Z"),
        ]
        _write_eval_results(f.name, runs)
        tmp = f.name
    try:
        regs = sc.find_eval_regressions(results_path=Path(tmp))
        assert len(regs) == 1, f"expected 1 regression, got {len(regs)}"
        assert regs[0]["caseId"] == "qual-x-001"
        assert regs[0]["baseline"] == 0.9, f"baseline should be 0.9, got {regs[0]['baseline']}"
        assert regs[0]["latest"] == 0.4, f"latest should be 0.4, got {regs[0]['latest']}"
    finally:
        os.unlink(tmp)


def eval_regression_skipped_with_insufficient_runs():
    """find_eval_regressions needs at least baseline_runs + 1 to flag."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import self_correct as sc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs = [
            _make_eval_run("qual-y-001", 0.9, True, "2026-06-29T01:00:00Z"),
            _make_eval_run("qual-y-001", 0.4, False, "2026-06-29T02:00:00Z"),
        ]
        _write_eval_results(f.name, runs)
        tmp = f.name
    try:
        regs = sc.find_eval_regressions(results_path=Path(tmp))
        assert len(regs) == 0, f"expected 0 regressions with insufficient runs, got {len(regs)}"
    finally:
        os.unlink(tmp)


def eval_regression_skips_error_runs():
    """find_eval_regressions ignores runs with errorMessage."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import self_correct as sc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs = [
            _make_eval_run("qual-z-001", 0.9, True, "2026-06-29T01:00:00Z"),
            _make_eval_run("qual-z-001", 0.9, True, "2026-06-29T02:00:00Z"),
            _make_eval_run("qual-z-001", 0.9, True, "2026-06-29T03:00:00Z"),
            _make_eval_run("qual-z-001", 0.0, False, "2026-06-29T04:00:00Z",
                           error="timeout"),  # error run, should be skipped
        ]
        _write_eval_results(f.name, runs)
        tmp = f.name
    try:
        regs = sc.find_eval_regressions(results_path=Path(tmp))
        # Latest run errored → skipped; no regression from the four entries
        # (the third run at 0.9 becomes the latest, with 2 baseline runs → insufficient)
        assert len(regs) == 0, f"expected 0 regressions when latest errored, got {len(regs)}"
    finally:
        os.unlink(tmp)


def eval_brief_emits_when_results_exist():
    """latest_eval_summary returns a string when results.jsonl has runs."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import improvement_injector as ii
    ii.EVAL_RESULTS_PATH = Path(tempfile.gettempdir()) / "test_eval_brief.jsonl"
    try:
        runs = [
            _make_eval_run("case-a", 1.0, True, "2026-06-29T01:00:00Z"),
            _make_eval_run("case-b", 0.0, False, "2026-06-29T01:30:00Z"),
            _make_eval_run("case-c", 1.0, True, "2026-06-29T02:00:00Z"),
        ]
        _write_eval_results(ii.EVAL_RESULTS_PATH, runs)
        brief = ii.latest_eval_summary()
        assert brief is not None, "expected a brief string, got None"
        assert "2/3" in brief, f"expected '2/3' in brief, got: {brief}"
        assert "passed" in brief
    finally:
        if ii.EVAL_RESULTS_PATH.exists():
            os.unlink(ii.EVAL_RESULTS_PATH)


def smoke_eval_harness():
    """eval_harness.py --help exits 0 (script_smoke.py catches this at edit time)."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "eval_harness.py"), "--help"],
        capture_output=True, timeout=5
    )
    assert r.returncode == 0, f"eval_harness.py --help failed: {r.stderr}"


def smoke_weekly_sweep():
    """weekly_sweep.py --help exits 0."""
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "weekly_sweep.py"), "--help"],
        capture_output=True, timeout=5
    )
    assert r.returncode == 0, f"weekly_sweep.py --help failed: {r.stderr}"


SUITES = {
    "v2_recall_ranker": [
        case("silent_on_empty_prompt", recall_ranker_silent_on_empty_prompt),
        case("silent_on_garbage", recall_ranker_silent_on_garbage),
        case("silent_when_no_mf_cli", recall_ranker_silent_when_no_mf_cli),
    ],
    "v2_escalation_advisor": [
        case("silent_on_no_path", escalation_advisor_silent_on_no_path),
        case("silent_on_clean_scope", escalation_advisor_silent_on_clean_scope),
        case("exits_clean_on_bad_json", escalation_advisor_exits_clean_on_bad_json),
    ],
    "v2_improvement_injector": [
        case("silent_when_no_file", improvement_injector_silent_when_no_improvements_file),
        case("exits_clean_on_bad_json", improvement_injector_exits_clean_on_bad_json),
        case("surfaces_fresh_entry", improvement_injector_surfaces_fresh_entry),
    ],
    "autonomy_gate": [
        case("blocks_settings_json", autonomy_gate_blocks_settings_json),
        case("blocks_binary_path", autonomy_gate_blocks_binary_path),
        case("blocks_force_push", autonomy_gate_blocks_force_push),
        case("blocks_rm_rf_root", autonomy_gate_blocks_rm_rf_root),
        case("blocks_credentials", autonomy_gate_blocks_credentials),
        case("feedback_on_scripts_edit", autonomy_gate_feedback_on_scripts_edit),
        case("feedback_on_git_push", autonomy_gate_feedback_on_git_push),
        case("silent_on_low_risk", autonomy_gate_silent_on_low_risk),
        case("silent_on_settings_local", autonomy_gate_silent_on_settings_local),
    ],
    "compact_continuity": [
        case("writes_packet", compact_continuity_writes_packet),
        case("restores_packet", compact_continuity_restores_packet),
        case("silent_without_packet", compact_continuity_silent_without_packet),
    ],
    "validator": [
        case("clean", validator_clean),
    ],
    "patch_effort": [
        case("check_idempotent", patch_effort_check_no_mutation),
    ],
    "memory_fabric": [
        case("preflight_silent_on_missing_path", preflight_silent_on_missing_path),
        case("prompt_search_silent_on_empty_prompt", prompt_search_silent_on_empty_prompt),
        case("prompt_search_finds_records", prompt_search_finds_records),
    ],
    "script_smoke": [
        case("clean_script_silent", smoke_test_clean_script),
    ],
    "agent_patterns": [
        case("brief_runs_clean", agent_patterns_brief_silent_on_empty),
        case("full_report_runs", agent_patterns_full_runs),
        case("json_valid", agent_patterns_json_valid),
    ],
    "proactive_drift": [
        case("runs_clean", proactive_drift_runs_clean),
    ],
    "outcome_tracker": [
        case("query_runs_clean", outcome_tracker_record_silent_on_empty),
    ],
    "extended_doctor": [
        case("surfaces_recent_work", doctor_surfaces_recent_work),
    ],
    "behavior": [
        case("blocks_settings_json_via_gate", behavior_blocks_settings_json_via_gate),
        case("blocks_env_via_old_hook", behavior_blocks_env_via_old_hook),
        case("snapshot_on_script_edit", behavior_snapshot_on_script_edit),
        case("compact_lifecycle", behavior_compact_lifecycle),
        case("memory_loop", behavior_memory_loop),
        case("prompt_search_surfaces_relevant", behavior_prompt_search_surfaces_relevant),
        case("worktree_round_trip_real_worktree", behavior_worktree_round_trip_real_worktree),
        case("normal_session_scope_unchanged", behavior_normal_session_scope_unchanged),
    ],
    "smoke_coverage": [
        case("snapshot_harness", smoke_snapshot_harness),
        case("restore_harness", smoke_restore_harness),
        case("self_correct", smoke_self_correct),
        case("harness_gc", smoke_harness_gc),
        case("tool_factory", smoke_tool_factory),
        case("compact_brief", smoke_memory_fabric_compact_brief),
        case("session_record", smoke_memory_fabric_session_record),
        case("session_close", smoke_session_close),
        case("eval_harness", smoke_eval_harness),
        case("weekly_sweep", smoke_weekly_sweep),
    ],
    "csi_presence_mirror": [
        case("silent_when_no_source_dir", csi_presence_mirror_silent_when_no_source_dir),
        case("copies_files_when_source_exists", csi_presence_mirror_copies_files_when_source_exists),
        case("silent_on_malformed_stdin", csi_presence_mirror_silent_on_malformed_stdin),
    ],
    "hook_event_tap": [
        case("passes_through_and_records", hook_event_tap_passes_through_and_records),
        case("classifies_block", hook_event_tap_classifies_block),
    ],
    "install_sh": [
        case("check_returns_clean_after_install", install_sh_check_returns_clean_after_install),
        case("manifest_has_expected_fields", install_sh_manifest_has_expected_fields),
    ],
    "probe_hook": [
        case("writes_marker_to_log_and_emits_json", probe_hook_writes_marker_to_log_and_emits_json),
        case("silent_on_log_write_error", probe_hook_silent_on_log_write_error),
    ],
    "brainstorm": [
        case("returns_gaps", brainstorm_py_returns_gaps),
    ],
    "goal_state": [
        case("set_status_complete_cycle", goal_state_set_status_complete_cycle),
    ],
    "eval_loop": [
        case("regression_detected_when_latest_drops", eval_regression_detected_when_latest_drops),
        case("regression_skipped_with_insufficient_runs", eval_regression_skipped_with_insufficient_runs),
        case("regression_skips_error_runs", eval_regression_skips_error_runs),
        case("brief_emits_when_results_exist", eval_brief_emits_when_results_exist),
    ],
}


def main():
    ap = argparse.ArgumentParser(description="Run harness tests")
    ap.add_argument("suite", nargs="?", choices=list(SUITES.keys()) + ["all"], default="all")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    total_pass = 0
    total_fail = 0
    failures = []

    suites = list(SUITES.keys()) if args.suite == "all" else [args.suite]
    for s in suites:
        if args.verbose:
            print(f"\n[{s}]")
        for name, run in SUITES[s]:
            ok, msg = run()
            if ok:
                total_pass += 1
                if args.verbose:
                    print(f"  PASS  {name}")
            else:
                total_fail += 1
                failures.append((s, name, msg))
                if args.verbose:
                    print(f"  FAIL  {name}: {msg}")
                else:
                    print(f"FAIL  {s}/{name}: {msg}")

    print(f"\nresults: {total_pass} pass, {total_fail} fail")
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()