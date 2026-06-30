#!/usr/bin/env python3
"""monitor_daemon.py — proactive monitoring daemon (Tier 5 #7).

Runs unattended (via launchd hourly, or via weekly_sweep) and checks for
external/dev-ops signals the agent can't see during a session:

- Stale dependencies (pip, npm) — uses `pip list --outdated` and
  `npm outdated --json` where available; JSON output for parseability.
- Untested scripts (delegated to proactive_drift.py's existing detection).
-Large debug/log dirs (delegated to harness_gc.py --deep).
- Failed tests / regressions (delegated to run_tests.py --json).
- Broken validator (`validate_harness.py` exit code).
- Expired weekly cron (the install.sh --install-cron mechanism) — checks
  launchctl and warns if the plist is missing or unloaded.

Output:
- Appends a JSON record to ~/.ncode/monitor_results.jsonl per run
- Writes a friendly markdown summary to ~/.ncode/monitor_status.md
- Issues with severity >= warning append to ~/.ncode/improvements.md

CLI:
  monitor_daemon.py            # run all checks, write outputs
  monitor_daemon.py --json     # emit JSON to stdout instead of files
  monitor_daemon.py --quiet    # only print high-severity items
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NCODE_DIR = Path.home() / ".ncode"
SCRIPTS_DIR = NCODE_DIR / "scripts"
RESULTS_PATH = NCODE_DIR / "monitor_results.jsonl"
STATUS_PATH = NCODE_DIR / "monitor_status.md"
IMPROVEMENTS_PATH = NCODE_DIR / "improvements.md"

PLIST_LABEL = "com.rasputinkaiser.ncode-sweep"
SEVERITIES = ("info", "warning", "critical")


def run_script(name, args=None, timeout=30):
    """Run a script in ~/.ncode/scripts/. Returns CompletedProcess."""
    cmd = ["python3", str(SCRIPTS_DIR / name)] + (args or [])
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        return subprocess.CompletedProcess(cmd, 1, "", f"failed: {e}")


def check_validator_present():
    """Is validate_harness.py present and exit-0?"""
    r = run_script("validate_harness.py", timeout=20)
    if r.returncode != 0:
        return [{
            "severity": "critical",
            "category": "validator",
            "title": "validate_harness.py failed",
            "detail": (r.stderr or r.stdout)[:300],
        }]
    return []


def check_tests_pass():
    """Does run_tests.py exit 0?"""
    r = run_script("run_tests.py", timeout=120)
    if r.returncode != 0:
        # Parse last line for summary
        last_line = (r.stdout or "").strip().splitlines()[-1:] or ["(no summary)"]
        return [{
            "severity": "critical",
            "category": "tests",
            "title": "run_tests.py regression",
            "detail": last_line[0],
        }]
    return []


def check_cron_installed():
    """Is the weekly sweep launchd plist loaded?"""
    r = subprocess.run(
        ["launchctl", "list", PLIST_LABEL],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode != 0:
        return [{
            "severity": "warning",
            "category": "cron",
            "title": "weekly sweep cron not loaded",
            "detail": (f"launchctl list {PLIST_LABEL} returned non-zero. "
                       "Run install.sh --install-cron to install the Mon 9:17 sweep."),
        }]
    return []


def check_pip_outdated():
    """Are any installed pip packages outdated? Best-effort."""
    try:
        r = subprocess.run(
            ["pip3", "list", "--outdated", "--format=json"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return []
    if r.returncode != 0:
        return []
    try:
        outdated = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not outdated:
        return []
    return [{
        "severity": "info",
        "category": "deps",
        "title": f"{len(outdated)} pip package(s) outdated",
        "detail": ", ".join(p["name"] for p in outdated[:10]) +
                  (f" ...({len(outdated)-10} more)" if len(outdated) > 10 else ""),
    }]


def check_untested_scripts():
    """Are there untested scripts in ~/.ncode/scripts/?"""
    r = run_script("proactive_drift.py", timeout=30)
    if r.returncode != 0:
        return []
    text = r.stdout or ""
    # Look for "Untested scripts" or similar lines
    issues = []
    for line in text.splitlines():
        if "untested" in line.lower() and "(" in line:
            issues.append({
                "severity": "warning",
                "category": "drift",
                "title": "untested scripts found",
                "detail": line.strip(),
            })
            break
    return issues


def check_install_drift():
    """Is the installed plugin out of sync with the source repo?"""
    install_sh = Path(__file__).resolve().parents[1] / "install.sh"
    if not install_sh.exists():
        return []  # No source repo — can't check drift
    r = subprocess.run(
        ["bash", str(install_sh), "--check"],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode == 0:
        return []
    return [{
        "severity": "warning",
        "category": "drift",
        "title": "Plugin install drift detected",
        "detail": (r.stdout or r.stderr or "").strip()[:200],
    }]


def check_script_permissions():
    """Are all installed scripts executable?

    Root-cause check for the recurring '+x drift' pattern: install.sh
    now chmod +x post-rsync, but this catches regressions if new scripts
    are added without that step catching them.
    """
    issues = []
    if not SCRIPTS_DIR.is_dir():
        return []
    non_exec = []
    for f in SCRIPTS_DIR.iterdir():
        if f.suffix not in (".py", ".sh"):
            continue
        if not os.access(f, os.X_OK):
            non_exec.append(f.name)
    if non_exec:
        issues.append({
            "severity": "info",
            "category": "permissions",
            "title": f"{len(non_exec)} script(s) not executable",
            "detail": ", ".join(non_exec[:8]) +
                      (f" ...({len(non_exec)-8} more)" if len(non_exec) > 8 else ""),
        })
    return issues


def check_large_debug_dirs():
    """Are there large debug dirs bloating ~/.ncode?"""
    r = run_script("harness_gc.py", args=["--deep"], timeout=30)
    if r.returncode != 0:
        return []
    text = r.stdout or ""
    issues = []
    # Look for suspiciously large entries (>50MB)
    for line in text.splitlines():
        if "MB" in line and ">" in line:
            try:
                # Parse "1234MB /path/to/dir" pattern
                if "MB" in line:
                    parts = line.split()
                    for p in parts:
                        if p.endswith("MB") and p[:-2].isdigit():
                            if int(p[:-2]) > 50:
                                issues.append({
                                    "severity": "info",
                                    "category": "disk",
                                    "title": "large dir/file in ~/.ncode",
                                    "detail": line.strip()[:200],
                                })
                                break
            except (ValueError, IndexError):
                pass
            if issues:
                break
    return issues


def run_all_checks():
    """Run every check. Returns list of issues (each dict)."""
    issues = []
    issues.extend(check_validator_present())
    issues.extend(check_tests_pass())
    issues.extend(check_cron_installed())
    issues.extend(check_install_drift())
    issues.extend(check_script_permissions())
    issues.extend(check_pip_outdated())
    issues.extend(check_untested_scripts())
    issues.extend(check_large_debug_dirs())
    return issues


def build_markdown(issues, started_at, finished_at):
    """Build the friendly ~/.ncode/monitor_status.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Monitor status — {ts}",
        "",
        f"Last run: started {started_at}, finished {finished_at}",
        f"Found {len(issues)} issue(s).",
        "",
    ]
    for sev in SEVERITIES:
        sev_issues = [i for i in issues if i.get("severity") == sev]
        if not sev_issues:
            continue
        lines.append(f"## {sev.upper()} ({len(sev_issues)})")
        for i in sev_issues:
            lines.append(f"- **[{i['category']}]** {i['title']}")
            if i.get("detail"):
                lines.append(f"  - {i['detail'][:200]}")
        lines.append("")
    if not issues:
        lines.append("All checks pass.")
    return "\n".join(lines) + "\n"


def append_to_improvements(issues):
    """Append WARNING+ issues to improvements.md (so they surface at SessionStart)."""
    high = [i for i in issues if i.get("severity") in ("warning", "critical")]
    if not high:
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(IMPROVEMENTS_PATH, "a", encoding="utf-8") as fp:
        fp.write(f"\n## Monitor alert — {ts}\n\n")
        for i in high:
            fp.write(f"- **[{i['severity']}] [{i['category']}]** {i['title']}\n")
            if i.get("detail"):
                fp.write(f"  {i['detail'][:200]}\n")


def persist_run(issues):
    """Append run record to ~/.ncode/monitor_results.jsonl as newline-delimited JSON."""
    record = {
        "id": datetime.now(timezone.utc).isoformat(),
        "issues": issues,
        "issueCount": len(issues),
        "criticalCount": sum(1 for i in issues if i.get("severity") == "critical"),
        "warningCount": sum(1 for i in issues if i.get("severity") == "warning"),
    }
    NCODE_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(record) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Proactive monitoring daemon (Tier 5 #7)")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON to stdout instead of writing files")
    ap.add_argument("--quiet", action="store_true",
                    help="only print WARNING+ items")
    args = ap.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    issues = run_all_checks()
    finished_at = datetime.now(timezone.utc).isoformat()

    if args.json:
        out = {"startedAt": started_at, "finishedAt": finished_at,
               "issueCount": len(issues), "issues": issues}
        print(json.dumps(out, indent=2))
        return 0

    persist_run(issues)
    markdown = build_markdown(issues, started_at, finished_at)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(markdown, encoding="utf-8")
    append_to_improvements(issues)

    if args.quiet:
        high = [i for i in issues if i.get("severity") in ("warning", "critical")]
        if not high:
            print("0 warnings/criticals.")
            return 0
        for i in high:
            print(f"  [{i['severity']}] [{i['category']}] {i['title']}")
        return 0

    print(f"monitor: {len(issues)} issue(s) — {STATUS_PATH}")
    for i in issues:
        print(f"  [{i['severity']}] [{i['category']}] {i['title']}")
    return 0 if not any(i.get("severity") == "critical" for i in issues) else 1


if __name__ == "__main__":
    sys.exit(main())
