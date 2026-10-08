"""Smoke-check MCP stdio discovery; the ModelDesk status probe is opt-in."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from modeldesk_mcp.contracts import public_error_message
from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES


@dataclass(frozen=True, slots=True)
class SmokeOptions:
    """Options for the non-mutating MCP smoke client."""

    include_com_status: bool
    timeout_seconds: int


def main(argv: list[str] | None = None) -> int:
    """Run the smoke client and return a process exit code."""

    options = _parse_args(argv)
    try:
        anyio.run(_run_smoke, options)
    except Exception as exception:  # noqa: BLE001 - command-line boundary.
        print(f"Smoke failed: {public_error_message(exception)}", file=sys.stderr)
        return 1
    return 0


async def _run_smoke(options: SmokeOptions) -> None:
    project_root = Path(__file__).resolve().parents[2]
    parameters = StdioServerParameters(command=sys.executable, args=["server.py"], cwd=project_root)
    async with stdio_client(parameters) as (read_stream, write_stream):
        timeout = float(options.timeout_seconds)
        async with ClientSession(read_stream, write_stream, read_timeout_seconds=timeout) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = tuple(tool.name for tool in tools_result.tools)
            _assert_expected_tools(tool_names)

            workflow_result = await session.call_tool(
                "modeldesk_get_workflow_plan",
                {"workflowName": "automation_session_smoke"},
                read_timeout_seconds=timeout,
            )
            _assert_successful_tool_call(workflow_result, "modeldesk_get_workflow_plan")

            if options.include_com_status:
                status_result = await session.call_tool(
                    "modeldesk_get_status",
                    {},
                    read_timeout_seconds=timeout,
                )
                _assert_successful_tool_call(status_result, "modeldesk_get_status")

    print(f"Smoke passed: discovered {len(tool_names)} tools and workflow plan invocation succeeded.")


def _assert_expected_tools(tool_names: tuple[str, ...]) -> None:
    missing_tools = tuple(name for name in EXPECTED_TOOL_NAMES if name not in tool_names)
    unexpected_tools = tuple(name for name in tool_names if name not in EXPECTED_TOOL_NAMES)
    if missing_tools or unexpected_tools or len(tool_names) != len(EXPECTED_TOOL_NAMES):
        raise RuntimeError(
            "Unexpected MCP tool surface. "
            f"Expected={len(EXPECTED_TOOL_NAMES)}, actual={len(tool_names)}, "
            f"missing={missing_tools}, unexpected={unexpected_tools}."
        )


def _assert_successful_tool_call(result: Any, operation_name: str) -> None:
    _assert_tool_call_completed(result, operation_name)
    structured_content = getattr(result, "structured_content", None)
    if structured_content is None:
        structured_content = getattr(result, "structuredContent", None)
    if not isinstance(structured_content, dict):
        raise RuntimeError(f"Tool '{operation_name}' did not return structured content.")
    if structured_content.get("ok") is not True:
        raise RuntimeError(f"Tool '{operation_name}' returned an unsuccessful ToolResult: {structured_content}.")


def _assert_tool_call_completed(result: Any, operation_name: str) -> None:
    is_error = getattr(result, "is_error", None)
    if is_error is None:
        is_error = getattr(result, "isError", False)
    if is_error:
        raise RuntimeError(f"Tool '{operation_name}' returned an MCP-level error: {result}.")


def _parse_args(argv: list[str] | None) -> SmokeOptions:
    parser = argparse.ArgumentParser(description="Smoke test the ModelDesk MCP stdio server.")
    status_group = parser.add_mutually_exclusive_group()
    status_group.add_argument(
        "--skip-com-status",
        action="store_true",
        help="Skip modeldesk_get_status so smoke discovery does not require ModelDesk COM.",
    )
    status_group.add_argument(
        "--include-com-status",
        action="store_true",
        help="Also call modeldesk_get_status after non-COM discovery checks.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Per-call MCP timeout in seconds.")
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")
    include_com_status = bool(args.include_com_status and not args.skip_com_status)
    return SmokeOptions(include_com_status, args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
