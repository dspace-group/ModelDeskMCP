"""Canonical mapping of MCP tool names to ModelDesk use cases.

The five documented use cases live in ``ModelDesk/doc/use-cases.md``:

- UC1: Parameterize ASM-Based Vehicle Models
- UC2: Build Roads for Simulation and Visualization
- UC3: Define Scenarios and Traffic Behavior
- UC4: Manage Traffic Objects and Scene Assets
- UC5: Analyze and Compare Simulation Results

Tools that are cross-cutting infrastructure (status, capabilities, project
handling, workflow planning, testing, AURELION sync) are tagged
``Supporting`` or with multiple use-case tags when they genuinely serve more
than one use case. This module is the single source of truth so that an
agent can be told "Use Case 3" and resolve the exact tool list through the
``modeldesk_list_tools_by_use_case`` MCP tool instead of searching docs.
"""

from __future__ import annotations

import re

UC1 = "UC1"
UC2 = "UC2"
UC3 = "UC3"
UC4 = "UC4"
UC5 = "UC5"
SUPPORTING = "Supporting"

ALL_USE_CASE_TAGS: tuple[str, ...] = (UC1, UC2, UC3, UC4, UC5, SUPPORTING)

USE_CASE_TITLES: dict[str, str] = {
    UC1: "Parameterize ASM-Based Vehicle Models",
    UC2: "Build Roads for Simulation and Visualization",
    UC3: "Define Scenarios and Traffic Behavior",
    UC4: "Manage Traffic Objects and Scene Assets",
    UC5: "Analyze and Compare Simulation Results",
    SUPPORTING: "Cross-cutting infrastructure supporting all use cases",
}

# Maps every registered MCP tool name to one or more use-case tags.
TOOL_USE_CASES: dict[str, tuple[str, ...]] = {
    # Supporting: server/session/project foundation
    "modeldesk_get_status": (SUPPORTING,),
    "modeldesk_get_capabilities": (SUPPORTING,),
    "modeldesk_open_project": (SUPPORTING,),
    "modeldesk_create_project_pool_file": (SUPPORTING,),
    "modeldesk_list_environment_pool_items": (SUPPORTING,),
    "modeldesk_save_project": (SUPPORTING,),
    "modeldesk_close_project": (SUPPORTING,),
    "modeldesk_list_experiments": (SUPPORTING,),
    "modeldesk_activate_experiment": (SUPPORTING,),
    "modeldesk_save_active_experiment": (SUPPORTING,),
    "modeldesk_download_active_experiment": (SUPPORTING,),
    "modeldesk_get_workflow_plan": (SUPPORTING,),

    # UC1: Parameterize ASM-Based Vehicle Models
    "modeldesk_list_parameter_sets": (UC1,),
    "modeldesk_activate_parameter_set": (UC1,),
    "modeldesk_get_parameterization_summary": (UC1,),
    "modeldesk_get_active_model_info": (UC1,),
    "modeldesk_set_active_model": (UC1,),
    "modeldesk_get_parameter_value": (UC1,),
    "modeldesk_set_scalar_parameter": (UC1,),
    "modeldesk_set_parameter_value": (UC1,),
    "modeldesk_get_processing_summary": (UC1,),
    "modeldesk_get_processing_configuration": (UC1,),
    "modeldesk_run_processing": (UC1,),

    # UC2: Build Roads for Simulation and Visualization
    "modeldesk_create_road_network": (UC2,),
    "modeldesk_get_road_summary": (UC2,),
    "modeldesk_activate_road": (UC2,),
    "modeldesk_list_roads": (UC2,),
    "modeldesk_save_road_network_as": (UC2,),
    "modeldesk_add_road": (UC2,),
    "modeldesk_update_road": (UC2,),
    "modeldesk_remove_road": (UC2,),
    "modeldesk_add_road_segment": (UC2,),
    "modeldesk_update_road_segment": (UC2,),
    "modeldesk_remove_road_segment": (UC2,),
    "modeldesk_configure_road_lanes": (UC2,),
    "modeldesk_add_road_object": (UC2,),
    "modeldesk_update_road_object": (UC2,),
    "modeldesk_remove_road_object": (UC2,),
    "modeldesk_connect_roads": (UC2,),
    "modeldesk_disconnect_road": (UC2,),
    "modeldesk_create_basic_road": (UC2,),

    # UC3: Define Scenarios and Traffic Behavior
    "modeldesk_create_traffic_scenario": (UC3,),
    "modeldesk_get_scenario_summary": (UC3,),
    "modeldesk_activate_scenario": (UC3,),
    "modeldesk_list_scenario_fellows": (UC3,),
    "modeldesk_list_scenario_maneuvers": (UC3,),
    "modeldesk_add_scenario_fellow": (UC3,),
    "modeldesk_update_scenario_fellow": (UC3,),
    "modeldesk_remove_scenario_fellow": (UC3,),
    "modeldesk_add_scenario_maneuver": (UC3,),
    "modeldesk_update_scenario_maneuver": (UC3,),
    "modeldesk_remove_scenario_maneuver": (UC3,),
    "modeldesk_set_scenario_maneuver_sequence": (UC3,),
    "modeldesk_set_maneuver_behavior_profiles": (UC3,),
    "modeldesk_get_scenario_road": (UC3,),
    "modeldesk_set_scenario_road": (UC3,),
    "modeldesk_list_fellow_activities": (UC3,),
    "modeldesk_get_vehicle_object_type": (UC3,),
    "modeldesk_list_vehicle_object_types": (UC3,),
    "modeldesk_set_vehicle_object_type": (UC3,),
    "modeldesk_start_maneuver": (UC3,),
    "modeldesk_stop_maneuver": (UC3,),
    "modeldesk_reset_maneuver": (UC3,),

    # UC4: Manage Traffic Objects and Scene Assets
    "modeldesk_get_traffic_objects_summary": (UC4,),
    "modeldesk_list_traffic_objects": (UC4,),
    "modeldesk_list_traffic_object_folders": (UC4,),
    "modeldesk_validate_traffic_object_reference": (UC4,),
    "modeldesk_add_traffic_object": (UC4,),
    "modeldesk_remove_traffic_object": (UC4,),
    "modeldesk_add_traffic_object_folder": (UC4,),
    "modeldesk_remove_traffic_object_folder": (UC4,),

    # UC5: Analyze and Compare Simulation Results
    "modeldesk_get_test_summary": (UC5,),
    "modeldesk_activate_test": (UC5,),
    "modeldesk_list_logical_test_cases": (UC5,),
    "modeldesk_list_concrete_test_cases": (UC5,),
    "modeldesk_execute_test": (UC5,),
    "modeldesk_get_plotting_summary": (UC5,),
    "modeldesk_activate_plotting": (UC5,),
    "modeldesk_list_plot_captures": (UC5,),
    "modeldesk_list_plot_layouts": (UC5,),
    "modeldesk_compare_captures": (UC5,),

    # Cross-cutting: road (UC2) and scenario (UC3) visualization sync
    "modeldesk_synchronize_aurelion": (UC2, UC3),

    # Self-referential: the lookup tool itself is supporting infrastructure
    "modeldesk_list_tools_by_use_case": (SUPPORTING,),
}


def get_use_case_tags(tool_name: str) -> tuple[str, ...]:
    """Return the use-case tags registered for a tool name, or an empty tuple."""

    return TOOL_USE_CASES.get(tool_name, ())


def format_use_case_tag_prefix(tool_name: str) -> str:
    """Return a docstring-friendly ``[UC1]``/``[UC2/UC3]`` prefix for a tool name."""

    tags = get_use_case_tags(tool_name)
    if not tags:
        return ""
    return f"[{'/'.join(tags)}] "


_USE_CASE_NUMBER_PATTERN = re.compile(r"(\d+)")


def resolve_use_case_query(query: str) -> str | None:
    """Normalize a free-form use-case query into a canonical tag.

    Accepts inputs such as ``"3"``, ``"uc3"``, ``"UC3"``, ``"Use Case 3"``,
    or ``"supporting"``/``"Supporting"``. Returns ``None`` when the query
    does not resolve to a known tag.
    """

    normalized = query.strip().lower()
    if normalized == "":
        return None

    if normalized == SUPPORTING.lower():
        return SUPPORTING

    match = _USE_CASE_NUMBER_PATTERN.search(normalized)
    if match:
        candidate = f"UC{match.group(1)}"
        if candidate in USE_CASE_TITLES:
            return candidate
        return None

    for tag in ALL_USE_CASE_TAGS:
        if normalized == tag.lower():
            return tag

    return None


def list_tools_for_use_case(use_case_tag: str) -> tuple[str, ...]:
    """Return all tool names tagged with the given canonical use-case tag, sorted."""

    return tuple(sorted(name for name, tags in TOOL_USE_CASES.items() if use_case_tag in tags))
