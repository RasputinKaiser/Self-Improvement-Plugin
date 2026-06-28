#!/usr/bin/env python3
"""Self-correction layer — proactive analyzer, not a hook.

Reads recent Memory Fabric records (filtered to source_backed_agent_run to
exclude CSI's seeded noise), identifies failure patterns, lists untested
scripts, surfaces repeated mistakes, and proposes concrete fixes. Writes a
markdown report to ~/.ncode/improvements.md.

Invoked from the weekly cron as part of the self-improvement sweep. Can also
be called on-demand: `python3 self_correct.py`.

Output is append-only to ~/.ncode/improvements.md so it builds a history.

Usage:
  self_correct.py                 # analyze last 50 records, append report
  self_correct.py --since 7d      # last 7 days only
  self_correct.py --json           # machine-readable, no file write
"""
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

CACHE_ROOT = os.path.expanduser(
    "~/.codex/plugins/cache/ralto-local/codex-memory-fabric"
)
NCODE_DIR = Path.home() / ".ncode"
SCRIPTS_DIR = NCODE_DIR / "scripts"
IMPROVEMENTS_PATH = NCODE_DIR / "improvements.md"
DEFAULT_LIMIT = 100


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def parse_since(since_str):
    if not since_str:
        return None
    m = re.match(r"^(\d+)([dhmw])$", since_str)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    units = {"d": "days", "h": "hours", "m": "minutes", "w": "weeks"}
    return datetime.now(timezone.utc) - timedelta(**{units[unit]: n})


def fetch_agent_records(mf, since_dt=None, limit=DEFAULT_LIMIT):
    """Pull recent records that came from real agent runs."""
    cmd = ["python3", mf, "search",
           "--query", "outcome session work learning task",
           "--provenance-type", "source_backed_agent_run",
           "--limit", str(limit)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            records = json.loads(r.stdout).get("records") or []
            if since_dt:
                filtered = []
                for rec in records:
                    ts = rec.get("created_at") or rec.get("updated_at") or ""
                    try:
                        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if rec_dt >= since_dt:
                            filtered.append(rec)
                    except (ValueError, TypeError):
                        pass
                records = filtered
            return records
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def find_failure_patterns(records):
    """Group failure-tagged records by topic + frequency."""
    failures = [rec for rec in records
                if "failure" in (rec.get("tags") or [])]
    by_topic = defaultdict(list)
    for rec in failures:
        body = (rec.get("body") or "").lower()
        title = (rec.get("title") or "").lower()
        # Extract file/path mentions as topic
        for m in re.findall(r"[\w/.\-]+\.(?:py|md|json|sh)", body + " " + title):
            by_topic[m].append(rec)
        # Also use tags as topics
        for tag in rec.get("tags") or []:
            if tag not in ("failure", "outcome"):
                by_topic[tag].append(rec)
    # Sort by frequency
    return sorted(by_topic.items(), key=lambda x: -len(x[1]))


def find_repeated_approaches(records):
    """Find tool/technique patterns that appear multiple times."""
    pattern_counts = Counter()
    for rec in records:
        body = rec.get("body") or ""
        # Extract mentions of approaches: tool combos, "Edit", "Bash", "Write", "patch"
        for line in body.split("\n"):
            line = line.strip().lower()
            if line.startswith("tool_calls:") or line.startswith("edits:") or line.startswith("bash_runs:"):
                continue
            for technique in ("binary patch", "byte-for-byte", "tool_factory",
                              "validate_harness", "harness_gc", "agent_patterns",
                              "memory_fabric", "autonomy_gate", "compact_continuity"):
                if technique in line:
                    pattern_counts[technique] += 1
    return pattern_counts.most_common(5)


def find_untested_scripts():
    """Scripts without references in run_tests.py."""
    if not SCRIPTS_DIR.is_dir():
        return []
    run_tests = SCRIPTS_DIR / "run_tests.py"
    if not run_tests.exists():
        return []
    content = run_tests.read_text(errors="replace")
    tested_stems = set()
    for m in re.findall(r"[\"']([\w_]+\.py)[\"']", content):
        tested_stems.add(m.replace(".py", ""))
    # also any function definition with that name
    for m in re.findall(r"def (\w+)", content):
        tested_stems.add(m)
    # also SUITES keys
    for m in re.findall(r"\"([\w_]+)\":\s*\[", content):
        tested_stems.add(m)

    untested = []
    for p in SCRIPTS_DIR.iterdir():
        if p.suffix != ".py" or p.name.startswith(".") or p.name == "run_tests.py":
            continue
        if p.stem not in tested_stems and p.name not in content:
            untested.append(p.name)
    return untested


def find_stale_scripts(days=60):
    """Scripts untouched in the last N days."""
    if not SCRIPTS_DIR.is_dir():
        return []
    import time
    threshold = time.time() - (days * 86400)
    stale = []
    for p in SCRIPTS_DIR.iterdir():
        if p.suffix != ".py":
            continue
        try:
            if p.stat().st_mtime < threshold:
                stale.append(p.name)
        except OSError:
            continue
    return stale


def find_never_recalled(mf, records):
    """Find records that are old but have never been retrieved via preflight."""
    # We can't directly query retrieval counts, so approximate by:
    # if a record >7d old and no recent record references its tags, it's "never recalled"
    # Simpler heuristic: records with body length <100 (stubs) and tags that don't appear in recent prompts
    return [rec for rec in records
            if len(rec.get("body", "")) < 100
            and (rec.get("created_at") or "")[:10] < "2026-06-27"][:5]


def build_report(records, since_str):
    """Assemble markdown report sections. Starts with H2 ## Self-correction."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = [f"## Self-correction — {ts}", ""]

    if not records:
        sections.append("_No prior records to analyze. Run more tasks to populate Memory Fabric._")
        return "\n".join(sections)

    outcomes = [r for r in records if "outcome" in (r.get("tags") or [])]
    failures = [r for r in records if "failure" in (r.get("tags") or [])]
    successes = [r for r in records if "success" in (r.get("tags") or [])]
    rate = (len(successes) / len(outcomes) * 100) if outcomes else 0

    sections.append("### Outcome metrics")
    sections.append(f"- total outcomes: {len(outcomes)}")
    sections.append(f"- successes: {len(successes)}")
    sections.append(f"- failures: {len(failures)}")
    if outcomes:
        sections.append(f"- success rate: {rate:.0f}%")
    if since_str:
        sections.append(f"- window: last {since_str}")
    sections.append("")

    failure_patterns = find_failure_patterns(failures)
    if failure_patterns:
        sections.append("### Recurring failure topics")
        for topic, rec_list in failure_patterns[:5]:
            if len(rec_list) >= 1:
                sections.append(f"- **{topic}** — {len(rec_list)}x failure")
                latest = rec_list[-1]
                title = latest.get("title", "")[:80]
                sections.append(f"  - latest: {title}")
        sections.append("")

    repeated = find_repeated_approaches(records)
    if repeated:
        sections.append("### Most-used approaches")
        for approach, n in repeated:
            sections.append(f"- {approach}: {n}x")
        sections.append("")

    untested = find_untested_scripts()
    if untested:
        sections.append(f"### Untested scripts ({len(untested)})")
        for name in untested:
            sections.append(f"- {name}")
        sections.append("")
        sections.append("**Action**: add at least one regression case per script to run_tests.py")
        sections.append("")

    stale = find_stale_scripts()
    if stale:
        sections.append(f"### Stale scripts (no edits in 60d) — {len(stale)}")
        for name in stale:
            sections.append(f"- {name}")
        sections.append("")

    sections.append("### Recommended actions")
    if failures and rate < 80:
        sections.append("- [ ] Decompose each failure record into a concrete lesson")
        sections.append("- [ ] Add a regression test that would catch the failure")
    if untested:
        sections.append(f"- [ ] Add tests for {len(untested)} untested scripts")
    sections.append("- [ ] Re-run run_tests.py and ensure all pass")
    sections.append("- [ ] If new patterns emerged, record as learning-tier memory")

    return "\n".join(sections)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Self-correction analyzer")
    ap.add_argument("--since", help="time window: 7d, 24h, 30m, 4w")
    ap.add_argument("--json", action="store_true", help="machine-readable, no file write")
    args = ap.parse_args()

    mf = find_cli()
    if not mf:
        print("ERR: memory_fabric CLI not found", file=sys.stderr)
        sys.exit(2)

    since_dt = parse_since(args.since)
    records = fetch_agent_records(mf, since_dt=since_dt)
    report = build_report(records, args.since)

    if args.json:
        print(json.dumps({
            "record_count": len(records),
            "failures": sum(1 for r in records if "failure" in (r.get("tags") or [])),
            "untested_scripts": find_untested_scripts(),
            "stale_scripts": find_stale_scripts(),
            "failure_patterns": [t for t, _ in find_failure_patterns(records)],
        }, indent=2))
        return

    if args.json:
        print(report)
        return

    IMPROVEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Append mode; ensure preceding newline if file doesn't end with one
    is_new = not IMPROVEMENTS_PATH.exists()
    if not is_new:
        try:
            size = IMPROVEMENTS_PATH.stat().st_size
            if size > 0:
                with open(IMPROVEMENTS_PATH, "rb") as fr:
                    fr.seek(-1, 2)
                    last_byte = fr.read(1)
                if last_byte != b"\n":
                    with open(IMPROVEMENTS_PATH, "a", encoding="utf-8") as f:
                        f.write("\n")
        except OSError:
            pass

    with open(IMPROVEMENTS_PATH, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# NCode Self-Improvement Journal\n\n")
            f.write("Append-only log of self-correction sweeps, ordered by recency.\n")
            f.write("Most recent entry is shown by memory_fabric_doctor on SessionStart.\n\n")
        # Each entry starts with ## Self-correction — <ts>
        f.write("\n" + report + "\n")

    print(f"report appended to {IMPROVEMENTS_PATH}")
    print(f"records analyzed: {len(records)}")


if __name__ == "__main__":
    main()
    sys.exit(0)