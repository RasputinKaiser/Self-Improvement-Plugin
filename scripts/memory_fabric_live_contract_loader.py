from __future__ import annotations
import ast
from pathlib import Path


TOOL_MODULES = ("memory_fabric_mcp.py", "memory_fabric_mcp_telemetry.py", "memory_fabric_mcp_install.py")


def load_surface_contract(base: Path) -> tuple[list[str], dict[str, set[str]]]:
    required: list[str] = []
    expected: dict[str, set[str]] = {}
    for module in TOOL_MODULES:
        merge_tools(required, expected, module_tools(base.with_name(module)))
    return required, expected


def merge_tools(
    required: list[str],
    expected: dict[str, set[str]],
    tools: list[tuple[str, list[str]]],
) -> None:
    for name, params in tools:
        if name not in required:
            required.append(name)
        if params:
            expected[name] = set(params)


def module_tools(path: Path) -> list[tuple[str, list[str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tools: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("memory_fabric_"):
            tools.append((node.name, [arg.arg for arg in node.args.args]))
    return tools
