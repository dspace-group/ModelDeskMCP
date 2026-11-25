"""MCPServer stdio server for ModelDesk Automation."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
import hashlib
import hmac
import json
import logging
from secrets import randbits, token_bytes
import sys
from time import perf_counter
from typing import Any
from uuid import uuid4

import anyio
from jsonschema import Draft202012Validator
from mcp import MCPError
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.types import INVALID_PARAMS, CallToolResult, InputRequiredResult, TextContent, Tool
from opentelemetry import context as otel_context, trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from modeldesk_mcp import __version__
from modeldesk_mcp.contracts import ToolError, ToolResult
from modeldesk_mcp.contracts.models import PreviewInspection
from modeldesk_mcp.tools.preview import PREVIEW_EFFECTS, build_preview
from modeldesk_mcp.tools.registry import input_schema_conditions


_AUDIT_LOGGER = logging.getLogger("modeldesk_mcp.invocations")
_TRACE_PROPAGATOR = TraceContextTextMapPropagator()
_REPLAYABLE_TOOLS = frozenset({"modeldesk_get_workflow_plan", "modeldesk_list_tools_by_use_case"})


class ModelDeskMcpServer(MCPServer):
    def __init__(self, preview_inspector: Callable[[str, dict[str, Any]], PreviewInspection] | None = None) -> None:
        super().__init__("ModelDesk Automation", version=__version__)
        self._validators: dict[str, Draft202012Validator] | None = None
        self._tool_descriptions: dict[str, str] = {}
        self._audit_key = token_bytes(32)
        self._server_session = str(uuid4())
        self._preview_inspector = preview_inspector
        self.middleware.append(self._audit_invocation)

    async def list_tools(self) -> list[Tool]:
        tools = []
        for tool in await super().list_tools():
            schema = {**tool.input_schema, "additionalProperties": False}
            conditions = input_schema_conditions(tool.name)
            if conditions:
                schema["allOf"] = conditions
            description = tool.description or ""
            if tool.name in PREVIEW_EFFECTS:
                schema["properties"] = {**schema.get("properties", {}),
                    "dryRun": {
                        "type": "boolean", "default": False, "examples": [True],
                        "description": "Preview the requested target and effects without applying changes.",
                    },
                    "inspectLive": {
                        "type": "boolean", "default": False, "examples": [True],
                        "description": "With dryRun=true, inspect an already-running ModelDesk instance without starting it or applying changes.",
                    },
                }
                schema.setdefault("allOf", []).append({
                    "if": {"required": ["inspectLive"], "properties": {"inspectLive": {"const": True}}},
                    "then": {"required": ["dryRun"], "properties": {"dryRun": {"const": True}}},
                })
                description += "\n\nUse dryRun=true to preview effects offline. Add inspectLive=true to read current state without starting ModelDesk."
            tools.append(tool.model_copy(update={"input_schema": schema, "description": description}))
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context | None = None
    ) -> CallToolResult | InputRequiredResult:
        if self._validators is None:
            tools = await self.list_tools()
            self._validators = {tool.name: Draft202012Validator(tool.input_schema) for tool in tools}
            self._tool_descriptions = {tool.name: tool.description or "" for tool in tools}
        validator = self._validators.get(name)
        if validator is None:
            raise MCPError(INVALID_PARAMS, "Unknown tool name.")
        messages = []
        for error in validator.iter_errors(arguments):
            location = ".".join(map(str, error.absolute_path)) or "arguments"
            if error.validator == "additionalProperties" and isinstance(error.instance, dict):
                unknown = error.instance.keys() - error.schema.get("properties", {}).keys()
                message = f"Unknown parameter(s) at {location}: " + ", ".join(sorted(unknown))
            elif error.validator == "required" and isinstance(error.instance, dict):
                missing = set(error.validator_value) - error.instance.keys()
                message = f"Missing required parameter(s) at {location}: " + ", ".join(sorted(missing))
            else:
                field_schema = validator.schema.get("properties", {}).get(error.absolute_path[0], {}) if error.absolute_path else {}
                expectation = error.schema.get("description") or field_schema.get("description") or error.schema.get("type") or error.validator
                message = f"Invalid parameter '{location}'; expected {expectation}."
            if message not in messages:
                messages.append(message)
            if len(messages) == 10:
                break
        if messages:
            message = " ".join(messages)
            error = ToolError("validation", message, name, "Correct the named parameters and retry.")
            structured = ToolResult.failure(name, self._server_session, error).to_dict()
            return CallToolResult(
                is_error=True,
                content=[TextContent(type="text", text=message)],
                structured_content=structured,
            )
        if name in PREVIEW_EFFECTS and ("dryRun" in arguments or "inspectLive" in arguments):
            arguments = dict(arguments)
            inspect_live = arguments.pop("inspectLive", False)
            if arguments.pop("dryRun", False):
                preview = build_preview(name, arguments, validator.schema["properties"], self._tool_descriptions[name])
                if inspect_live:
                    inspection = (
                        await anyio.to_thread.run_sync(self._preview_inspector, name, arguments)
                        if self._preview_inspector is not None else
                        PreviewInspection(targetVerified=False, observed={}, changes=[], conflicts=[], unverified=["Live inspection is not available."])
                    )
                    preview["inspection"] = inspection
                    preview["targetVerified"] = inspection["targetVerified"]
                structured = ToolResult.success(name, self._server_session, preview).to_dict()
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(structured))], structured_content=structured,
                )
        result = await super().call_tool(name, arguments, context)
        if isinstance(result, CallToolResult) and (result.structured_content or {}).get("ok") is False:
            return result.model_copy(update={"is_error": True})
        return result

    async def _audit_invocation(self, ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
        if ctx.method != "tools/call":
            return await call_next(ctx)
        from modeldesk_mcp.tools import TOOL_DOMAIN_BY_NAME

        params = ctx.params or {}
        name = params.get("name")
        tool = name if isinstance(name, str) and name in TOOL_DOMAIN_BY_NAME else "unregistered"
        arguments = json.dumps(params.get("arguments"), sort_keys=True, separators=(",", ":")).encode()
        input_hash = hmac.new(self._audit_key, arguments, hashlib.sha256).hexdigest()
        raw_meta = params.get("_meta")
        parent = _TRACE_PROPAGATOR.extract(raw_meta if isinstance(raw_meta, dict) else {})
        parent_span = trace.get_current_span(parent).get_span_context()
        span_context = trace.SpanContext(
            trace_id=parent_span.trace_id if parent_span.is_valid else (randbits(128) or 1),
            span_id=randbits(64) or 1,
            is_remote=False,
            trace_flags=parent_span.trace_flags,
            trace_state=parent_span.trace_state,
        )
        token = otel_context.attach(trace.set_span_in_context(trace.NonRecordingSpan(span_context), parent))
        start = perf_counter()
        outcome: str | int = "interrupted"
        try:
            result = await call_next(ctx)
            outcome = "ok"
            if isinstance(result, CallToolResult):
                is_error, structured = result.is_error, result.structured_content
            elif isinstance(result, dict):
                is_error, structured = result.get("isError"), result.get("structuredContent")
            else:
                is_error, structured = False, None
            if is_error:
                structured = structured or {}
                error = structured.get("error") or structured
                outcome = error.get("errorType", "tool_error")
            return result
        except MCPError as error:
            outcome = error.error.code
            raise
        except Exception:
            outcome = "request_error"
            raise
        finally:
            otel_context.detach(token)
            _AUDIT_LOGGER.info(json.dumps({
                "event": "mcp.tool.invocation", "tool": tool, "toolVersion": __version__,
                "inputHash": input_hash, "durationMs": round((perf_counter() - start) * 1000, 3),
                "outcomeCode": outcome, "traceId": f"{span_context.trace_id:032x}",
                "spanId": f"{span_context.span_id:016x}",
            }, separators=(",", ":")))


def create_app() -> MCPServer:
    """Create an MCPServer that reports the package version during initialization."""

    from modeldesk_mcp.com_bridge import ComStaDispatcher, ModelDeskAutomationGateway
    from modeldesk_mcp.config import ComGatewayOptions
    from modeldesk_mcp.domain import ModelDeskService, WorkflowCatalog
    from modeldesk_mcp.tools import register_tools
    from modeldesk_mcp.tools.resources import register_resources

    options = ComGatewayOptions.load_from_environment()
    dispatcher = ComStaDispatcher()
    gateway = ModelDeskAutomationGateway(dispatcher, options)
    workflows = WorkflowCatalog()
    service = ModelDeskService(gateway, workflows)
    mcp = ModelDeskMcpServer(gateway.inspect_preview)
    register_tools(mcp, service)
    register_resources(mcp, workflows)
    return mcp


def _replay_from_stdin() -> int:
    def reject(code: str, message: str) -> int:
        print(json.dumps({"ok": False, "error": {"code": code, "message": message}}))
        return 2

    try:
        raw_request = sys.stdin.read(1_048_577)
        if len(raw_request) > 1_048_576:
            return reject("invalid_replay_request", "Replay input exceeds the character limit.")
        request = json.loads(raw_request, parse_constant=_reject_non_json_constant)
    except ValueError:
        return reject("invalid_replay_request", "Expected one valid JSON replay request on stdin.")
    if not isinstance(request, dict) or set(request) != {"tool", "arguments"}:
        return reject("invalid_replay_request", "Expected an object with tool and arguments fields.")
    name = request["tool"]
    arguments = request["arguments"]
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return reject("invalid_replay_request", "Tool must be a string and arguments must be an object.")
    if name not in _REPLAYABLE_TOOLS and not (
        name in PREVIEW_EFFECTS and arguments.get("dryRun") is True and arguments.get("inspectLive") is not True
    ):
        return reject("replay_not_safe", "Only pure catalog operations and explicit effect previews can be replayed.")

    result = asyncio.run(create_app().call_tool(name, arguments))
    if not isinstance(result, CallToolResult):
        return reject("replay_result_unknown", "The tool did not produce a complete result.")
    data = dict(result.structured_content or {})
    data.pop("sessionId", None)
    print(json.dumps({"isError": result.is_error, "result": data}, sort_keys=True))
    return 2 if result.is_error else 0


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"Unsupported JSON constant: {value}")


def main(argv: list[str] | None = None) -> int | None:
    """Run COM-free metadata commands or start the MCP stdio server.

    Metadata commands return before app creation, so they do not construct the
    COM runtime. During server operation, stdout belongs to MCP framing.
    """

    parser = argparse.ArgumentParser(description="ModelDesk MCP stdio server.")
    metadata_group = parser.add_mutually_exclusive_group()
    metadata_group.add_argument("--version", action="store_true", help="Print the server version and exit.")
    metadata_group.add_argument("--replay", action="store_true", help="Replay one safe JSON tool invocation from stdin.")
    metadata_group.add_argument("--list-tools", action="store_true", help="Print registered tool names and exit.")
    metadata_group.add_argument(
        "--list-resources",
        action="store_true",
        help="Print the registered resource status and exit.",
    )
    metadata_group.add_argument(
        "--list-prompts",
        action="store_true",
        help="Print the registered prompt status and exit.",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(f"modeldesk-mcp {__version__}")
        return 0
    if args.replay:
        return _replay_from_stdin()
    if args.list_tools:
        from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES

        print(*EXPECTED_TOOL_NAMES, sep="\n")
        return 0
    if args.list_resources:
        from modeldesk_mcp.tools.resources import WORKFLOW_CATALOG_URI

        print(WORKFLOW_CATALOG_URI)
        return 0
    if args.list_prompts:
        print("No MCP prompts are registered.")
        return 0

    _AUDIT_LOGGER.setLevel(logging.INFO)
    if not _AUDIT_LOGGER.handlers:
        _AUDIT_LOGGER.addHandler(logging.StreamHandler())
    _AUDIT_LOGGER.propagate = False
    create_app().run()


if __name__ == "__main__":
    raise SystemExit(main())
