"""Tests for Environment Pool group validation."""

from modeldesk_mcp.contracts import EnvironmentPoolGroup, EnvironmentPoolGroupRequest


def test_environment_pool_objects_mapping() -> None:
    request = EnvironmentPoolGroupRequest.create("Objects", True)

    assert request.group == EnvironmentPoolGroup.OBJECTS
    assert request.folder_name() == "Objects"
    assert request.file_extension() == ".tro"
    assert request.domain_name() == "environmentPool.objects"


def test_environment_pool_traffic_driver_alias() -> None:
    request = EnvironmentPoolGroupRequest.create("Traffic Driver", False)

    assert request.group == EnvironmentPoolGroup.TRAFFIC_DRIVER
    assert request.folder_name() == "Traffic Driver"
    assert request.file_extension() == ".trd"


def test_environment_pool_road_extension_alias() -> None:
    request = EnvironmentPoolGroupRequest.create(".rd", False)

    assert request.group == EnvironmentPoolGroup.ROAD