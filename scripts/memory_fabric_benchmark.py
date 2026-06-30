#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
IMPL = ROOT / "fixtures" / "benchmarks" / "policy_benchmark.py"


def load_impl() -> Any:
    import sys

    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("policy_benchmark", IMPL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_benchmark(store: Path) -> dict[str, Any]:
    return load_impl().run_benchmark(store)


def main(argv: list[str] | None = None) -> int:
    return load_impl().main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
