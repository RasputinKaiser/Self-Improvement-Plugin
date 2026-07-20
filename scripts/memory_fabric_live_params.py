from __future__ import annotations
from typing import Any


SCHEMA_KEYS = ["params", "parameters", "input_schema", "inputSchema", "schema"]


def param_names(definition: Any) -> set[str]:
    if isinstance(definition, list):
        return {str(item) for item in definition}
    if not isinstance(definition, dict):
        return set()
    return first_schema_params(definition) or params_from_value(definition)


def first_schema_params(definition: dict[str, Any]) -> set[str]:
    for key in SCHEMA_KEYS:
        names = params_from_value(definition.get(key))
        if names:
            return names
    return set()


def params_from_value(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        return params_from_dict(value)
    return set()


def params_from_dict(value: dict[str, Any]) -> set[str]:
    properties = value.get("properties")
    if isinstance(properties, dict):
        return set(properties)
    return {key for key, item in value.items() if isinstance(item, (dict, list, str))}
