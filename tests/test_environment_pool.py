"""Tests for Environment Pool group validation."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import EnvironmentPoolGroup, EnvironmentPoolGroupRequest


class _InlineDispatcher:
    def invoke(self, operation, timeout_seconds):
        return operation()


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


@pytest.mark.parametrize(
    ("group", "extension"),
    (("Road", ".rd"), ("Scenario", ".xml"), ("Objects", ".tro"), ("Traffic Driver", ".trd")),
)
def test_gateway_lists_only_selected_environment_pool_group(
    tmp_path: Path,
    group: str,
    extension: str,
) -> None:
    working_root = tmp_path
    group_directory = working_root / "Pool" / "Environment" / group
    group_directory.mkdir(parents=True)
    (group_directory / f"target{extension}").write_text("", encoding="utf-8")
    (group_directory / "ignored.txt").write_text("", encoding="utf-8")
    nested_directory = group_directory / "nested"
    nested_directory.mkdir()
    (nested_directory / f"nested{extension}").write_text("", encoding="utf-8")

    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = SimpleNamespace(  # type: ignore[attr-defined]
        ActiveProject=SimpleNamespace(WorkingRoot=str(working_root))
    )

    result = gateway.list_environment_pool_items(group, recursive=True)

    assert result.ok
    data = result.to_dict()["data"]
    assert data["available"] is True
    assert data["count"] == 2
    assert {item["path"].lower().endswith(f"target{extension}".lower()) or item["path"].lower().endswith(f"nested{extension}".lower()) for item in data["items"]} == {True}
