#!/usr/bin/env python3
"""Harness validator for ~/.ncode/.

Read-only. Reports:
- skills referenced in NCODE.md that don't exist
- agents/commands referenced but missing
- scripts referenced but missing or non-executable
- reference docs linked from NCODE.md that don't exist
- malformed settings.local.json
- skills missing SKILL.md or frontmatter

Exit 0 if clean, 1 if drift found.
"""
import json
import os
import re
import sys
from pathlib import Path

NCODE_DIR = Path.home() / ".ncode"
NCODE_MD = Path.home() / "NCODE.md"
SETTINGS_LOCAL = NCODE_DIR / "settings.local.json"
SETTINGS_GLOBAL = NCODE_DIR / "settings.json"

findings = []


def add(level, msg):
    findings.append((level, msg))


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


content = read(NCODE_MD)
if not content:
    add("ERR", f"{NCODE_MD} missing")

# Extract link/file references: paths/strings ending in .md, agents/, skills/, scripts/, references/
# Only treat strings starting with .ncode/, /, ~/ or references/ as path refs.
ref_pat = re.compile(r"(?:~/\.ncode/|/Users/[^)]+?\.ncode/|\.ncode/|references/)[^)\s`'\"]+")
backtick_pat = re.compile(r"`([a-z][a-z0-9_-]+\.(?:py|md|sh))`")
matches = set(ref_pat.findall(content))
backticks = set(backtick_pat.findall(content))

# Normalize: extract relative paths under .ncode referring to scripts/skills/agents/commands/references
# Skip paths inside settings.json — settings.json is a referenced-as-do-not-edit, not a script target.
# Skip glob patterns (*.py, ?[...]) and brace expansions — they're matchers, not literal paths.
skip_patterns = ("settings.json", "settings.local.json")
glob_chars = ("*", "?", "[", "{")
checks = set()
for m in matches:
    if m.endswith(tuple(skip_patterns)) or any(s in m for s in skip_patterns):
        continue
    if any(c in m for c in glob_chars):
        continue
    p = m
    if p.startswith("~"):
        p = str(Path(p).expanduser())
    elif p.startswith(".ncode/"):
        p = str(Path.home() / p)
    elif p.startswith("references/"):
        p = str(NCODE_DIR / p)
    elif p.startswith("/Users/"):
        pass
    else:
        continue
    checks.add(Path(p))

# Also detect skill/agent/script names mentioned in backticks
for b in backticks:
    # Look for it under scripts/, references/
    for sub in ("scripts", "references", "agents", "skills"):
        cand = NCODE_DIR / sub / b
        if cand.exists():
            checks.add(cand)
            break

for p in checks:
    if not p.exists():
        add("ERR", f"NCODE.md references missing path: {p}")

# Validate skills
skills_dir = NCODE_DIR / "skills"
if skills_dir.is_dir():
    for d in skills_dir.iterdir():
        if not d.is_dir():
            continue
        sm = d / "SKILL.md"
        if not sm.exists():
            add("ERR", f"skill '{d.name}' missing SKILL.md")
            continue
        body = read(sm)
        if not body.startswith("---"):
            add("WARN", f"skill '{d.name}' SKILL.md missing frontmatter")
        else:
            fm = body.split("---", 2)[1] if body.count("---") >= 2 else ""
            if "name:" not in fm or "description:" not in fm:
                add("WARN", f"skill '{d.name}' SKILL.md frontmatter incomplete")

# Validate agents
agents_dir = NCODE_DIR / "agents"
if agents_dir.is_dir():
    for f in agents_dir.iterdir():
        if f.suffix == ".md":
            body = read(f)
            if not body.startswith("---"):
                add("WARN", f"agent '{f.name}' missing frontmatter")

# Validate settings.local.json
if SETTINGS_LOCAL.exists():
    try:
        json.loads(SETTINGS_LOCAL.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        add("ERR", f"settings.local.json malformed: {e}")

# Validate scripts are executable
scripts_dir = NCODE_DIR / "scripts"
if scripts_dir.is_dir():
    for f in scripts_dir.iterdir():
        if f.suffix == ".py" and not os.access(f, os.X_OK):
            add("INFO", f"script {f.name} not executable (chmod +x)")

# Ensure references exist
refs_dir = NCODE_DIR / "references"
if refs_dir.is_dir():
    for f in refs_dir.iterdir():
        if f.suffix == ".md" and not f.read_text(encoding="utf-8", errors="ignore").strip():
            add("WARN", f"reference doc empty: {f.name}")

# Report
errs = [f for lvl, f in findings if lvl == "ERR"]
warns = [f for lvl, f in findings if lvl == "WARN"]
infos = [f for lvl, f in findings if lvl == "INFO"]

for level, msg in findings:
    print(f"[{level}] {msg}")

print(f"\nsummary: {len(errs)} errors, {len(warns)} warnings, {len(infos)} info")

sys.exit(1 if errs else 0)