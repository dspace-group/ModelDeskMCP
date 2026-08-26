"""Tests for the registered FastMCP tool surface."""

from collections.abc import Callable
import re
from typing import Any

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.contracts import public_error_message
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
