from __future__ import annotations
from memory_fabric_capture import capture_representative_usage
from memory_fabric_measurement import measurement_plan
from memory_fabric_mcp_args import optional_paths
from memory_fabric_telemetry_audit import telemetry_audit
from memory_fabric_telemetry_contract import telemetry_contract
from memory_fabric_telemetry_status import telemetry_status
from memory_fabric_token_coverage import token_coverage
from memory_fabric_usage import usage_report


def register_telemetry_tool(mcp, dumps):
    @mcp.tool()
    def memory_fabric_telemetry(
        operation: str,
        output: str = "",
        store: str = "",
        input_path: str = "",
        operations_input: str = "",
        usage_input: str = "",
        inline_json: str = "",
        plugin_eval_output: str = "",
        min_samples: int = 5,
        min_scenarios: int = 3,
        sample_limit: int = 20,
        allow_nonrepresentative_export: bool = False,
    ):
        return dumps(
            telemetry_operation(
                operation=operation,
                output=output,
                store=store,
                input_path=input_path,
                operations_input=operations_input,
                usage_input=usage_input,
                inline_json=inline_json,
                plugin_eval_output=plugin_eval_output,
                min_samples=min_samples,
                min_scenarios=min_scenarios,
                sample_limit=sample_limit,
                allow_nonrepresentative_export=allow_nonrepresentative_export,
            )
        )


def telemetry_operation(operation, **kwargs):
    key = operation.strip().replace("-", "_")
    handler = telemetry_handlers().get(key)
    return handler(kwargs) if handler else unknown_operation()


def telemetry_handlers():
    return {
        "audit": telemetry_audit_operation,
        "capture": telemetry_capture_operation,
        "contract": telemetry_contract_operation,
        "coverage": telemetry_coverage_operation,
        "measurement_plan": telemetry_measurement_plan_operation,
        "status": telemetry_status_operation,
        "usage_report": telemetry_usage_report_operation,
    }


def telemetry_measurement_plan_operation(args):
    return measurement_plan(
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
        usage_input=args["input_path"] or "/tmp/codex-memory-fabric-usage.jsonl",
        plugin_eval_output=args["plugin_eval_output"] or "/tmp/codex-memory-fabric-plugin-eval-usage.jsonl",
    )


def telemetry_capture_operation(args):
    return capture_representative_usage(
        output=args["output"],
        store=args["store"],
        min_scenarios=args["min_scenarios"],
    )


def telemetry_contract_operation(args):
    return telemetry_contract(
        output=args["output"],
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
    )


def telemetry_status_operation(args):
    return telemetry_status(
        operations_input=args["operations_input"],
        usage_input=optional_paths(args["usage_input"]),
        inline_json=args["inline_json"],
        plugin_eval_output=args["plugin_eval_output"],
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
    )


def telemetry_audit_operation(args):
    return telemetry_audit(
        usage_input=optional_paths(args["usage_input"]),
        inline_json=args["inline_json"],
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
        sample_limit=args["sample_limit"],
    )


def telemetry_coverage_operation(args):
    return token_coverage(
        operations_input=args["operations_input"],
        usage_input=optional_paths(args["usage_input"]),
        inline_json=args["inline_json"],
        plugin_eval_output=args["plugin_eval_output"],
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
    )


def telemetry_usage_report_operation(args):
    return usage_report(
        paths=optional_paths(args["input_path"]),
        inline_json=args["inline_json"],
        plugin_eval_output=args["plugin_eval_output"],
        min_samples=args["min_samples"],
        min_scenarios=args["min_scenarios"],
        allow_nonrepresentative_export=args["allow_nonrepresentative_export"],
    )


def unknown_operation():
    return {
        "ok": False,
        "status": "unknown_telemetry_operation",
        "supported_operations": sorted(telemetry_handlers()),
    }
