"""Tests for the registered FastMCP tool surface."""

from collections.abc import Callable
import asyncio
import re
from typing import Any

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.contracts import ToolResult, public_error_message
from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES, TOOL_DOMAIN_BY_NAME, TOOL_DOMAINS, register_tools


class FakeMcp:
    """Small decorator collector matching the FastMCP tool registration shape."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = function
            return function

        return decorator


class FakeService:
    """Placeholder service; registration does not execute service methods."""


def test_expected_tool_names_are_unique_lowercase_modeldesk_identifiers() -> None:
    assert EXPECTED_TOOL_NAMES
    assert len(EXPECTED_TOOL_NAMES) == len(set(EXPECTED_TOOL_NAMES))
    assert all(re.fullmatch(r"modeldesk_[a-z0-9_]+", name) for name in EXPECTED_TOOL_NAMES)
    assert set(TOOL_DOMAIN_BY_NAME) == set(EXPECTED_TOOL_NAMES)
    assert set(TOOL_DOMAIN_BY_NAME.values()) == set(TOOL_DOMAINS)
    assert TOOL_DOMAIN_BY_NAME["modeldesk_set_maneuver_behavior_profiles"] == "Scenario/TrafficScenario"
    assert TOOL_DOMAIN_BY_NAME["modeldesk_start_maneuver"] == "Scenario/TrafficScenario"


def test_public_error_message_redacts_absolute_windows_paths() -> None:
    drive_path = chr(67) + r":\Users\example\project.md"

    message = public_error_message(f"COM failed while opening {drive_path}.")

    assert "[local path]" in message
    assert drive_path not in message


def test_public_error_message_redacts_entire_windows_path_containing_spaces() -> None:
    drive_path = r"C:\Program Files\ModelDesk\Project Files\vehicle.md"

    message = public_error_message(f"COM failed while opening '{drive_path}'.")

    assert "[local path]" in message
    assert "Program Files" not in message
    assert "ModelDesk" not in message
    assert "vehicle.md" not in message


def test_public_error_message_redacts_unquoted_windows_path_without_eating_context() -> None:
    drive_path = r"C:\Program Files\ModelDesk\Project Files\vehicle.md"

    message = public_error_message(f"Could not open {drive_path}; retry once.")

    assert message == "Could not open [local path]; retry once."


def test_gateway_validation_result_redacts_absolute_windows_paths() -> None:
    drive_path = chr(67) + r":\Users\example\project.md"
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._session_id = "test-session"  # type: ignore[attr-defined]

    result = gateway._validation_failure("modeldesk_open_project", f"Missing {drive_path}")

    assert result.error is not None
    assert result.error.message == "Missing [local path]"


def test_register_tools_registers_exact_expected_names() -> None:
    fake_mcp = FakeMcp()

    register_tools(fake_mcp, FakeService())

    assert tuple(fake_mcp.tools.keys()) == EXPECTED_TOOL_NAMES


def test_real_mcp_schemas_document_inputs_and_share_tool_result_envelope() -> None:
    from mcp.server.mcpserver import MCPServer

    class SchemaService(FakeService):
        def get_status(self) -> ToolResult:
            return ToolResult.success("modeldesk_get_status", "schema-test", {"ready": True})

    server = MCPServer("schema-test")
    register_tools(server, SchemaService())
    tools = asyncio.run(server.list_tools())
    assert tuple(tool.name for tool in tools) == EXPECTED_TOOL_NAMES

    missing_examples: list[tuple[str, str]] = []
    for tool in tools:
        properties = tool.input_schema.get("properties", {})
        for property_name, property_schema in properties.items():
            assert property_schema.get("description"), f"{tool.name}.{property_name} has no description"
            if not property_schema.get("examples"):
                missing_examples.append((tool.name, property_name))
    assert missing_examples == [("modeldesk_activate_test", "testName")]

    open_project = next(tool for tool in tools if tool.name == "modeldesk_open_project")
    assert open_project.input_schema["properties"]["projectFile"]["examples"]

    envelope_properties = {"ok", "operation", "sessionId", "data", "warnings", "artifacts", "error"}
    for tool in tools:
        assert tool.output_schema is not None
        assert set(tool.output_schema["properties"]) == envelope_properties
        data_schema = tool.output_schema["properties"]["data"]
        assert "type" not in data_schema
        assert "properties" not in data_schema
        assert "additionalProperties" not in data_schema

    result = asyncio.run(server.call_tool("modeldesk_get_status", {}))
    assert result.structured_content == {
        "ok": True,
        "operation": "modeldesk_get_status",
        "sessionId": "schema-test",
        "data": {"ready": True},
        "warnings": [],
        "artifacts": [],
        "error": None,
    }
