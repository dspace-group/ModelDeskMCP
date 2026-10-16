"""Tests for workflow catalog parity."""

import asyncio
import json

from mcp.server.mcpserver import MCPServer

from modeldesk_mcp.domain import WorkflowCatalog
from modeldesk_mcp.contracts.use_cases import list_tools_for_use_case
from modeldesk_mcp.tools.resources import register_resources


def test_workflow_catalog_returns_automation_smoke_plan() -> None:
    result = WorkflowCatalog().get_workflow_plan("automation_session_smoke")
    data = result.to_dict()

    assert data["ok"] is True
    assert data["data"]["name"] == "automation_session_smoke"
    assert "modeldesk_get_status" in data["data"]["requiredTools"]


def test_workflow_catalog_lists_registered_plans_in_stable_order() -> None:
    names = tuple(plan.name for plan in WorkflowCatalog().list_workflow_plans())

    assert names == tuple(sorted(names))
    assert "automation_session_smoke" in names
    assert "create_basic_traffic_scenario" in names


def test_workflow_catalog_resource_discovers_plans_and_use_cases() -> None:
    server = MCPServer("resource-test")
    register_resources(server, WorkflowCatalog())

    resources = asyncio.run(server.list_resources())
    contents = asyncio.run(server.read_resource("modeldesk://workflow-catalog"))
    catalog = json.loads(contents[0].content)

    assert [str(resource.uri) for resource in resources] == ["modeldesk://workflow-catalog"]
    assert len(catalog["workflows"]) == 9
    assert {entry["id"] for entry in catalog["useCases"]} == {"UC1", "UC2", "UC3", "UC4", "UC5", "Supporting"}
    assert all(entry["requiredTools"] for entry in catalog["workflows"])


def test_workflow_catalog_rejects_unknown_plan() -> None:
    result = WorkflowCatalog().get_workflow_plan("missing")
    data = result.to_dict()

    assert data["ok"] is False
    assert data["error"]["errorType"] == "not_found"


def test_scenario_workflow_warns_that_fellow_creation_does_not_position_it() -> None:
    result = WorkflowCatalog().get_workflow_plan("create_basic_traffic_scenario")
    data = result.to_dict()

    assert data["ok"] is True
    assert "creation alone does not position it" in str(data["data"]).lower()
    assert "longitudinalposition" in str(data["data"]).lower()


def test_road_and_scenario_routing_includes_required_project_pool_tools() -> None:
    for use_case in ("UC2", "UC3"):
        tools = list_tools_for_use_case(use_case)

        assert "modeldesk_create_project_pool_file" in tools
        assert "modeldesk_list_environment_pool_items" in tools
