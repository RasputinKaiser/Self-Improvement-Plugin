#!/usr/bin/env python3
"""Generate compact inline-widget HTML from live SIPS state.

Hermes desktop renders any HTML file inline in chat via the ::preview{file="..."}
directive. The frame injects the app theme as CSS variables and a transparent
background, so widgets written against var(--foreground)/var(--accent) etc.
read as native chat UI — the same trick as the btc-usd-sparkline demo.

Usage:
    python3 scripts/inline_widget.py board [--out PATH]
    python3 scripts/inline_widget.py lifecycle [--out PATH]
    python3 scripts/inline_widget.py memory [--out PATH]

Widget kinds:
    board      Goal Board projection: status, progress, task cards, counts.
    lifecycle  Hook-event stream: top tools, status breakdown, activity sparkline.
    memory     Memory Fabric: record counts, trust split, tier donut, recent records.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

BASE_CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  font-family: var(--font-family, ui-sans-serif, system-ui, sans-serif);
  color: var(--foreground, #333);
  font-size: 13px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}
.w { max-width: 560px; }
.caption {
  font-size: 11px;
  color: var(--muted-foreground, #888);
  margin: 0 0 6px;
  text-wrap: balance;
}
.card {
  border-radius: 12px;
  background: var(--card, rgba(127,127,127,0.06));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--foreground, #333) 8%, transparent),
    0 1px 2px color-mix(in srgb, var(--foreground, #333) 4%, transparent),
    0 3px 10px color-mix(in srgb, var(--foreground, #333) 6%, transparent);
  padding: 12px;
  animation: rise 0.3s cubic-bezier(0.2, 0, 0, 1) backwards;
}
@keyframes rise { from { transform: translateY(6px); } }
.num { font-variant-numeric: tabular-nums; }
.head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dot {
  width: 8px; height: 8px; border-radius: 50%; flex: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}
.dot.running, .dot.active { background: #eab308; color: #eab308; }
.dot.complete, .dot.done, .dot.ok { background: #22c55e; color: #22c55e; }
.dot.blocked, .dot.failed { background: #ef4444; color: #ef4444; }
.obj {
  font-weight: 600;
  flex: 1 1 140px;
  min-width: 120px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-wrap: balance;
  font-size: 12.5px;
}
.chip {
  font-size: 10px;
  font-weight: 600;
  border-radius: 999px;
  padding: 2px 8px;
  flex: none;
  font-variant-numeric: tabular-nums;
  color: var(--muted-foreground, #888);
  background: color-mix(in srgb, var(--foreground, #333) 6%, transparent);
}
.chip.good { color: #16a34a; background: color-mix(in srgb, #22c55e 14%, transparent); }
.chip.warn { color: #b45309; background: color-mix(in srgb, #eab308 18%, transparent); }
.chip.bad { color: #dc2626; background: color-mix(in srgb, #ef4444 14%, transparent); }
.chip.accent { color: var(--accent, #3b82f6); background: color-mix(in srgb, var(--accent, #3b82f6) 12%, transparent); }
.progress {
  margin: 10px 0 5px;
  height: 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--foreground, #333) 10%, transparent);
  overflow: hidden;
}
.progress > i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--accent, #3b82f6) 70%, transparent), var(--accent, #3b82f6));
  transition: width 0.4s cubic-bezier(0.2, 0, 0, 1);
}
.meta { font-size: 11px; color: var(--muted-foreground, #888); margin: 0; font-variant-numeric: tabular-nums; }
.tasks { display: grid; gap: 5px; margin-top: 9px; }
.task {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 9px;
  border-radius: 7px;
  cursor: default;
  transition: background 0.15s ease;
  animation: rise 0.3s cubic-bezier(0.2, 0, 0, 1) backwards;
}
.task:nth-child(1) { animation-delay: 0.04s; }
.task:nth-child(2) { animation-delay: 0.08s; }
.task:nth-child(3) { animation-delay: 0.12s; }
.task:nth-child(4) { animation-delay: 0.16s; }
.task:nth-child(5) { animation-delay: 0.20s; }
.task:nth-child(6) { animation-delay: 0.24s; }
.task:nth-child(7) { animation-delay: 0.28s; }
.task:nth-child(8) { animation-delay: 0.32s; }
.task:hover { background: color-mix(in srgb, var(--accent, #3b82f6) 8%, transparent); }
.task .phase {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent, #3b82f6);
  flex: none;
  width: 58px;
}
.task .t {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.task .st { font-size: 10px; flex: none; color: var(--muted-foreground, #888); font-variant-numeric: tabular-nums; }
.actions { display: flex; gap: 6px; margin-top: 11px; }
.actions button {
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  background: color-mix(in srgb, var(--foreground, #333) 7%, transparent);
  color: var(--foreground, #333);
  padding: 6px 12px;
  cursor: pointer;
  position: relative;
  transition: background 0.15s ease, transform 0.12s ease;
}
.actions button::after { content: ""; position: absolute; inset: -6px; border-radius: 14px; }
.actions button:hover { background: color-mix(in srgb, var(--accent, #3b82f6) 14%, transparent); }
.actions button:active { transform: scale(0.96); }
.bars { display: grid; gap: 7px; margin-top: 10px; }
.bar { display: grid; grid-template-columns: 92px 1fr 52px; align-items: center; gap: 8px;
  animation: rise 0.3s cubic-bezier(0.2, 0, 0, 1) backwards; }
.bar:nth-child(1) { animation-delay: 0.03s; } .bar:nth-child(2) { animation-delay: 0.06s; }
.bar:nth-child(3) { animation-delay: 0.09s; } .bar:nth-child(4) { animation-delay: 0.12s; }
.bar:nth-child(5) { animation-delay: 0.15s; } .bar:nth-child(6) { animation-delay: 0.18s; }
.bar:nth-child(7) { animation-delay: 0.21s; } .bar:nth-child(8) { animation-delay: 0.24s; }
.bar .name { font-size: 11.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar .track { height: 6px; border-radius: 999px; background: color-mix(in srgb, var(--foreground, #333) 8%, transparent); overflow: hidden; }
.bar .track > i { display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--accent, #3b82f6) 55%, transparent), var(--accent, #3b82f6)); }
.bar .val { font-size: 11px; color: var(--muted-foreground, #888); text-align: right; font-variant-numeric: tabular-nums; }
.spark { margin-top: 12px; }
.spark svg { display: block; width: 100%; height: 44px; }
.spark .cap { font-size: 10px; color: var(--muted-foreground, #888); margin: 3px 0 0; }
.legend { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.recent { display: grid; gap: 6px; margin-top: 10px; }
.rec {
  display: flex; align-items: baseline; gap: 8px;
  padding: 6px 9px; border-radius: 7px;
  transition: background 0.15s ease;
  animation: rise 0.3s cubic-bezier(0.2, 0, 0, 1) backwards;
}
.rec:nth-child(1) { animation-delay: 0.04s; }
.rec:nth-child(2) { animation-delay: 0.08s; }
.rec:nth-child(3) { animation-delay: 0.12s; }
.rec:nth-child(4) { animation-delay: 0.16s; }
.rec:hover { background: color-mix(in srgb, var(--accent, #3b82f6) 8%, transparent); }
.rec .rt { flex: 1 1 auto; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.donut-row { display: flex; align-items: center; gap: 14px; margin-top: 10px; }
.donut { flex: none; }
.donut svg { display: block; }
.donut-legend { display: grid; gap: 4px; font-size: 11px; flex: 1; }
.donut-legend .row { display: flex; align-items: center; gap: 6px; }
.donut-legend .sw { width: 8px; height: 8px; border-radius: 3px; flex: none; }
.donut-legend .lbl { flex: 1; color: var(--muted-foreground, #888); }
.donut-legend .v { font-variant-numeric: tabular-nums; font-weight: 600; }
"""


def _page(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>{BASE_CSS}</style>
</head>
<body>
<div class="w">
{body}
</div>
</body>
</html>
"""


def _chip(text: str, kind: str = "") -> str:
    cls = f"chip {kind}".strip()
    return f'<span class="{cls}">{escape(text)}</span>'


# ---------------------------------------------------------------- board ----

def load_board() -> dict:
    """Read the live Goal Board projection through the existing CLI path.

    Degrades to an empty board when no goal is set (fresh SIPS homes) so the
    widget renders an honest empty state instead of failing.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "goal_state.py"), "board"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        try:
            error = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            error = {}
        if error.get("ok") is False and "no goal" in str(error.get("error", "")):
            return {"status": "inactive", "objective": "", "progress": {}, "counts": {}, "tasks": [], "revision": 0, "run_id": "legacy-goal"}
        raise RuntimeError(f"goal_state.py board failed: {proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


def render_board(board: dict) -> str:
    status = board.get("status", "unknown")
    objective = board.get("objective", "")
    progress = board.get("progress", {})
    total = int(progress.get("total", 0) or 0)
    complete = int(progress.get("complete", 0) or 0)
    ratio = float(progress.get("ratio", 0) or 0)
    pct = round(ratio * 100)
    counts = board.get("counts", {})
    revision = board.get("revision", 0)
    run_id = board.get("run_id", "unknown")
    tasks = board.get("tasks", [])

    count_bits = " · ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    task_html = []
    for task in tasks[:8]:
        phase = task.get("phase", "?")
        t_status = task.get("status", "?")
        title = task.get("title") or task.get("description") or task.get("id", "")
        attempts = task.get("attempts", 0)
        st_kind = ""
        if t_status in ("done", "completed", "complete"):
            st_kind = "good"
        elif t_status in ("failed", "blocked"):
            st_kind = "bad"
        elif t_status == "running":
            st_kind = "accent"
        task_html.append(
            '<div class="task" title="{title}">'
            '<span class="phase">{phase}</span>'
            '<span class="t">{title}</span>'
            '<span class="st">{status}{att}</span>'
            "</div>".format(
                title=escape(title[:140]),
                phase=escape(phase),
                status=escape(t_status),
                att=f" · try {attempts}" if attempts else "",
            )
        )
    more = len(tasks) - len(task_html)
    if more > 0:
        task_html.append(f'<div class="meta">+{more} more task(s)</div>')

    more_btn = ""
    if run_id and run_id != "legacy-goal":
        more_btn = '<button data-hermes-send="Show the SIPS goal board">Open Goal Board</button>'

    body = f"""
  <p class="caption">SIPS Goal Board — hover a task for detail; buttons send a chat prompt.</p>
  <div class="card">
    <div class="head">
      <span class="dot {escape(status)}"></span>
      <span class="obj" title="{escape(objective)}">{escape(objective[:160] or "(no objective)")}</span>
      {_chip(f"rev {revision}")}
      {_chip(escape(str(run_id)))}
    </div>
    <div class="progress" role="progressbar" aria-valuenow="{pct}"><i style="width:{pct}%"></i></div>
    <p class="meta"><span class="num">{complete}/{total} tasks ({pct}%)</span> · {escape(count_bits) or "no counts"}</p>
    <div class="tasks">{''.join(task_html) or '<p class="meta">no tasks</p>'}</div>
    <div class="actions">
      <button data-hermes-send="Refresh the SIPS inline board widget">Refresh</button>
      {more_btn}
    </div>
  </div>
"""
    return _page(body)


# ------------------------------------------------------------ lifecycle ----

def _hook_events_path() -> Path:
    override = os.environ.get("SIPS_HOOK_EVENTS")
    if override:
        return Path(override)
    for candidate in (Path.home() / ".hermes/sips/hook_events.jsonl",
                      Path.home() / ".codex/sips/hook_events.jsonl"):
        if candidate.exists():
            return candidate
    return Path.home() / ".hermes/sips/hook_events.jsonl"


def load_lifecycle() -> dict:
    path = _hook_events_path()
    tools: collections.Counter = collections.Counter()
    statuses: collections.Counter = collections.Counter()
    buckets: collections.Counter = collections.Counter()  # 6h epoch buckets
    sessions: set = set()
    first = last = None
    with path.open() as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("tool_name"):
                tools[d["tool_name"]] += 1
            if d.get("status"):
                statuses[d["status"]] += 1
            sid = d.get("session_id")
            if sid:
                sessions.add(sid)
            ts = d.get("ts")
            if ts:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    epoch = dt.timestamp()
                    if first is None or epoch < first:
                        first = epoch
                    if last is None or epoch > last:
                        last = epoch
                    buckets[int(epoch // 21600)] += 1
                except ValueError:
                    pass
    return {
        "tools": dict(tools),
        "statuses": dict(statuses),
        "buckets": dict(sorted(buckets.items())),
        "sessions": len(sessions),
        "window": {"first": first, "last": last},
    }


def _sparkline_svg(buckets: dict[int, int], width: int = 520, height: int = 44) -> str:
    if not buckets:
        return ""
    values = list(buckets.values())
    vmax = max(values) or 1
    n = len(values)
    step = width / max(n - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - 4 - (v / vmax) * (height - 10)
        pts.append((round(x, 1), round(y, 1)))
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"M0,{height} L" + " L".join(f"{x},{y}" for x, y in pts) + f" L{width},{height} Z"
    from datetime import datetime, timezone
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="2" fill="var(--accent, #3b82f6)"><title>'
        f'{datetime.fromtimestamp(b, tz=timezone.utc):%m-%d %H:%M} — {v} events</title></circle>'
        for (x, y), (b, v) in zip(pts, buckets.items())
    )
    return f"""<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="activity">
  <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="var(--accent, #3b82f6)" stop-opacity="0.25"/>
    <stop offset="1" stop-color="var(--accent, #3b82f6)" stop-opacity="0"/>
  </linearGradient></defs>
  <path d="{area}" fill="url(#sg)"/>
  <polyline points="{line}" fill="none" stroke="var(--accent, #3b82f6)" stroke-width="1.5"
    stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
  {dots}
</svg>"""


def render_lifecycle(data: dict) -> str:
    tools: dict = data.get("tools", {})
    statuses: dict = data.get("statuses", {})
    buckets: dict = data.get("buckets", {})
    sessions = data.get("sessions", 0)
    total = sum(tools.values()) or 1
    top = sorted(tools.items(), key=lambda kv: -kv[1])[:8]

    bars = "".join(
        f'<div class="bar" title="{escape(name)}: {count} calls">'
        f'<span class="name">{escape(name)}</span>'
        f'<span class="track"><i style="width:{round(count / top[0][1] * 100)}%"></i></span>'
        f'<span class="val num">{count}</span></div>'
        for name, count in top
    )

    blocked = statuses.get("blocked", 0)
    ok = statuses.get("ok", 0) + statuses.get("allowed", 0)
    status_chips = (
        _chip(f"{ok} ok", "good")
        + (f" {_chip(f'{blocked} blocked', 'bad')}" if blocked else "")
        + f" {_chip(f'{sessions} sessions')}"
    )

    from datetime import datetime, timezone
    first = data.get("window", {}).get("first")
    last_t = data.get("window", {}).get("last")
    span = ""
    if first and last_t:
        days = max((last_t - first) / 86400, 0.04)
        span = f"{datetime.fromtimestamp(first, tz=timezone.utc):%b %d} – {datetime.fromtimestamp(last_t, tz=timezone.utc):%b %d} ({days:.1f}d)"

    body = f"""
  <p class="caption">SIPS hook-event stream — hover bars and sparkline dots for detail.</p>
  <div class="card">
    <div class="head">
      <span class="dot ok"></span>
      <span class="obj">Hook event lifecycle</span>
      {status_chips}
    </div>
    <div class="bars">{bars or '<p class="meta">no tool events</p>'}</div>
    <div class="spark">
      {_sparkline_svg(buckets)}
      <p class="cap num">events per 6h · {escape(span)} · <span class="num">{total}</span> tool calls</p>
    </div>
    <div class="actions">
      <button data-hermes-send="Refresh the SIPS inline lifecycle widget">Refresh</button>
    </div>
  </div>
"""
    return _page(body)


# --------------------------------------------------------------- memory ----

def _memory_store_path() -> Path:
    override = os.environ.get("CODEX_MEMORY_FABRIC_STORE")
    if override:
        return Path(override)
    return Path.home() / ".codex/memory-fabric/memory.jsonl"


def load_memory() -> dict:
    path = _memory_store_path()
    trust: collections.Counter = collections.Counter()
    tiers: collections.Counter = collections.Counter()
    recent: list[dict] = []
    total = 0
    with path.open() as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            total += 1
            trust[trust_status(d)] += 1
            tiers[d.get("tier", "unknown")] += 1
            if len(recent) < 20:
                recent.append(d)
    return {
        "total": total,
        "trust": dict(trust),
        "tiers": dict(tiers),
        "recent": recent,
    }


TIER_COLORS = {
    "learning": "#8b5cf6",
    "work": "#3b82f6",
    "knowledge": "#22c55e",
    "unknown": "#94a3b8",
}
TRUST_KIND = {
    "ready": "good",
    "usable": "accent",
    "verify_before_use": "warn",
    "unknown": "",
}


def trust_status(record: dict) -> str:
    """Normalize trust across nested (trust.status) and flat (verify_before_use) schemas."""
    nested = (record.get("trust") or {}).get("status")
    if nested:
        return nested
    return "verify_before_use" if record.get("verify_before_use") else "ready"


def _donut_svg(tiers: dict, size: int = 64, stroke: int = 9) -> str:
    total = sum(tiers.values()) or 1
    r = (size - stroke) / 2
    c = 2 * 3.14159265 * r
    offset = 0.0
    segs = []
    for tier, count in sorted(tiers.items(), key=lambda kv: -kv[1]):
        frac = count / total
        color = TIER_COLORS.get(tier, "#94a3b8")
        segs.append(
            f'<circle cx="{size / 2}" cy="{size / 2}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-dasharray="{frac * c:.2f} {c:.2f}" '
            f'stroke-dashoffset="{-offset * c:.2f}" transform="rotate(-90 {size / 2} {size / 2})">'
            f"<title>{escape(tier)}: {count}</title></circle>"
        )
        offset += frac
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="tier donut">{"".join(segs)}</svg>'


def render_memory(data: dict) -> str:
    total = data.get("total", 0)
    trust: dict = data.get("trust", {})
    tiers: dict = data.get("tiers", {})
    recent: list[dict] = data.get("recent", [])

    trust_chips = " ".join(
        _chip(f"{count} {status}", TRUST_KIND.get(status, ""))
        for status, count in sorted(trust.items(), key=lambda kv: -kv[1])
    )

    legend_rows = []
    for tier, count in sorted(tiers.items(), key=lambda kv: -kv[1]):
        color = TIER_COLORS.get(tier, "#94a3b8")
        legend_rows.append(
            f'<div class="row"><span class="sw" style="background:{color}"></span>'
            f'<span class="lbl">{escape(tier)}</span><span class="v">{count}</span></div>'
        )

    recs = []
    for d in recent[:4]:
        status = trust_status(d)
        recs.append(
            '<div class="rec" title="{body}">'
            '<span class="rt">{title}</span>{chip}</div>'.format(
                body=escape((d.get("body") or "")[:200]),
                title=escape((d.get("title") or "(untitled)")[:80]),
                chip=_chip(status, TRUST_KIND.get(status, "")),
            )
        )

    body = f"""
  <p class="caption">SIPS Memory Fabric — hover records for the claim body; trust chips are retrieval guidance, not proof.</p>
  <div class="card">
    <div class="head">
      <span class="dot running"></span>
      <span class="obj">Memory Fabric</span>
      {_chip(f"{total} records", "accent")}
    </div>
    <div class="legend">{trust_chips or '<span class="meta">no trust data</span>'}</div>
    <div class="donut-row">
      <div class="donut">{_donut_svg(tiers)}</div>
      <div class="donut-legend">{''.join(legend_rows) or '<span class="meta">no tiers</span>'}</div>
    </div>
    <div class="recent">{''.join(recs) or '<p class="meta">no records</p>'}</div>
    <div class="actions">
      <button data-hermes-send="Refresh the SIPS inline memory widget">Refresh</button>
    </div>
  </div>
"""
    return _page(body)


# ------------------------------------------------------------- selfloop ----

def load_selfloop() -> dict:
    """Read persisted selfloop goal state through the existing goal_state loader."""
    import goal_state  # same scripts dir; resolves SIPS_HOME the canonical way

    return goal_state.load() or {}


OUTCOME_KIND = {
    "improved": "good",
    "flat": "warn",
    "no_change": "warn",
    "regressed": "bad",
    "failed": "bad",
}


def render_selfloop(state: dict) -> str:
    mode = state.get("mode", "selfloop")
    focus = state.get("focus", "")
    status = state.get("status", "unknown")
    cycles = int(state.get("cycleCount", 0) or 0)
    turns = int(state.get("turnCount", 0) or 0)
    plateau = int(state.get("plateauStreak", 0) or 0)
    last = state.get("lastCycle") or {}
    history: list[dict] = state.get("cycleHistory") or []

    chips = (
        _chip(escape(str(mode)), "accent")
        + f" {_chip(f'cycle {cycles}')}"
        + f" {_chip(f'{turns} turns')}"
    )
    if plateau > 0:
        chips += f" {_chip(f'plateau {plateau}', 'warn')}"

    outcome = last.get("outcome", "unknown")
    summary = last.get("summary", "")
    last_html = ""
    if last:
        last_html = (
            f'<div class="recent" style="margin-top:10px">'
            f'<div class="rec"><span class="rt">{escape(summary or "(no summary)")}</span>'
            f"{_chip(escape(str(outcome)), OUTCOME_KIND.get(outcome, ''))}</div></div>"
        )

    rows = []
    for entry in list(reversed(history))[:8]:
        oc = entry.get("outcome", "unknown")
        oc_kind = OUTCOME_KIND.get(oc, "")
        rows.append(
            '<div class="rec" title="{summary}">'
            '<span class="sw" style="background:var(--accent, #3b82f6); border-radius:50%; width:7px; height:7px; flex:none; opacity:{op}"></span>'
            '<span class="rt">{summary}</span>'
            '<span class="st num" style="font-size:10px; color:var(--muted-foreground, #888); flex:none">c{cycle}</span>'
            "{chip}</div>".format(
                summary=escape((entry.get("summary") or "(no summary)")[:110]),
                cycle=escape(str(entry.get("cycle", "?"))),
                op="1" if oc_kind == "good" else "0.35",
                chip=_chip(escape(str(oc)), oc_kind),
            )
        )

    body = f"""
  <p class="caption">SIPS selfloop — cycle history is the proof receipt; newest first.</p>
  <div class="card">
    <div class="head">
      <span class="dot {escape(status)}"></span>
      <span class="obj">Selfloop{f" — focus: {escape(focus)}" if focus else ""}</span>
      {chips}
    </div>
    {last_html}
    <div class="recent">{''.join(rows) or '<p class="meta">no cycles recorded</p>'}</div>
    <div class="actions">
      <button data-hermes-send="Refresh the SIPS inline selfloop widget">Refresh</button>
    </div>
  </div>
"""
    return _page(body)


# --------------------------------------------------------------- fleet ----

def load_fleet() -> dict:
    """Read the campaign-fleet registry projection through the existing API."""
    import sips_paths
    from sips_runtime.campaign_fleet import CampaignFleet

    fleet = CampaignFleet(sips_paths.harness_home())
    campaigns = fleet.list(limit=24)
    children_total = sum(int(c.get("child_count", 0) or 0) for c in campaigns)
    archived_total = sum(int(c.get("archived_child_count", 0) or 0) for c in campaigns)
    statuses: dict[str, int] = {}
    for c in campaigns:
        statuses[c.get("status", "unknown")] = statuses.get(c.get("status", "unknown"), 0) + 1
    return {
        "campaigns": campaigns,
        "statuses": statuses,
        "children_total": children_total,
        "archived_total": archived_total,
    }


def render_fleet(data: dict) -> str:
    campaigns: list[dict] = data.get("campaigns", [])
    statuses: dict = data.get("statuses", {})
    children_total = data.get("children_total", 0)
    archived_total = data.get("archived_total", 0)

    chips = " ".join(
        _chip(f"{count} {status}", "accent" if status == "active" else "")
        for status, count in sorted(statuses.items())
    ) or _chip("empty fleet")

    rows = []
    for c in campaigns[:8]:
        status = c.get("status", "unknown")
        child_count = int(c.get("child_count", 0) or 0)
        arch = int(c.get("archived_child_count", 0) or 0)
        rows.append(
            '<div class="rec" title="{objective}">'
            '<span class="rt">{cid} — {objective}</span>'
            '<span class="st num" style="font-size:10px; color:var(--muted-foreground, #888); flex:none">{kids} kids{arch}</span>'
            "{chip}</div>".format(
                cid=escape(str(c.get("campaign_id", ""))[:28]),
                objective=escape(str(c.get("objective", "") or "(no objective)")[:70]),
                kids=child_count,
                arch=f" · {arch} archived" if arch else "",
                chip=_chip(escape(str(status)), "accent" if status == "active" else ""),
            )
        )
    more = len(campaigns) - len(rows)
    if more > 0:
        rows.append(f'<p class="meta">+{more} more campaign(s)</p>')

    empty = "" if campaigns else '<p class="meta">No campaigns yet — create one with homebase_campaign_fleet_write (operation=create).</p>'
    body = f"""
  <p class="caption">SIPS campaign fleet — event-backed metadata spine; external host threads remain a separate proof layer.</p>
  <div class="card">
    <div class="head">
      <span class="dot {'ok' if campaigns else 'running'}"></span>
      <span class="obj">Campaign Fleet</span>
      {chips}
    </div>
    <p class="meta num" style="margin-top:8px">{children_total} child threads · {archived_total} archived across {len(campaigns)} campaign(s)</p>
    <div class="recent">{empty}{''.join(rows)}</div>
    <div class="actions">
      <button data-hermes-send="Refresh the SIPS inline fleet widget">Refresh</button>
    </div>
  </div>
"""
    return _page(body)


RENDERERS = {
    "board": (load_board, render_board),
    "lifecycle": (load_lifecycle, render_lifecycle),
    "memory": (load_memory, render_memory),
    "selfloop": (load_selfloop, render_selfloop),
    "fleet": (load_fleet, render_fleet),
}


# --------------------------------------------------- panel-facing probes ----

def widget_kinds() -> list[str]:
    """Sorted widget kinds, derived from RENDERERS — never hardcoded elsewhere."""
    return sorted(RENDERERS)


def widget_brief(kind: str) -> dict[str, Any]:
    """Cheap availability probe for one widget kind, without rendering.

    Runs the kind's loader (bounded, read-only) and reports whether a render
    would succeed right now. Never raises — failures become available:false.
    """
    if kind not in RENDERERS:
        return {"kind": kind, "available": False, "note": "unknown widget kind"}
    loader, _renderer = RENDERERS[kind]
    try:
        loader()
    except Exception as exc:  # noqa: BLE001 - the probe must never raise
        return {"kind": kind, "available": False, "note": f"{type(exc).__name__}: {exc}"}
    return {"kind": kind, "available": True}


# ------------------------------------------------------- mcp tool surface ----

WIDGET_SUMMARY_KEYS = {
    "board": ("status", "objective", "revision", "progress"),
    "lifecycle": ("sessions",),
    "memory": ("total",),
    "selfloop": ("mode", "focus", "status", "cycleCount", "turnCount"),
    "fleet": ("statuses", "children_total", "archived_total"),
}


def widget_payload(kind: str) -> dict[str, Any]:
    """Render a widget to the SIPS home widgets dir and return the inline directive.

    Writes a static HTML render (derived view only; no state mutation) so the
    host agent can emit ::preview{file="..."} inline in chat.
    """
    if kind not in RENDERERS:
        raise KeyError(kind)
    import sips_paths

    loader, renderer = RENDERERS[kind]
    data = loader()
    html = renderer(data)
    out = sips_paths.harness_home() / "widgets" / f"{kind}-widget.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    summary = {key: data.get(key) for key in WIDGET_SUMMARY_KEYS[kind] if key in data}
    return {
        "schema": "sips.inline-widget.v1",
        "ok": True,
        "kind": kind,
        "path": str(out),
        "media": f"MEDIA:{out}",
        "directive": f'::preview{{file="{out}"}}',
        "summary": summary,
        "claim_boundary": "Static HTML render of state at generation time; it does not execute, verify, or authorize anything. Re-invoke to refresh.",
    }


def widget_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SIPS Inline Widget",
        "",
        f"- **kind** `{payload.get('kind')}`",
        f"- **path** `{payload.get('path')}`",
        "- **deliver** put this directive on its own line in the chat reply:",
        "",
        "```",
        payload.get("directive", ""),
        "```",
        "",
        "## Summary",
        "",
    ]
    for key, value in (payload.get("summary") or {}).items():
        lines.append(f"- **{key}** `{value}`")
    lines += ["", f"> {payload.get('claim_boundary', '')}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(RENDERERS), nargs="?", default="board")
    parser.add_argument("--out", type=Path, default=None, help="Output HTML path")
    args = parser.parse_args(argv)

    loader, renderer = RENDERERS[args.kind]
    data = loader()
    html = renderer(data)

    out = args.out
    if out is None:
        out = Path.cwd() / f"sips-{args.kind}-widget.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"MEDIA:{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
