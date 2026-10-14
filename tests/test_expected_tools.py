"""Tests for the registered FastMCP tool surface."""

from collections.abc import Callable
import asyncio
import re
from typing import Any

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.contracts import ModelDeskStatus, ToolResult, public_error_message
from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES, TOOL_DOMAIN_BY_NAME, TOOL_DOMAINS, register_tools
from modeldesk_mcp.tools.registry import _ADDITIVE_TOOL_NAMES, _OPEN_WORLD_TOOL_NAMES, _READ_ONLY_TOOL_NAMES


class FakeMcp:
    """Small decorator collector matching the FastMCP tool registration shape."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}
        self.annotations: dict[str, Any] = {}

    def tool(self, name: str, annotations: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = function
            self.annotations[name] = annotations
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
    assert tuple(fake_mcp.annotations.keys()) == EXPECTED_TOOL_NAMES


def test_real_mcp_schemas_document_inputs_and_share_tool_result_envelope() -> None:
    from mcp.server.mcpserver import MCPServer

    class SchemaService(FakeService):
        def get_status(self) -> ToolResult:
            return ToolResult.success(
                "modeldesk_get_status",
                "schema-test",
                ModelDeskStatus("schema-test", True, None, False, None, None, "ModelDesk.Application", "AMD64"),
            )

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
    paginated_tools = {
        "modeldesk_list_environment_pool_items",
        "modeldesk_list_experiments",
        "modeldesk_list_parameter_sets",
        "modeldesk_list_roads",
        "modeldesk_list_scenario_fellows",
        "modeldesk_list_scenario_maneuvers",
        "modeldesk_list_fellow_activities",
        "modeldesk_list_vehicle_object_types",
        "modeldesk_list_traffic_objects",
        "modeldesk_list_traffic_object_folders",
        "modeldesk_list_logical_test_cases",
        "modeldesk_list_concrete_test_cases",
        "modeldesk_list_plot_captures",
        "modeldesk_list_plot_layouts",
    }
    dry_run_tools = {
        "modeldesk_close_project",
        "modeldesk_remove_road",
        "modeldesk_remove_road_segment",
        "modeldesk_remove_road_object",
        "modeldesk_disconnect_road",
        "modeldesk_remove_scenario_fellow",
        "modeldesk_remove_scenario_maneuver",
        "modeldesk_remove_traffic_object",
        "modeldesk_remove_traffic_object_folder",
    }
    for tool in tools:
        assert tool.output_schema is not None
        assert set(tool.output_schema["properties"]) == envelope_properties
        data_schema = tool.output_schema["properties"]["data"]
        assert "anyOf" in data_schema
        data_branch = next(branch for branch in data_schema["anyOf"] if branch.get("type") != "null")
        if "$ref" in data_branch:
            definition_name = data_branch["$ref"].rsplit("/", 1)[-1]
            data_definition = tool.output_schema["$defs"][definition_name]
        else:
            data_definition = data_branch
        assert data_definition["type"] == "object"
        assert data_definition["properties"]

        error_schema = tool.output_schema["$defs"]["ToolErrorEnvelope"]["properties"]["errorType"]
        assert error_schema["enum"] == [
            "validation",
            "not_found",
            "timeout",
            "invalid_state",
            "com_error",
            "unexpected",
        ]

        annotations = tool.annotations
        assert annotations is not None
        assert annotations.read_only_hint is (True if tool.name in _READ_ONLY_TOOL_NAMES else None)
        assert annotations.open_world_hint is (tool.name in _OPEN_WORLD_TOOL_NAMES)
        assert annotations.destructive_hint is (False if tool.name in _ADDITIVE_TOOL_NAMES else None)
        assert annotations.idempotent_hint is (True if annotations.read_only_hint else None)
        assert "Preconditions:" in (tool.description or "")
        assert "Possible failure codes:" in (tool.description or "")
        if tool.name in paginated_tools:
            offset_schema = tool.input_schema["properties"]["offset"]
            assert offset_schema["default"] == 0
            assert "offset" in offset_schema["description"].lower()
            assert "nextOffset" in data_definition["properties"]
        if tool.name in dry_run_tools:
            dry_run_schema = tool.input_schema["properties"]["dryRun"]
            assert dry_run_schema["default"] is False
            assert "preview" in dry_run_schema["description"].lower()

    replay_risk_tools = {
        "modeldesk_create_project_pool_file",
        "modeldesk_create_road_network",
        "modeldesk_create_traffic_scenario",
        "modeldesk_add_road",
        "modeldesk_add_road_segment",
        "modeldesk_add_road_object",
        "modeldesk_connect_roads",
        "modeldesk_create_basic_road",
        "modeldesk_add_scenario_fellow",
        "modeldesk_add_scenario_maneuver",
        "modeldesk_add_traffic_object",
        "modeldesk_add_traffic_object_folder",
        "modeldesk_run_processing",
        "modeldesk_execute_test",
        "modeldesk_start_maneuver",
    }
    assert all("Replay risk:" in by_name.description for by_name in tools if by_name.name in replay_risk_tools)

    result = asyncio.run(server.call_tool("modeldesk_get_status", {}))
    assert result.structured_content == {
        "ok": True,
        "operation": "modeldesk_get_status",
        "sessionId": "schema-test",
        "data": {
            "sessionId": "schema-test",
            "modelDeskReachable": True,
            "modelDeskVersion": None,
            "hasActiveProject": False,
            "activeProjectName": None,
            "activeExperimentName": None,
            "progId": "ModelDesk.Application",
            "processArchitecture": "AMD64",
        },
        "warnings": [],
        "artifacts": [],
        "error": None,
    }
