from __future__ import annotations
import argparse
import inspect
from typing import Any, Callable


ArgSpec = tuple[str, dict[str, Any]]


def arg(name: str, **kwargs: Any) -> ArgSpec:
    return name, kwargs


def add_args(parser: argparse.ArgumentParser, specs: list[ArgSpec]) -> None:
    for name, kwargs in specs:
        parser.add_argument(name, **kwargs)


def arg_specs_from_signature(func: Callable[..., Any], names: str) -> list[ArgSpec]:
    signature = inspect.signature(func)
    return [
        arg(f"--{name.replace('_', '-')}", **arg_kwargs(signature.parameters[name]))
        for name in names.split()
    ]


def arg_kwargs(parameter: inspect.Parameter) -> dict[str, Any]:
    if parameter.default is inspect.Parameter.empty:
        return {"required": True}
    default = parameter.default
    if isinstance(default, bool):
        return bool_kwargs(default)
    if isinstance(default, int):
        return {"type": int, "default": default}
    if isinstance(default, float):
        return {"type": float, "default": default}
    if parameter.name == "usage_input":
        return {"action": "append", "default": []}
    return {"default": default}


def bool_kwargs(default: bool) -> dict[str, Any]:
    if default:
        return {"action": "store_false"}
    return {"action": "store_true"}
