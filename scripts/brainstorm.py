#!/usr/bin/env python3
"""Brainstorm — survey current capabilities and identify gaps.

Reads the capability map at references/capability_map.md, surveys the actual
installed state (scripts, hooks, agents, commands, app panes), and returns
a ranked list of 3-5 gaps with effort + leverage scores.

Usage:
  brainstorm.py              # markdown report
  brainstorm.py --json       # machine-readable
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path.home() / ".ncode/plugins/marketplaces/harness-local"
CAPABILITY_MAP = Path.home() / "Code/harness-self-improvement/references/capability_map.md"

# Capability areas that are checked items (shipped) vs unchecked (gaps)
# The brainstorm script reads the map and finds unchecked items in Tier 3+.


def read_capability_map():
    """Parse capability_map.md, return list of (tier, name, shipped, area)."""
    if not CAPABILITY_MAP.exists():
        return []
    content = CAPABILITY_MAP.read_text(encoding="utf-8")
    entries = []
    current_tier = "?"
    for line in content.split("\n"):
        m = re.match(r"^## (Tier \d+)", line)
        if m:
            current_tier = m.group(1)
            continue
        m = re.match(r"^- \[([ x])\]\s+(.+)", line)
        if m:
            shipped = m.group(1) == "x"
            name = m.group(2).strip()
            entries.append({
                "tier": current_tier,
                "name": name,
                "shipped": shipped,
            })
    return entries


def survey_installed():
    """Count what's actually installed: scripts, hooks, agents, commands."""
    scripts_dir = PLUGIN_ROOT / "scripts"
    agents_dir = PLUGIN_ROOT / "agents"
    commands_dir = PLUGIN_ROOT / "commands"
    hooks_file = PLUGIN_ROOT / "hooks/hooks.json"

    script_count = len(list(scripts_dir.glob("*.py"))) + len(list(scripts_dir.glob("*.sh"))) if scripts_dir.exists() else 0
    agent_count = len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0
    command_count = len(list(commands_dir.glob("*.md"))) if commands_dir.exists() else 0

    hook_count = 0
    if hooks_file.exists():
        try:
            d = json.loads(hooks_file.read_text())
            for blocks in d.get("hooks", {}).values():
                for block in blocks:
                    hook_count += len(block.get("hooks", []))
        except json.JSONDecodeError:
            pass

    return {
        "scripts": script_count,
        "hooks": hook_count,
        "agents": agent_count,
        "commands": command_count,
    }


def survey_app():
    """Check if harness-app exists and count its panes."""
    app_dir = Path.home() / "Code/harness-self-improvement"
    app_src = Path.home() / "Code/harness-app/Sources/HarnessApp"
    if not app_src.exists():
        return None
    swift_files = list(app_src.rglob("*.swift"))
    pane_files = list((app_src / "Views").glob("*Pane.swift")) + list((app_src / "Views").glob("*View.swift"))
    return {
        "swift_files": len(swift_files),
        "panes": len(pane_files),
        "pane_names": [p.stem for p in pane_files],
    }


def find_gaps(capability_map, installed, app):
    """Cross-reference capability map against installed state."""
    gaps = []
    for entry in capability_map:
        if entry["shipped"]:
            continue
        # Skip Tier 4 (future) unless explicitly requested
        if "Tier 4" in entry["tier"]:
            # Only skip if we already have enough Tier 3 gaps
            if len(gaps) >= 3:
                continue

        name = entry["name"]

        # Score: leverage (how much does it unlock?) + effort (how hard to build?)
        leverage = 5
        effort = "medium"
        area = "General"

        lower = name.lower()

        if "browser use" in lower or "in-app browser" in lower and "use" in lower:
            leverage = 9
            effort = "medium"
            area = "External surfaces"
        elif "vision" in lower or "screenshot" in lower:
            leverage = 8
            effort = "medium"
            area = "External surfaces"
        elif "computer use" in lower:
            leverage = 9
            effort = "high"
            area = "External surfaces"
        elif "live session attach" in lower:
            leverage = 7
            effort = "high"
            area = "Interaction"
        elif "multi-agent" in lower or "orchestration" in lower:
            leverage = 7
            effort = "medium"
            area = "Multi-agent"
        elif "plan approval" in lower:
            leverage = 5
            effort = "low"
            area = "Interaction"
        elif "scheduled" in lower or "cron" in lower:
            leverage = 4
            effort = "low"
            area = "Self-improvement"
        elif "cost" in lower or "budget" in lower:
            leverage = 6
            effort = "low"
            area = "Safety"
        elif "mcp" in lower and "browser" in lower:
            leverage = 5
            effort = "medium"
            area = "External surfaces"
        elif "voice" in lower:
            leverage = 4
            effort = "medium"
            area = "Interaction"
        elif "worktree" in lower:
            leverage = 3
            effort = "medium"
            area = "Action"
        elif "skill" in lower and "market" in lower:
            leverage = 4
            effort = "medium"
            area = "External surfaces"
        elif "evaluation" in lower or "benchmark" in lower:
            leverage = 5
            effort = "high"
            area = "Self-improvement"
        elif "telemetry" in lower or "dashboard" in lower:
            leverage = 4
            effort = "low"
            area = "Observation"
        elif "prompt" in lower and "template" in lower:
            leverage = 3
            effort = "low"
            area = "Interaction"
        elif "scheduled" in lower or "cron" in lower:
            leverage = 4
            effort = "low"
            area = "Self-improvement"

        gaps.append({
            "name": name,
            "tier": entry["tier"],
            "leverage": leverage,
            "effort": effort,
            "area": area,
        })

    # Sort by leverage desc, then effort asc
    effort_order = {"low": 0, "medium": 1, "high": 2}
    gaps.sort(key=lambda g: (-g["leverage"], effort_order.get(g["effort"], 1)))
    return gaps[:5]  # top 5


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    capability_map = read_capability_map()
    installed = survey_installed()
    app = survey_app()
    gaps = find_gaps(capability_map, installed, app)

    if args.json:
        print(json.dumps({
            "installed": installed,
            "app": app,
            "gaps": gaps,
            "total_capabilities": len(capability_map),
            "shipped_count": sum(1 for e in capability_map if e["shipped"]),
            "gap_count": len(gaps),
        }, indent=2))
        return

    print("# Brainstorm — Capability Gap Survey\n")
    print(f"**Installed:** {installed['scripts']} scripts · {installed['hooks']} hooks · "
          f"{installed['agents']} agents · {installed['commands']} commands")
    if app:
        print(f"**App:** {app['swift_files']} Swift files · {app['panes']} panes")
    print(f"**Capability map:** {sum(1 for e in capability_map if e['shipped'])}/{len(capability_map)} shipped\n")

    if not gaps:
        print("_No gaps found — all Tier 3 capabilities are shipped._")
        return

    print(f"## Top {len(gaps)} gaps (ranked by leverage)\n")
    for i, gap in enumerate(gaps, 1):
        print(f"{i}. **{gap['name']}** ({gap['tier']})")
        print(f"   - Leverage: {gap['leverage']}/10")
        print(f"   - Effort: {gap['effort']}")
        print(f"   - Area: {gap['area']}")
        print()


if __name__ == "__main__":
    main()
    sys.exit(0)