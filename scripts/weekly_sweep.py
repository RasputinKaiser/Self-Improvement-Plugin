#!/usr/bin/env python3
"""weekly_sweep.py — weekly self-improvement sweep.

Runs the full self-improvement loop unattended:
1. snapshot harness (pre-sweep known-good state)
2. run_tests.py (regression suite)
3. eval_harness.py (run eval cases — Tier 5 capability extension)
4. self_correct.py (analyze outcomes + eval regressions → improvements.md)
5. snapshot again (post-sweep known-good state)
6. record a learning-tier memory capturing what was swept

Designed to be invoked by NCode's scheduled task system (CronCreate) on
Mondays around 9:17 AM. Runs in the harness cwd (~/.ncode) so hooks fire
correctly.

Exit code 0 = clean sweep; non-zero = something failed (investigate via
~/.ncode/improvements.md or the smoke output).
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path.home() / ".ncode" / "scripts"


def run_step(name, cmd, cwd=None, timeout=300):
    """Run a subprocess, print a header, return (ok, stdout_tail)."""
    print(f"\n=== {name} ===", flush=True)
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd or str(Path.home() / ".ncode"),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ok = r.returncode == 0
        tail = (r.stdout + r.stderr).strip().splitlines()[-5:]
        for line in tail:
            print(f"  {line}")
        if not ok:
            print(f"  (exit {r.returncode})")
        return ok, r.stdout
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return False, ""
    except (OSError, FileNotFoundError) as e:
        print(f"  ERROR: {e}")
        return False, ""


def rotate_logs():
    """Keep only the last ~8KB of sweep.log + sweep.err.log (prevents unbounded growth)."""
    log_dir = Path.home() / ".ncode" / "logs"
    for log_name in ("sweep.log", "sweep.err.log"):
        log_path = log_dir / log_name
        if not log_path.exists():
            continue
        try:
            size = log_path.stat().st_size
            if size > 16_000:
                with open(log_path, "rb") as f:
                    f.seek(size - 8_000)
                    content = f.read()
                with open(log_path, "wb") as f:
                    f.write(b"[rotated - older entries truncated]\n" + content)
        except OSError:
            pass


def prune_old_snapshots(keep_recent=5, max_age_days=30):
    """Prune snapshots older than max_age_days, keeping the most recent `keep_recent`."""
    snap_dir = Path.home() / ".ncode" / "backups/snapshots"
    if not snap_dir.is_dir():
        return 0, 0
    import time as _time
    import shutil as _shutil
    now = _time.time()
    snapshots = []
    for entry in snap_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            manifest = entry / "manifest.json"
            ts = manifest.stat().st_mtime if manifest.exists() else entry.stat().st_mtime
            snapshots.append((ts, entry))
        except OSError:
            continue
    snapshots.sort(key=lambda x: x[0], reverse=True)
    pruned = 0
    for i, (ts, entry) in enumerate(snapshots):
        age_days = (now - ts) / 86400
        if i < keep_recent:
            continue
        if age_days > max_age_days:
            try:
                _shutil.rmtree(entry)
                pruned += 1
            except OSError:
                pass
    return pruned, len(snapshots)


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Weekly self-improvement sweep (snapshot → tests → evals → self_correct → snapshot)"
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="print plan, don't execute steps")
    args = ap.parse_args()

    if args.dry_run:
        print("dry-run: would run snapshot → tests → eval_harness → self_correct → snapshot")
        return 0

    rotate_logs()

    started_at = datetime.now(timezone.utc).isoformat()
    print(f"=== weekly sweep started {started_at} ===", flush=True)

    results = {}

    # 1. Pre-sweep snapshot
    ok, _ = run_step(
        "snapshot (pre-sweep)",
        ["python3", str(SCRIPTS_DIR / "snapshot_harness.py"),
         "--reason", "pre-weekly-sweep"],
        timeout=30,
    )
    results["snapshot_pre"] = ok

    # 2. Tests
    ok, _ = run_step(
        "run_tests.py",
        ["python3", str(SCRIPTS_DIR / "run_tests.py")],
        timeout=180,
    )
    results["tests"] = ok

    # 3. Eval harness (Tier 5 closure — drives evals unattended)
    # Allowed to fail without aborting the sweep — evals are informational.
    ok, eval_stdout = run_step(
        "eval_harness.py",
        ["python3", str(SCRIPTS_DIR / "eval_harness.py"), "--json"],
        timeout=600,
    )
    results["eval"] = ok
    eval_summary = None
    try:
        eval_summary = json.loads(eval_stdout) if eval_stdout.strip() else None
    except json.JSONDecodeError:
        pass

    # 4. Self-correction (now includes find_eval_regressions)
    ok, _ = run_step(
        "self_correct.py",
        ["python3", str(SCRIPTS_DIR / "self_correct.py")],
        timeout=60,
    )
    results["self_correct"] = ok

    # 4b. Proactive monitoring daemon (Tier 5 #7) — runs the same checks
    # unattended. Writing to improvements.md is intentional (appends WARNING+
    # items), so subsequent steps see them.
    ok, _ = run_step(
        "monitor_daemon.py",
        ["python3", str(SCRIPTS_DIR / "monitor_daemon.py"), "--quiet"],
        timeout=180,
    )
    results["monitor"] = ok

    # 4c. Fix drafter (Phase C) — drafts proposed fixes for any active
    # eval regressions. Does NOT auto-apply — surfaces for review.
    ok, _ = run_step(
        "fix_drafter.py",
        ["python3", str(SCRIPTS_DIR / "fix_drafter.py"), "--json"],
        timeout=30,
    )
    results["fix_drafter"] = ok

    # 5. Post-sweep snapshot
    ok, _ = run_step(
        "snapshot (post-sweep)",
        ["python3", str(SCRIPTS_DIR / "snapshot_harness.py"),
         "--reason", "post-weekly-sweep"],
        timeout=30,
    )
    results["snapshot_post"] = ok

    # 6. Summary
    finished_at = datetime.now(timezone.utc).isoformat()
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n=== sweep complete — {passed}/{total} steps ok ===", flush=True)
    for k, v in results.items():
        sym = "OK" if v else "FAIL"
        print(f"  [{sym}] {k}")

    if eval_summary:
        ran = eval_summary.get("ran", 0)
        passed_e = eval_summary.get("passed", 0)
        failed_e = eval_summary.get("failed", 0)
        errors_e = eval_summary.get("errors", 0)
        print(f"\n  eval: {passed_e}/{ran} passed, {failed_e} failed, {errors_e} errors")

    # Exit non-zero if any critical step failed (snapshot_pre, tests, self_correct)
    critical_ok = results.get("snapshot_pre") and results.get("tests") and results.get("self_correct")

    # 7. Prune old snapshots (keep most recent 5, delete >30d old)
    pruned, total_snaps = prune_old_snapshots()
    if pruned:
        print(f"  pruned {pruned} snapshots (>{30}d old, kept 5 most recent)")

    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())