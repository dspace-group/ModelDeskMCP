"""Dry-run workflow recipes for ModelDesk MCP use cases."""

from __future__ import annotations

import uuid

from modeldesk_mcp.contracts import ToolError, ToolResult, WorkflowPlan


class WorkflowCatalog:
    """Provides dry-run workflow recipes composed from lower-level MCP tools."""

    def __init__(self) -> None:
        self._session_id = uuid.uuid4().hex

    def list_workflow_plans(self) -> tuple[WorkflowPlan, ...]:
        """Return all registered dry-run recipes in stable name order."""

        return tuple(_WORKFLOW_FACTORIES[name]() for name in sorted(_WORKFLOW_FACTORIES))

    def get_workflow_plan(self, workflow_name: str) -> ToolResult:
        """Return a registered workflow plan by name."""

        if workflow_name.strip() == "":
            error = ToolError("validation", "Workflow name must not be empty.", "modeldesk_get_workflow_plan", "Use one of the documented workflow names.")
            return ToolResult.failure("modeldesk_get_workflow_plan", self._session_id, error)

        normalized_name = workflow_name.strip().lower()
        plan = _WORKFLOW_FACTORIES.get(normalized_name)
        if plan is None:
            error = ToolError("not_found", f"Workflow '{workflow_name}' is not registered.", "modeldesk_get_workflow_plan", "Call with a predefined workflow recipe name.")
            return ToolResult.failure("modeldesk_get_workflow_plan", self._session_id, error)
        return ToolResult.success("modeldesk_get_workflow_plan", self._session_id, plan())


def _create_parameterization_plan() -> WorkflowPlan:
    steps = (
        "Open or verify active project.",
        "Activate the target experiment.",
        "Inspect or set the active model in the active experiment.",
        "List and activate the target parameter set.",
        "Inspect active parameterization metadata and current parameter values.",
        "Set scalar, vector, matrix, table, or text parameter values with explicit paths and JSON payloads.",
        "Save the active parameter set or active project.",
    )
    tools = (
        "modeldesk_open_project",
        "modeldesk_activate_experiment",
        "modeldesk_get_active_model_info",
        "modeldesk_set_active_model",
        "modeldesk_list_parameter_sets",
        "modeldesk_activate_parameter_set",
        "modeldesk_get_parameterization_summary",
        "modeldesk_set_scalar_parameter",
        "modeldesk_set_parameter_value",
        "modeldesk_save_project",
    )
    return WorkflowPlan("parameterize_vehicle_variant", "UC1", True, steps, tools, "Dry-run plan for the UC1 parameterization workflow.")


def _create_road_plan() -> WorkflowPlan:
    steps = (
        "Open or verify active project.",
        "List Environment Pool Road files when the available .rd files are unknown.",
        "Create the target road network in the active project pool with CreateFile(0, name, overwriteExisting) when a new .rd is requested.",
        "Activate or save the target road network (.rd).",
        "List, add, rename, or remove roads inside the active road network.",
        "Create or update typed road segments, including Straight, Circular, Clothoid, and Spline segments.",
        "Configure lane sections and traffic objects at road-relative s/d positions.",
        "Connect road start/end connection points for predecessor/successor style road chains.",
        "Save and download the active road network or active experiment if required.",
    )
    tools = (
        "modeldesk_list_environment_pool_items",
        "modeldesk_create_project_pool_file",
        "modeldesk_create_road_network",
        "modeldesk_activate_road",
        "modeldesk_save_road_network_as",
        "modeldesk_list_roads",
        "modeldesk_add_road",
        "modeldesk_update_road",
        "modeldesk_remove_road",
        "modeldesk_add_road_segment",
        "modeldesk_update_road_segment",
        "modeldesk_remove_road_segment",
        "modeldesk_configure_road_lanes",
        "modeldesk_add_road_object",
        "modeldesk_update_road_object",
        "modeldesk_remove_road_object",
        "modeldesk_connect_roads",
        "modeldesk_disconnect_road",
        "modeldesk_create_basic_road",
        "modeldesk_get_road_summary",
        "modeldesk_save_active_experiment",
        "modeldesk_download_active_experiment",
    )
    return WorkflowPlan("create_basic_road", "UC2", True, steps, tools, "Covers RoadNetwork save-as, multi-road editing, typed segment editing, lane setup, road traffic objects, and road-to-road connection points for the active road network.")


def _create_scenario_plan() -> WorkflowPlan:
    steps = (
        "Activate the target traffic scenario.",
        "List Environment Pool Scenario and Traffic Driver files when the available .xml or .trd files are unknown.",
        "Create the target traffic scenario in the active project pool with CreateFile(1, name, overwriteExisting) when a new scenario file is requested.",
        "Read fellows, maneuver collections, and scenario summary.",
        "Add, update, and remove fellows, including traffic-object and traffic-driver references.",
        "Add, update, and remove maneuvers on the scenario or selected fellows.",
        "Add a fellow, then add its sequence; creation alone does not position it.",
        "Set fellow position with explicit Position -> YawAngleConstant -> Constant JSON and verify longitudinalPosition before saving or downloading.",
        "Set ego sequence StartPosition in meters along the route and InitialLongitudinalVelocity in km/h; verify both returned values.",
        "Set maneuver sequence order and longitudinal/lateral behavior profiles.",
        "Use maneuver control to start, stop, or reset executable scenario behavior.",
        "Save and download the active experiment.",
    )
    tools = (
        "modeldesk_list_environment_pool_items",
        "modeldesk_create_project_pool_file",
        "modeldesk_create_traffic_scenario",
        "modeldesk_activate_scenario",
        "modeldesk_get_scenario_summary",
        "modeldesk_list_scenario_fellows",
        "modeldesk_list_scenario_maneuvers",
        "modeldesk_add_scenario_fellow",
        "modeldesk_update_scenario_fellow",
        "modeldesk_remove_scenario_fellow",
        "modeldesk_add_scenario_maneuver",
        "modeldesk_update_scenario_maneuver",
        "modeldesk_remove_scenario_maneuver",
        "modeldesk_verify_scenario_maneuver_sequence",
        "modeldesk_set_maneuver_behavior_profiles",
        "modeldesk_start_maneuver",
        "modeldesk_stop_maneuver",
        "modeldesk_reset_maneuver",
        "modeldesk_save_active_experiment",
        "modeldesk_download_active_experiment",
    )
    return WorkflowPlan("create_basic_traffic_scenario", "UC3", True, steps, tools, "Covers scenario creation/activation, fellow and maneuver authoring, behavior sequencing/profiles, and executable maneuver control. Fellow creation alone does not set position; verify explicit Position -> YawAngleConstant readback before persistence.")


def _create_processing_plan() -> WorkflowPlan:
    steps = (
        "Activate the experiment and parameter set.",
        "Inspect processing configuration.",
        "Validate measurement input and mapping details from the exposed configuration.",
        "Run parameter-set processing.",
        "Save the project or active experiment.",
    )
    tools = (
        "modeldesk_activate_experiment",
        "modeldesk_activate_parameter_set",
        "modeldesk_get_processing_summary",
        "modeldesk_get_processing_configuration",
        "modeldesk_run_processing",
        "modeldesk_save_project",
    )
    return WorkflowPlan("run_processing_and_save_parameter_set", "UC1", True, steps, tools, "Dry-run plan for measurement-driven parameter processing (part of UC1 parameterization).")


def _create_traffic_object_plan() -> WorkflowPlan:
    steps = (
        "Open or verify active project.",
        "List Environment Pool Objects files when filesystem-backed .tro catalog items are needed.",
        "Read the traffic object catalog summary.",
        "List traffic objects and folders from the active catalog.",
        "Validate traffic object references before road placement or scenario assignment.",
        "Apply catalog mutation tools only after folder/object subtype schemas are verified.",
    )
    tools = (
        "modeldesk_list_environment_pool_items",
        "modeldesk_get_traffic_objects_summary",
        "modeldesk_list_traffic_objects",
        "modeldesk_list_traffic_object_folders",
        "modeldesk_validate_traffic_object_reference",
        "modeldesk_get_scenario_summary",
    )
    return WorkflowPlan("manage_traffic_objects", "UC4", True, steps, tools, "Covers catalog inspection and reference validation; catalog mutation is phased after catalog path semantics are verified.")


def _create_testing_plan() -> WorkflowPlan:
    steps = (
        "Activate the test configuration.",
        "Read logical and concrete test case summary.",
        "List logical and concrete test cases for traceable execution scope selection.",
        "Execute the requested test scope.",
        "Return verdict details and artifact locations when available.",
    )
    tools = (
        "modeldesk_activate_test",
        "modeldesk_get_test_summary",
        "modeldesk_list_logical_test_cases",
        "modeldesk_list_concrete_test_cases",
        "modeldesk_execute_test",
    )
    return WorkflowPlan("execute_regression_test", "Supporting", True, steps, tools, "Dry-run plan for structured simulation testing; supports validation across UC1-UC5 but is not one of the five documented ModelDesk use cases.")


def _create_plotting_plan() -> WorkflowPlan:
    steps = (
        "Activate plotting configuration.",
        "Read capture and layout summary.",
        "List captures and layouts for explicit comparison setup.",
        "Compare selected capture signals with explicit numeric tolerances.",
        "Return structured comparison metrics and the tolerance verdict.",
    )
    tools = (
        "modeldesk_activate_plotting",
        "modeldesk_get_plotting_summary",
        "modeldesk_list_plot_captures",
        "modeldesk_list_plot_layouts",
        "modeldesk_compare_captures",
    )
    return WorkflowPlan("plot_and_compare_two_runs", "UC5", True, steps, tools, "UC5 Analyze and Compare Simulation Results using MATLAB captures from the active project's measurement pool.")


def _create_aurelion_plan() -> WorkflowPlan:
    steps = (
        "Activate project, experiment, road, and scenario.",
        "Download the active experiment if required.",
        "Synchronize the selected system and scenario to AURELION.",
        "Return synchronization result details.",
    )
    tools = (
        "modeldesk_activate_road",
        "modeldesk_activate_scenario",
        "modeldesk_download_active_experiment",
        "modeldesk_synchronize_aurelion",
    )
    return WorkflowPlan("sync_scene_to_aurelion", "UC2/UC3", True, steps, tools, "Dry-run plan for ModelDesk-to-AURELION synchronization; supports the road (UC2) and scenario (UC3) use cases.")


def _create_automation_smoke_plan() -> WorkflowPlan:
    steps = (
        "Read server and ModelDesk status.",
        "Read capability flags for all domains.",
        "Open a project if no active project exists.",
        "List experiments and parameter sets.",
        "Return a concise automation readiness report.",
    )
    tools = (
        "modeldesk_get_status",
        "modeldesk_get_capabilities",
        "modeldesk_open_project",
        "modeldesk_list_experiments",
        "modeldesk_list_parameter_sets",
    )
    return WorkflowPlan("automation_session_smoke", "Supporting", True, steps, tools, "Dry-run plan for validating that the MCP automation session is ready; cross-cutting readiness check, not one of the five documented use cases.")


_WORKFLOW_FACTORIES = {
    "parameterize_vehicle_variant": _create_parameterization_plan,
    "create_basic_road": _create_road_plan,
    "create_basic_traffic_scenario": _create_scenario_plan,
    "manage_traffic_objects": _create_traffic_object_plan,
    "run_processing_and_save_parameter_set": _create_processing_plan,
    "execute_regression_test": _create_testing_plan,
    "plot_and_compare_two_runs": _create_plotting_plan,
    "sync_scene_to_aurelion": _create_aurelion_plan,
    "automation_session_smoke": _create_automation_smoke_plan,
}
