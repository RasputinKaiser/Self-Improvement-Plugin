#!/usr/bin/env python3
"""Agent patterns aggregator.

Queries Memory Fabric for recent outcome + learning records, classifies them,
surfaces trends: success rate, common failure patterns, repeated task types,
automation candidates.

Usage:
  agent_patterns.py                      # full report, last 50 records
  agent_patterns.py --brief             # one-line summary for SessionStart
  agent_patterns.py --json               # machine-readable
  agent_patterns.py --since 7d          # last 7 days only

Advisory-only, silent on failure.
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
DEFAULT_LIMIT = 50


def find_cli():
    candidates = sorted(glob.glob(f"{CACHE_ROOT}/0.1.0*/scripts/memory_fabric.py"))
    return candidates[-1] if candidates else None


def parse_since(since_str):
    """Parse '7d', '24h', '30m' into a datetime threshold."""
    if not since_str:
        return None
    m = re.match(r"^(\d+)([dhmw])$", since_str)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    units = {"d": "days", "h": "hours", "m": "minutes", "w": "weeks"}
    return datetime.now(timezone.utc) - timedelta(**{units[unit]: n})


def fetch_records(mf, scope=None, limit=DEFAULT_LIMIT):
    """Fetch recent learning records (outcomes + learnings).

    Filter to source_backed_agent_run provenance to exclude seeded
    learning records — those would otherwise drown out my actual patterns.
    """
    cmd = ["python3", mf, "search",
           "--query", "outcome session learning task",
           "--tier", "learning",
           "--provenance-type", "source_backed_agent_run",
           "--limit", str(limit)]
    if scope:
        cmd.extend(["--scope", scope])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout).get("records") or []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def classify_outcomes(records, since_dt=None):
    """Pull outcome-tagged records and compute metrics."""
    outcomes = []
    for rec in records:
        tags = rec.get("tags") or []
        if "outcome" not in tags and "task-metrics" not in tags:
            continue
        ts = rec.get("created_at") or rec.get("updated_at") or ""
        if since_dt and ts:
            try:
                rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if rec_dt < since_dt:
                    continue
            except (ValueError, TypeError):
                pass
        outcomes.append(rec)

    total = len(outcomes)
    successes = sum(1 for o in outcomes if "success" in (o.get("tags") or []))
    failures = sum(1 for o in outcomes if "failure" in (o.get("tags") or []))
    total_calls = 0
    total_edits = 0
    for o in outcomes:
        body = o.get("body", "")
        for line in body.split("\n"):
            if line.startswith("tool_calls:"):
                try:
                    total_calls += int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("edits:"):
                try:
                    total_edits += int(line.split(":")[1].strip())
                except ValueError:
                    pass
    return {
        "total": total,
        "successes": successes,
        "failures": failures,
        "success_rate": (successes / total) if total else 0,
        "total_tool_calls": total_calls,
        "total_edits": total_edits,
    }


def find_repeated_patterns(records):
    """Find common title/keyword patterns across non-outcome learnings."""
    learnings = [r for r in records
                 if "outcome" not in (r.get("tags") or [])
                 and "task-metrics" not in (r.get("tags") or [])]
    title_words = Counter()
    for rec in learnings:
        title = rec.get("title", "").lower()
        for w in re.findall(r"\b[a-z][a-z0-9_-]{2,}\b", title):
            if w not in {"the", "and", "for", "with", "from", "into", "after", "before"}:
                title_words[w] += 1
    return title_words.most_common(8)


def extract_approach_metrics(records):
    """For outcome records, parse tool_calls/edits/bash_runs and pair with success/failure.

    Returns list of dicts: {success, tool_calls, edits, bash_runs, attempts, title}
    where title is the prompt truncated.
    """
    outcomes = []
    for rec in records:
        tags = rec.get("tags") or []
        if "outcome" not in tags and "task-metrics" not in tags:
            continue
        success = "success" in tags
        body = rec.get("body", "")
        m = {"success": success, "title": rec.get("title", "")[:80]}
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("tool_calls:"):
                try: m["tool_calls"] = int(line.split(":", 1)[1].strip())
                except ValueError: m["tool_calls"] = 0
            elif line.startswith("edits:"):
                try: m["edits"] = int(line.split(":", 1)[1].strip())
                except ValueError: m["edits"] = 0
            elif line.startswith("bash_runs:"):
                try: m["bash_runs"] = int(line.split(":", 1)[1].strip())
                except ValueError: m["bash_runs"] = 0
            elif line.startswith("attempts:"):
                try: m["attempts"] = int(line.split(":", 1)[1].strip())
                except ValueError: m["attempts"] = 0
        outcomes.append(m)
    return outcomes


def correlate_approach_outcome(records):
    """Compute per-approach-metric success rates.

    Returns dict: {metric: {bucket_name: {success_count, total_count, success_rate}}}

    Buckets: low/medium/high based on quartiles of the metric.
    """
    outcomes = extract_approach_metrics(records)
    if len(outcomes) < 3:
        return None

    results = {}

    for metric in ("tool_calls", "edits", "bash_runs", "attempts"):
        values = [m.get(metric, 0) for m in outcomes]
        if not values or max(values) == 0:
            continue
        # tertiles
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        p33 = sorted_vals[n // 3] if n >= 3 else 0
        p67 = sorted_vals[(2 * n) // 3] if n >= 3 else 0

        buckets = {"low": [], "medium": [], "high": []}
        for o in outcomes:
            v = o.get(metric, 0)
            if v <= p33:
                bucket = "low"
            elif v <= p67:
                bucket = "medium"
            else:
                bucket = "high"
            buckets[bucket].append(o)

        bucket_stats = {}
        for name, items in buckets.items():
            if items:
                succ = sum(1 for o in items if o["success"])
                bucket_stats[name] = {
                    "success": succ,
                    "total": len(items),
                    "rate": succ / len(items),
                    "avg_val": sum(o.get(metric, 0) for o in items) / len(items),
                }
        results[metric] = bucket_stats

    return results


def format_correlation(corr):
    """Human-readable correlation summary."""
    if not corr:
        return None
    lines = ["Approach → outcome correlation (bucket success rates):"]
    for metric, buckets in corr.items():
        if not buckets:
            continue
        lines.append(f"  {metric}:")
        for name, stats in buckets.items():
            rate_pct = stats["rate"] * 100
            lines.append(f"    {name}: {rate_pct:.0f}% ({stats['success']}/{stats['total']}, avg {stats['avg_val']:.1f})")
    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Agent patterns aggregator")
    ap.add_argument("--brief", action="store_true", help="one-line summary")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--since", help="time window: 7d, 24h, 30m, 4w")
    ap.add_argument("--scope", help="project scope filter")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = ap.parse_args()

    mf = find_cli()
    if not mf:
        if args.json:
            print("[]")
        return

    since_dt = parse_since(args.since)
    records = fetch_records(mf, scope=args.scope, limit=args.limit)
    if not records:
        if args.brief:
            return
        if args.json:
            print("[]")
        else:
            print("no records found")
        return

    outcomes = classify_outcomes(records, since_dt)
    patterns = find_repeated_patterns(records)
    correlation = correlate_approach_outcome(records)

    if args.brief:
        if outcomes["total"] == 0:
            return
        rate = outcomes["success_rate"] * 100
        msg = (f"agent_patterns: {outcomes['total']} outcomes, "
               f"{rate:.0f}% success, "
               f"{outcomes['total_tool_calls']} tool calls, "
               f"{outcomes['total_edits']} edits.")
        if patterns:
            top = patterns[0]
            msg += f" Top pattern: '{top[0]}' ({top[1]}x)."
        if correlation:
            # Add a one-line correlation hint
            for metric, buckets in correlation.items():
                if not buckets:
                    continue
                # Find the bucket with highest success rate
                best = max(buckets.items(), key=lambda x: x[1]["rate"])
                if best[1]["total"] >= 2:
                    msg += f" {metric}={best[0]} correlates with success ({best[1]['rate']*100:.0f}%)."
                    break
        sys.stdout.write(json.dumps({"additionalContext": msg}))
        sys.stdout.flush()
        return

    if args.json:
        print(json.dumps({
            "outcomes": outcomes,
            "patterns": patterns,
            "correlation": correlation,
            "record_count": len(records),
        }, indent=2))
        return

    print("=== Agent Patterns ===\n")
    if outcomes["total"]:
        rate = outcomes["success_rate"] * 100
        avg_calls = outcomes["total_tool_calls"] / outcomes["total"] if outcomes["total"] else 0
        avg_edits = outcomes["total_edits"] / outcomes["total"] if outcomes["total"] else 0
        print(f"Outcomes: {outcomes['total']} total, {rate:.0f}% success")
        print(f"  successes: {outcomes['successes']}")
        print(f"  failures: {outcomes['failures']}")
        print(f"  total tool calls: {outcomes['total_tool_calls']} (avg {avg_calls:.1f}/task)")
        print(f"  total edits: {outcomes['total_edits']} (avg {avg_edits:.1f}/task)")
    else:
        print("Outcomes: 0 (record more outcomes via task_outcome_tracker)")

    if patterns:
        print(f"\nTop patterns across {len(records)} learning records:")
        for word, count in patterns:
            print(f"  {word}: {count}x")

    corr_text = format_correlation(correlation)
    if corr_text:
        print(f"\n{corr_text}")


if __name__ == "__main__":
    main()
    sys.exit(0)
