"""MCP resources for static ModelDesk workflow discovery."""

from __future__ import annotations

import json
from typing import Any

from modeldesk_mcp.contracts.use_cases import ALL_USE_CASE_TAGS, USE_CASE_TITLES, list_tools_for_use_case
from modeldesk_mcp.domain.workflow_catalog import WorkflowCatalog

WORKFLOW_CATALOG_URI = "modeldesk://workflow-catalog"


def register_resources(mcp: Any, workflows: WorkflowCatalog) -> None:
    """Register the static workflow and use-case catalog resource."""

    if mcp is None:
        raise ValueError("mcp must not be None")
    if workflows is None:
        raise ValueError("workflows must not be None")

    @mcp.resource(
        WORKFLOW_CATALOG_URI,
        name="modeldesk_workflow_catalog",
        title="ModelDesk Workflow Catalog",
        description="Discover workflow names, ordered steps, required tools, and supported use-case identifiers.",
        mime_type="application/json",
    )
    def modeldesk_workflow_catalog() -> str:
        payload = {
            "workflows": [
                {
                    "name": plan.name,
                    "useCase": plan.use_case,
                    "message": plan.message,
                    "steps": list(plan.steps),
                    "requiredTools": list(plan.required_tools),
                }
                for plan in workflows.list_workflow_plans()
            ],
            "useCases": [
                {
                    "id": use_case,
                    "title": USE_CASE_TITLES[use_case],
                    "tools": list(list_tools_for_use_case(use_case)),
                }
                for use_case in ALL_USE_CASE_TAGS
            ],
        }
        return json.dumps(payload, indent=2)
