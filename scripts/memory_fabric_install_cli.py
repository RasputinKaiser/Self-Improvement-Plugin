from __future__ import annotations
import shutil
import subprocess
from typing import Any


def check_cli(codex_command: str) -> dict[str, Any]:
    path = shutil.which(codex_command)
    if not path:
        return missing_cli(codex_command)
    try:
        result = run_plugin_help(path)
    except subprocess.TimeoutExpired:
        return timed_out_cli(codex_command, path)
    output = result.stdout or ""
    return {
        "ok": result.returncode == 0,
        "command": codex_command,
        "path": path,
        "returncode": result.returncode,
        "plugin_add_available": subcommand_available(output, "add"),
        "plugin_list_available": subcommand_available(output, "list"),
        "plugin_help_excerpt": "\n".join(output.splitlines()[:12]),
    }


def missing_cli(codex_command: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": codex_command,
        "path": "",
        "plugin_add_available": False,
        "plugin_list_available": False,
    }


def timed_out_cli(codex_command: str, path: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": codex_command,
        "path": path,
        "plugin_add_available": False,
        "plugin_list_available": False,
        "error": "codex plugin --help timed out after 5 seconds",
    }


def run_plugin_help(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [path, "plugin", "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=5,
    )


def subcommand_available(output: str, name: str) -> bool:
    return f" {name}" in output and "Commands:" in output
