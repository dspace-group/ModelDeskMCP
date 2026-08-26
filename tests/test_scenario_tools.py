"""Tests for scenario and vehicle object type tool input validation."""

from __future__ import annotations

from typing import Any

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector, SelectorKind
from modeldesk_mcp.contracts.models import ToolResult


def _make_gateway() -> ModelDeskAutomationGateway:
    return ModelDeskAutomationGateway(ComStaDispatcher(), ComGatewayOptions())


def test_set_scenario_road_rejects_empty_road_name() -> None:
    gateway = _make_gateway()

    result = gateway.set_scenario_road("", save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


def test_set_scenario_road_rejects_whitespace_only_road_name() -> None:
    gateway = _make_gateway()

    result = gateway.set_scenario_road("   ", save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


def test_set_vehicle_object_type_rejects_negative_element_index() -> None:
    gateway = _make_gateway()
    ego_selector = Selector.create(None, None)

    result = gateway.set_vehicle_object_type(ego_selector, maneuver_index=0, element_index=-1, save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


class _FakeGateway:
    """Minimal gateway stub that records calls and returns a canned success result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.session_id = "test-session"

    def _record(self, name: str, *args: Any) -> ToolResult:
        self.calls.append((name, args))
        return ToolResult.success(name, "test-session", {})

    def get_scenario_road(self) -> ToolResult:
        return self._record("get_scenario_road")

    def set_scenario_road(self, road_name: str, save: bool, download: bool) -> ToolResult:
        return self._record("set_scenario_road", road_name, save, download)

    def list_fellow_activities(self, fellow_selector: Selector) -> ToolResult:
        return self._record("list_fellow_activities", fellow_selector)

    def get_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int) -> ToolResult:
        return self._record("get_vehicle_object_type", fellow_selector, maneuver_index)

    def list_vehicle_object_types(self, fellow_selector: Selector, maneuver_index: int) -> ToolResult:
        return self._record("list_vehicle_object_types", fellow_selector, maneuver_index)

    def set_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int, element_index: int, save: bool, download: bool) -> ToolResult:
        return self._record("set_vehicle_object_type", fellow_selector, maneuver_index, element_index, save, download)


def _make_service(fake_gateway: _FakeGateway) -> Any:
    from modeldesk_mcp.domain.service import ModelDeskService

    service = object.__new__(ModelDeskService)
    service._gateway = fake_gateway  # type: ignore[attr-defined]
    return service


def test_service_list_fellow_activities_passes_active_selector_for_ego() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("active", "active")

    assert result.ok
    assert len(fake.calls) == 1
    name, args = fake.calls[0]
    assert name == "list_fellow_activities"
    selector: Selector = args[0]
    assert selector.by == SelectorKind.ACTIVE


def test_service_list_fellow_activities_passes_index_selector_for_fellow() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("index", "2")

    assert result.ok
    name, args = fake.calls[0]
    selector: Selector = args[0]
    assert selector.by == SelectorKind.INDEX
    assert selector.to_com_value() == 2


def test_service_list_fellow_activities_rejects_invalid_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("name", "")

    assert not result.ok
    assert len(fake.calls) == 0


def test_service_get_vehicle_object_type_routes_maneuver_index() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    service.get_vehicle_object_type("active", "active", 3)

    name, args = fake.calls[0]
    assert name == "get_vehicle_object_type"
    assert args[1] == 3


def test_set_vehicle_object_type_rejects_invalid_fellow_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.set_vehicle_object_type("name", "", 0, 0, False, False)

    assert not result.ok
    assert len(fake.calls) == 0


# --- SAFEARRAY regression tests ---
# AvailableElements may return a Python tuple (COM SAFEARRAY) instead of a COM
# collection object. The helpers _available_type_elements and
# _summarize_type_elements must handle both cases without AttributeError.

def test_available_type_elements_handles_python_tuple() -> None:
    from modeldesk_mcp.com_bridge.gateway import _available_type_elements, _summarize_type_elements

    class _FakeTypeManager:
        AvailableElements = ("elem0", "elem1", "elem2")

    elements = _available_type_elements(_FakeTypeManager())

    assert elements == ["elem0", "elem1", "elem2"]


def test_summarize_type_elements_builds_domain_summary_from_list() -> None:
    from modeldesk_mcp.com_bridge.gateway import _summarize_type_elements
    from modeldesk_mcp.contracts.models import DomainSummary

    elements = ["elem0", "elem1"]
    result = _summarize_type_elements("scenarios.objectTypes.ego", elements, "object type", 500)

    assert isinstance(result, DomainSummary)
    assert result.count == 2
    assert len(result.items) == 2
    assert result.items[0].index == 0
    assert result.items[1].index == 1


def test_summarize_type_elements_truncates_at_max_items() -> None:
    from modeldesk_mcp.com_bridge.gateway import _summarize_type_elements

    elements = list(range(10))
    result = _summarize_type_elements("domain", elements, "type", 3)

    assert result.count == 10
    assert len(result.items) == 3
    assert result.message is not None
