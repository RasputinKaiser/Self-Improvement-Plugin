from __future__ import annotations

import subprocess
from types import SimpleNamespace

import harness_browser_mcp as browser_mcp


def test_browser_see_runs_local_vlm_and_returns_description(monkeypatch):
    responses = []
    commands = []

    monkeypatch.setattr(
        browser_mcp,
        "send_command",
        lambda tool, args: {
            "ok": True,
            "result": {
                "path": "/tmp/browser-see.png",
                "width": 800,
                "height": 600,
            },
        },
    )
    monkeypatch.setattr(
        browser_mcp,
        "write_mcp_response",
        lambda msg_id, result: responses.append((msg_id, result)),
    )

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(stdout="A settings page is visible.", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    browser_mcp._handle_browser_see(5, {"question": "What is visible?"})

    command, kwargs = commands[0]
    assert command[0] == "python3"
    assert command[1].endswith("/vision/see.py")
    assert command[2:] == ["/tmp/browser-see.png", "-q", "What is visible?"]
    assert kwargs == {"capture_output": True, "text": True, "timeout": 60}
    assert responses == [
        (
            5,
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Screenshot: /tmp/browser-see.png (800x600px)\n\n"
                            "VLM description:\nA settings page is visible."
                        ),
                    }
                ],
                "isError": False,
            },
        )
    ]
