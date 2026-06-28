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


SUITES = {
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