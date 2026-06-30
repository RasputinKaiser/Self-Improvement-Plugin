from __future__ import annotations
import re


def tool_present(required: str, advertised_tools: list[str]) -> bool:
    return any(tool_matches(required, advertised) for advertised in advertised_tools)


def tool_matches(required: str, advertised: str) -> bool:
    return advertised == required or advertised.endswith("." + required) or advertised.endswith("__" + required)


def tool_aliases(required: str, advertised_tools: list[str]) -> list[str]:
    return [advertised for advertised in advertised_tools if tool_alias_matches(required, advertised)]


def present_tools(required_tools: list[str], advertised_tools: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    present = []
    aliased = {}
    for tool in required_tools:
        if tool_present(tool, advertised_tools):
            present.append(tool)
            continue
        aliases = tool_aliases(tool, advertised_tools)
        if aliases:
            present.append(tool)
            aliased[tool] = aliases
    return present, aliased


def tool_alias_matches(required: str, advertised: str) -> bool:
    name = advertised_name(advertised)
    suffix = name.removeprefix(required + "_")
    return name != suffix and bool(re.fullmatch(r"[0-9a-f]{12,}", suffix))


def advertised_name(advertised: str) -> str:
    if "." in advertised:
        return advertised.rsplit(".", 1)[-1]
    if "__" in advertised:
        return advertised.rsplit("__", 1)[-1]
    return advertised


def canonical_tool_name(advertised: str, required_tools: list[str]) -> str:
    for required in required_tools:
        if tool_matches(required, advertised) or tool_alias_matches(required, advertised):
            return required
    return ""
