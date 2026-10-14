"""Tests for project-pool file creation validation."""

from types import SimpleNamespace

import pytest

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import ProjectPoolFileCreationRequest, ProjectPoolFileType


class _InlineDispatcher:
    def invoke(self, operation, timeout_seconds):
        return operation()


class _RecordingPool:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, bool]] = []

    def CreateFile(self, file_type: int, name: str, overwrite_existing: bool) -> bool:
        self.calls.append((file_type, name, overwrite_existing))
        return True


def test_project_pool_request_maps_road_alias_and_strips_extension() -> None:
    request = ProjectPoolFileCreationRequest.create("RoadNetwork", "City.rd", False)

    assert request.file_type == ProjectPoolFileType.ROAD_NETWORK
    assert request.to_com_type() == 0
    assert request.name == "City"
    assert request.expected_extension() == ".rd"


def test_project_pool_request_accepts_numeric_scenario_type() -> None:
    request = ProjectPoolFileCreationRequest.create("1", "CutIn.xml", True)

    assert request.file_type == ProjectPoolFileType.TRAFFIC_SCENARIO
    assert request.to_com_type() == 1
    assert request.name == "CutIn"
    assert request.overwrite_existing is True


def test_project_pool_type_three_matches_automation_layout_configuration() -> None:
    request = ProjectPoolFileCreationRequest.create("3", "Layout.xml", False)

    assert request.file_type.display_name == "LayoutConfiguration"


def test_project_pool_request_rejects_directory_names() -> None:
    with pytest.raises(ValueError):
        ProjectPoolFileCreationRequest.create("RoadNetwork", "Roads/City.rd", False)


def test_project_pool_request_rejects_invalid_type() -> None:
    with pytest.raises(ValueError):
        ProjectPoolFileCreationRequest.create("Unknown", "City", False)


def test_create_road_network_without_active_project_returns_structured_failure() -> None:
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = SimpleNamespace(ActiveProject=None)  # type: ignore[attr-defined]

    result = gateway.create_road_network("SafeProbe", overwrite_existing=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "invalid_state"


def test_close_project_dry_run_does_not_close_project() -> None:
    class Project:
        Name = "Project A"

        def __init__(self) -> None:
            self.closed = False

        def Close(self, save: bool) -> None:
            self.closed = True

    project = Project()
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = SimpleNamespace(ActiveProject=project)  # type: ignore[attr-defined]

    result = gateway.close_project(save=False, dry_run=True)

    assert result.ok
    assert result.to_dict()["data"]["details"]["dryRun"] == "true"
    assert result.to_dict()["data"]["details"]["unsavedChanges"] == "unknown"
    assert not project.closed


def test_gateway_reacquires_active_project_on_each_operation() -> None:
    class MutableApplication:
        Version = "fake"

        def __init__(self) -> None:
            self.active_project = SimpleNamespace(Name="First project", ActiveExperiment=None)

        @property
        def ActiveProject(self):
            return self.active_project

    application = MutableApplication()
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]

    first = gateway.get_status()
    application.active_project = SimpleNamespace(Name="Second project", ActiveExperiment=None)
    second = gateway.get_status()

    assert first.to_dict()["data"]["activeProjectName"] == "First project"
    assert second.to_dict()["data"]["activeProjectName"] == "Second project"


def test_specialized_pool_creation_uses_source_defined_road_and_scenario_ids() -> None:
    pool = _RecordingPool()
    application = SimpleNamespace(ActiveProject=SimpleNamespace(Pool=pool))
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]

    road_result = gateway.create_road_network("OvertakeRoad", overwrite_existing=False)
    scenario_result = gateway.create_traffic_scenario("CutIn", overwrite_existing=True)

    assert road_result.ok
    assert scenario_result.ok
    assert pool.calls == [(0, "OvertakeRoad", False), (1, "CutIn", True)]
