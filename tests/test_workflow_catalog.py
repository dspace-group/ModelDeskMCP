"""Tests for workflow catalog parity."""

from modeldesk_mcp.domain import WorkflowCatalog


def test_workflow_catalog_returns_automation_smoke_plan() -> None:
    result = WorkflowCatalog().get_workflow_plan("automation_session_smoke")
    data = result.to_dict()

    assert data["ok"] is True
    assert data["data"]["name"] == "automation_session_smoke"
    assert "modeldesk_get_status" in data["data"]["requiredTools"]


def test_workflow_catalog_rejects_unknown_plan() -> None:
    result = WorkflowCatalog().get_workflow_plan("missing")
    data = result.to_dict()

    assert data["ok"] is False
    assert data["error"]["errorType"] == "not_found"