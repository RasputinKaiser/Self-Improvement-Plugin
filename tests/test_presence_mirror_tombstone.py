from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOMBSTONE = ROOT / "scripts" / "sips_presence_mirror.py"


def test_retired_presence_mirror_path_is_silent_and_inert(tmp_path):
    source = tmp_path / ".codex" / "sips"
    source.mkdir(parents=True)
    (source / "chat-presence.md").write_text("active state\n", encoding="utf-8")

    run = subprocess.run(
        ["python3", str(TOMBSTONE)],
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert run.returncode == 0, run.stderr
    assert run.stdout == ""
    assert run.stderr == ""
    assert not (tmp_path / ".ncode").exists()
