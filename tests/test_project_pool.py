"""Tests for project-pool file creation validation."""

import pytest

from modeldesk_mcp.contracts import ProjectPoolFileCreationRequest, ProjectPoolFileType


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


def test_project_pool_request_rejects_directory_names() -> None:
    with pytest.raises(ValueError):
        ProjectPoolFileCreationRequest.create("RoadNetwork", "Roads/City.rd", False)


def test_project_pool_request_rejects_invalid_type() -> None:
    with pytest.raises(ValueError):
        ProjectPoolFileCreationRequest.create("Unknown", "City", False)