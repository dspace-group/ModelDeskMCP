"""Validation facade between MCP tools and the COM automation gateway.

The service keeps the MCP registration layer thin and preserves the structured
error boundary. Specialized domain operations are delegated to the COM bridge;
general automation, Scenario/TrafficScenario, Road/RoadGenerator,
Plotting/PlotManager, and TrafficObjectManager remain identifiable by their
registered tool names and never bypass the gateway.
"""

from __future__ import annotations

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.contracts import (
    USE_CASE_TITLES,
    ModelDeskDomain,
    Selector,
    ToolError,
    ToolResult,
    list_tools_for_use_case,
    public_error_message,
    resolve_use_case_query,
)
from modeldesk_mcp.domain.workflow_catalog import WorkflowCatalog


class ModelDeskService:
    """Provides typed operations for MCP tools while keeping tool modules thin."""

    def __init__(self, gateway: ModelDeskAutomationGateway, workflows: WorkflowCatalog) -> None:
        if gateway is None:
            raise ValueError("gateway must not be None")
        if workflows is None:
            raise ValueError("workflows must not be None")
        self._gateway = gateway
        self._workflows = workflows

    def add_traffic_object(self, name: str, object3d: str) -> ToolResult:
        """Add a traffic object to the Traffic Object Manager."""
        return self._gateway.add_traffic_object(name, object3d)

    def remove_traffic_object(self, selector_kind: str, selector_value: str, dry_run: bool = False) -> ToolResult:
        """Remove a traffic object by selector (index, name, id, ...)."""
        selector = self._create_selector("modeldesk_remove_traffic_object", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.remove_traffic_object(selector, dry_run)

    def add_traffic_object_folder(self, name: str) -> ToolResult:
        """Add a folder to the Traffic Object Manager."""
        return self._gateway.add_traffic_object_folder(name)

    def remove_traffic_object_folder(self, selector_kind: str, selector_value: str, dry_run: bool = False) -> ToolResult:
        """Remove a folder by selector (name, id, ...)."""
        selector = self._create_selector("modeldesk_remove_traffic_object_folder", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.remove_traffic_object_folder(selector, dry_run)

    def get_status(self) -> ToolResult:
        """Get ModelDesk and MCP bridge status."""

        return self._gateway.get_status()

    def get_capabilities(self) -> ToolResult:
        """Get ModelDesk automation capabilities."""

        return self._gateway.get_capabilities()

    def open_project(self, project_file: str, initial_experiment: str | None, save_active: bool) -> ToolResult:
        """Open a project."""

        return self._gateway.open_project(project_file, initial_experiment, save_active)

    def create_project_pool_file(self, file_type: str, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a project-pool file."""

        return self._gateway.create_project_pool_file(file_type, name, overwrite_existing)

    def create_road_network(self, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a road network project-pool file."""

        return self._gateway.create_road_network(name, overwrite_existing)

    def create_traffic_scenario(self, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a traffic-scenario project-pool file."""

        return self._gateway.create_traffic_scenario(name, overwrite_existing)

    def list_environment_pool_items(self, group: str, recursive: bool, offset: int = 0) -> ToolResult:
        """List Environment Pool items for a group."""

        return self._gateway.list_environment_pool_items(group, recursive, offset)

    def save_project(self) -> ToolResult:
        """Save the active project."""

        return self._gateway.save_project()

    def close_project(self, save: bool, dry_run: bool = False) -> ToolResult:
        """Close the active project."""

        return self._gateway.close_project(save, dry_run)

    def list_experiments(self, offset: int = 0) -> ToolResult:
        """List project experiments."""

        return self._gateway.list_experiments(offset)

    def activate_experiment(self, selector_kind: str, selector_value: str, save_active: bool) -> ToolResult:
        """Activate an experiment."""

        try:
            selector = Selector.create(selector_kind, selector_value)
        except ValueError as exception:
            return self._validation_failure("modeldesk_activate_experiment", public_error_message(exception))
        return self._gateway.activate_experiment(selector, save_active)

    def list_parameter_sets(self, offset: int = 0) -> ToolResult:
        """List parameter sets."""

        return self._gateway.list_parameter_sets(offset)

    def activate_parameter_set(self, selector_kind: str, selector_value: str, save_active: bool) -> ToolResult:
        """Activate a parameter set."""

        try:
            selector = Selector.create(selector_kind, selector_value)
        except ValueError as exception:
            return self._validation_failure("modeldesk_activate_parameter_set", public_error_message(exception))
        return self._gateway.activate_parameter_set(selector, save_active)

    def get_parameterization_summary(self) -> ToolResult:
        """Get active parameterization summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.PARAMETERIZATION, "modeldesk_get_parameterization_summary")

    def get_active_model_info(self) -> ToolResult:
        """Get active model information for the active experiment."""

        return self._gateway.get_active_model_info()

    def set_active_model(self, model_file_path: str, ml_working_directory: str | None, initialization_command: str | None, platform_name: str | None) -> ToolResult:
        """Set active model for the active experiment."""

        return self._gateway.set_active_model(model_file_path, ml_working_directory, initialization_command, platform_name)

    def get_parameter_value(self, parameter_path: str) -> ToolResult:
        """Get a parameter value."""

        return self._gateway.get_parameter_value(parameter_path)

    def set_scalar_parameter(self, parameter_path: str, value: str) -> ToolResult:
        """Set a scalar parameter."""

        return self._gateway.set_scalar_parameter(parameter_path, value)

    def set_parameter_value(self, parameter_path: str, value_kind: str, value_json: str) -> ToolResult:
        """Set a typed parameter value."""

        return self._gateway.set_parameter_value(parameter_path, value_kind, value_json)

    def get_road_summary(self) -> ToolResult:
        """Get active road summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.ROADS, "modeldesk_get_road_summary")

    def activate_road(self, selector_kind: str, selector_value: str) -> ToolResult:
        """Activate a road."""

        try:
            selector = Selector.create(selector_kind, selector_value)
        except ValueError as exception:
            return self._validation_failure("modeldesk_activate_road", public_error_message(exception))
        return self._gateway.activate_road(selector)

    def list_roads(self, offset: int = 0) -> ToolResult:
        """List active-road-network roads."""

        return self._gateway.list_roads(offset)

    def save_road_network_as(self, file_name: str, overwrite_existing: bool) -> ToolResult:
        """Save active road network to file."""

        return self._gateway.save_road_network_as(file_name, overwrite_existing)

    def add_road(self, name: str | None, left_lane_count: int, right_lane_count: int, lane_width: float, save: bool, download: bool) -> ToolResult:
        """Add a road."""

        return self._gateway.add_road(name, left_lane_count, right_lane_count, lane_width, save, download)

    def update_road(self, selector_kind: str, selector_value: str, name: str | None, save: bool, download: bool) -> ToolResult:
        """Update a road."""

        selector = self._create_selector("modeldesk_update_road", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.update_road(selector, name, save, download)

    def remove_road(self, selector_kind: str, selector_value: str, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a road."""

        selector = self._create_selector("modeldesk_remove_road", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.remove_road(selector, save, download, dry_run)

    def add_road_segment(self, selector_kind: str, selector_value: str, segment_type: str, properties_json: str | None, insert_after_segment_index: int, save: bool, download: bool) -> ToolResult:
        """Add a road segment."""

        selector = self._create_selector("modeldesk_add_road_segment", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.add_road_segment(selector, segment_type, properties_json, insert_after_segment_index, save, download)

    def update_road_segment(self, selector_kind: str, selector_value: str, segment_index: int, segment_type: str | None, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update a road segment."""

        selector = self._create_selector("modeldesk_update_road_segment", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.update_road_segment(selector, segment_index, segment_type, properties_json, save, download)

    def remove_road_segment(self, selector_kind: str, selector_value: str, segment_index: int, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a road segment."""

        selector = self._create_selector("modeldesk_remove_road_segment", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.remove_road_segment(selector, segment_index, save, download, dry_run)

    def configure_road_lanes(self, selector_kind: str, selector_value: str, lane_section_index: int, left_lane_count: int, right_lane_count: int, lane_width: float, lane_section_length: float, save: bool, download: bool) -> ToolResult:
        """Configure road lanes."""

        selector = self._create_selector("modeldesk_configure_road_lanes", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.configure_road_lanes(selector, lane_section_index, left_lane_count, right_lane_count, lane_width, lane_section_length, save, download)

    def add_road_object(self, selector_kind: str, selector_value: str, s: float, d: float, name: str | None, catalog_path: str | None, lane_mapping_json: str | None, save: bool, download: bool) -> ToolResult:
        """Add a road object."""

        selector = self._create_selector("modeldesk_add_road_object", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.add_road_object(selector, s, d, name, catalog_path, lane_mapping_json, save, download)

    def update_road_object(self, selector_kind: str, selector_value: str, object_index: int, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update a road object."""

        selector = self._create_selector("modeldesk_update_road_object", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.update_road_object(selector, object_index, properties_json, save, download)

    def remove_road_object(self, selector_kind: str, selector_value: str, object_index: int, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a road object."""

        selector = self._create_selector("modeldesk_remove_road_object", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.remove_road_object(selector, object_index, save, download, dry_run)

    def connect_roads(self, source_selector_kind: str, source_selector_value: str, source_point: str | None, target_selector_kind: str, target_selector_value: str, target_point: str | None, mode: str | None, save: bool, download: bool) -> ToolResult:
        """Connect roads."""

        source_selector = self._create_selector("modeldesk_connect_roads", source_selector_kind, source_selector_value)
        if isinstance(source_selector, ToolResult):
            return source_selector
        target_selector = self._create_selector("modeldesk_connect_roads", target_selector_kind, target_selector_value)
        if isinstance(target_selector, ToolResult):
            return target_selector
        return self._gateway.connect_roads(source_selector, source_point, target_selector, target_point, mode, save, download)

    def disconnect_road(self, selector_kind: str, selector_value: str, connection_point: str | None, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Disconnect a road connection point."""

        selector = self._create_selector("modeldesk_disconnect_road", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.disconnect_road(selector, connection_point, save, download, dry_run)

    def create_basic_road(self, name: str | None, length: float, left_lane_count: int, right_lane_count: int, lane_width: float, traffic_objects_json: str | None, save: bool, download: bool) -> ToolResult:
        """Create a basic road."""

        return self._gateway.create_basic_road(name, length, left_lane_count, right_lane_count, lane_width, traffic_objects_json, save, download)

    def get_scenario_summary(self) -> ToolResult:
        """Get scenario summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.SCENARIOS, "modeldesk_get_scenario_summary")

    def activate_scenario(self, scenario_name: str) -> ToolResult:
        """Activate a traffic scenario."""

        return self._gateway.activate_scenario(scenario_name)

    def list_scenario_fellows(self, offset: int = 0) -> ToolResult:
        """List scenario fellows."""

        return self._gateway.list_scenario_fellows(offset)

    def list_scenario_maneuvers(self, offset: int = 0) -> ToolResult:
        """List scenario maneuvers."""

        return self._gateway.list_scenario_maneuvers(offset)

    def add_scenario_fellow(self, name: str | None, properties_json: str | None, traffic_object_selector_kind: str | None, traffic_object_selector_value: str | None, traffic_object_catalog_path: str | None, traffic_driver_reference: str | None, save: bool, download: bool) -> ToolResult:
        """Add scenario fellow."""

        traffic_object_selector = self._create_optional_selector("modeldesk_add_scenario_fellow", traffic_object_selector_kind, traffic_object_selector_value)
        if isinstance(traffic_object_selector, ToolResult):
            return traffic_object_selector
        return self._gateway.add_scenario_fellow(name, properties_json, traffic_object_selector, traffic_object_catalog_path, traffic_driver_reference, save, download)

    def update_scenario_fellow(self, fellow_selector_kind: str, fellow_selector_value: str, name: str | None, properties_json: str | None, traffic_object_selector_kind: str | None, traffic_object_selector_value: str | None, traffic_object_catalog_path: str | None, traffic_driver_reference: str | None, save: bool, download: bool) -> ToolResult:
        """Update scenario fellow."""

        fellow_selector = self._create_selector("modeldesk_update_scenario_fellow", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        traffic_object_selector = self._create_optional_selector("modeldesk_update_scenario_fellow", traffic_object_selector_kind, traffic_object_selector_value)
        if isinstance(traffic_object_selector, ToolResult):
            return traffic_object_selector
        return self._gateway.update_scenario_fellow(fellow_selector, name, properties_json, traffic_object_selector, traffic_object_catalog_path, traffic_driver_reference, save, download)

    def remove_scenario_fellow(self, fellow_selector_kind: str, fellow_selector_value: str, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove scenario fellow."""

        fellow_selector = self._create_selector("modeldesk_remove_scenario_fellow", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.remove_scenario_fellow(fellow_selector, save, download, dry_run)

    def add_scenario_maneuver(self, fellow_selector_kind: str, fellow_selector_value: str, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Add scenario maneuver."""

        fellow_selector = self._create_selector("modeldesk_add_scenario_maneuver", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.add_scenario_maneuver(fellow_selector, properties_json, save, download)

    def update_scenario_maneuver(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_selector_kind: str, maneuver_selector_value: str, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update scenario maneuver."""

        fellow_selector = self._create_selector("modeldesk_update_scenario_maneuver", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        maneuver_selector = self._create_selector("modeldesk_update_scenario_maneuver", maneuver_selector_kind, maneuver_selector_value)
        if isinstance(maneuver_selector, ToolResult):
            return maneuver_selector
        return self._gateway.update_scenario_maneuver(fellow_selector, maneuver_selector, properties_json, save, download)

    def remove_scenario_maneuver(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_selector_kind: str, maneuver_selector_value: str, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove scenario maneuver."""

        fellow_selector = self._create_selector("modeldesk_remove_scenario_maneuver", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        maneuver_selector = self._create_selector("modeldesk_remove_scenario_maneuver", maneuver_selector_kind, maneuver_selector_value)
        if isinstance(maneuver_selector, ToolResult):
            return maneuver_selector
        return self._gateway.remove_scenario_maneuver(fellow_selector, maneuver_selector, save, download, dry_run)

    def set_scenario_maneuver_sequence(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_selectors_json: str, save: bool, download: bool) -> ToolResult:
        """Set scenario maneuver sequence."""

        fellow_selector = self._create_selector("modeldesk_set_scenario_maneuver_sequence", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.set_scenario_maneuver_sequence(fellow_selector, maneuver_selectors_json, save, download)

    def set_maneuver_behavior_profiles(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_selector_kind: str, maneuver_selector_value: str, longitudinal_profile_json: str | None, lateral_profile_json: str | None, save: bool, download: bool) -> ToolResult:
        """Set maneuver behavior profiles."""

        fellow_selector = self._create_selector("modeldesk_set_maneuver_behavior_profiles", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        maneuver_selector = self._create_selector("modeldesk_set_maneuver_behavior_profiles", maneuver_selector_kind, maneuver_selector_value)
        if isinstance(maneuver_selector, ToolResult):
            return maneuver_selector
        return self._gateway.set_maneuver_behavior_profiles(fellow_selector, maneuver_selector, longitudinal_profile_json, lateral_profile_json, save, download)

    def get_scenario_road(self) -> ToolResult:
        """Return the road reference on the active traffic scenario."""

        return self._gateway.get_scenario_road()

    def set_scenario_road(self, road_name: str, save: bool, download: bool) -> ToolResult:
        """Set the road reference on the active traffic scenario."""

        return self._gateway.set_scenario_road(road_name, save, download)

    def list_fellow_activities(self, fellow_selector_kind: str, fellow_selector_value: str, offset: int = 0) -> ToolResult:
        """List maneuvers/activities for a fellow or the ego vehicle."""

        fellow_selector = self._create_selector("modeldesk_list_fellow_activities", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.list_fellow_activities(fellow_selector, offset)

    def get_vehicle_object_type(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_index: int) -> ToolResult:
        """Return the active 3D object type for a fellow or ego maneuver."""

        fellow_selector = self._create_selector("modeldesk_get_vehicle_object_type", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.get_vehicle_object_type(fellow_selector, maneuver_index)

    def list_vehicle_object_types(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_index: int, offset: int = 0) -> ToolResult:
        """List all available 3D object types for a fellow or ego maneuver."""

        fellow_selector = self._create_selector("modeldesk_list_vehicle_object_types", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.list_vehicle_object_types(fellow_selector, maneuver_index, offset)

    def set_vehicle_object_type(self, fellow_selector_kind: str, fellow_selector_value: str, maneuver_index: int, element_index: int, save: bool, download: bool) -> ToolResult:
        """Activate a 3D object type by index for a fellow or ego maneuver."""

        fellow_selector = self._create_selector("modeldesk_set_vehicle_object_type", fellow_selector_kind, fellow_selector_value)
        if isinstance(fellow_selector, ToolResult):
            return fellow_selector
        return self._gateway.set_vehicle_object_type(fellow_selector, maneuver_index, element_index, save, download)

    def get_traffic_objects_summary(self) -> ToolResult:
        """Get traffic-object summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.TRAFFIC_OBJECTS, "modeldesk_get_traffic_objects_summary")

    def list_traffic_objects(self, offset: int = 0) -> ToolResult:
        """List traffic objects."""

        return self._gateway.list_traffic_objects(offset)

    def list_traffic_object_folders(self, offset: int = 0) -> ToolResult:
        """List traffic-object folders."""

        return self._gateway.list_traffic_object_folders(offset)

    def validate_traffic_object_reference(self, selector_kind: str, selector_value: str) -> ToolResult:
        """Validate a traffic-object reference."""

        selector = self._create_selector("modeldesk_validate_traffic_object_reference", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.validate_traffic_object_reference(selector)

    def get_processing_summary(self) -> ToolResult:
        """Get processing summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.PROCESSING, "modeldesk_get_processing_summary")

    def get_processing_configuration(self) -> ToolResult:
        """Get processing configuration."""

        return self._gateway.get_processing_configuration()

    def run_processing(self) -> ToolResult:
        """Run processing."""

        return self._gateway.run_processing()

    def get_test_summary(self) -> ToolResult:
        """Get testing summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.TESTING, "modeldesk_get_test_summary")

    def activate_test(self, test_name: str) -> ToolResult:
        """Activate a test."""

        return self._gateway.activate_test(test_name)

    def list_logical_test_cases(self, offset: int = 0) -> ToolResult:
        """List logical test cases."""

        return self._gateway.list_logical_test_cases(offset)

    def list_concrete_test_cases(self, logical_test_case_selector_kind: str, logical_test_case_selector_value: str, offset: int = 0) -> ToolResult:
        """List concrete test cases for one logical test case."""

        logical_test_case_selector = self._create_selector("modeldesk_list_concrete_test_cases", logical_test_case_selector_kind, logical_test_case_selector_value)
        if isinstance(logical_test_case_selector, ToolResult):
            return logical_test_case_selector
        return self._gateway.list_concrete_test_cases(logical_test_case_selector, offset)

    def execute_test(self, scope: str, selector_kind: str | None, selector_value: str | None) -> ToolResult:
        """Execute a test scope."""

        return self._gateway.execute_test(scope, selector_kind, selector_value)

    def get_plotting_summary(self) -> ToolResult:
        """Get plotting summary."""

        return self._gateway.get_domain_summary(ModelDeskDomain.PLOTTING, "modeldesk_get_plotting_summary")

    def activate_plotting(self, selector_kind: str, selector_value: str) -> ToolResult:
        """Activate plotting."""

        selector = self._create_selector("modeldesk_activate_plotting", selector_kind, selector_value)
        if isinstance(selector, ToolResult):
            return selector
        return self._gateway.activate_plotting(selector)

    def list_plot_captures(self, offset: int = 0) -> ToolResult:
        """List plot captures."""

        return self._gateway.list_plot_captures(offset)

    def list_plot_layouts(self, offset: int = 0) -> ToolResult:
        """List plot layouts."""

        return self._gateway.list_plot_layouts(offset)

    def compare_captures(
        self,
        reference_capture: str,
        candidate_capture: str,
        signal_specs_json: str,
        tolerances_json: str,
    ) -> ToolResult:
        """Compare two MATLAB captures from the active project's measurement pool."""

        return self._gateway.compare_captures(
            reference_capture,
            candidate_capture,
            signal_specs_json,
            tolerances_json,
        )

    def save_active_experiment(self) -> ToolResult:
        """Save active experiment."""

        return self._gateway.save_active_experiment()

    def download_active_experiment(self) -> ToolResult:
        """Download active experiment."""

        return self._gateway.download_active_experiment()

    def start_maneuver(self, download_if_not_running: bool) -> ToolResult:
        """Start maneuver execution."""

        return self._gateway.start_maneuver(download_if_not_running)

    def stop_maneuver(self) -> ToolResult:
        """Stop maneuver execution."""

        return self._gateway.stop_maneuver()

    def reset_maneuver(self) -> ToolResult:
        """Reset maneuver execution."""

        return self._gateway.reset_maneuver()

    def synchronize_aurelion(self, system: str | None, scenario: str | None) -> ToolResult:
        """Synchronize AURELION."""

        return self._gateway.synchronize_aurelion(system, scenario)

    def get_workflow_plan(self, workflow_name: str) -> ToolResult:
        """Get a dry-run workflow plan."""

        return self._workflows.get_workflow_plan(workflow_name)

    def list_tools_by_use_case(self, use_case: str) -> ToolResult:
        """Resolve a use-case query (e.g. "3", "UC3", "Use Case 3") to its tagged tools."""

        if use_case.strip() == "":
            return self._validation_failure("modeldesk_list_tools_by_use_case", "Use case must not be empty. Provide a value such as '3', 'UC3', or 'Use Case 3'.")

        resolved_tag = resolve_use_case_query(use_case)
        if resolved_tag is None:
            error = ToolError(
                "not_found",
                f"Use case '{use_case}' is not recognized.",
                "modeldesk_list_tools_by_use_case",
                "Use one of UC1-UC5 or 'Supporting', for example 'UC3' or '3'.",
            )
            return ToolResult.failure("modeldesk_list_tools_by_use_case", self._gateway.session_id, error)

        tools = list_tools_for_use_case(resolved_tag)
        data = {
            "useCase": resolved_tag,
            "title": USE_CASE_TITLES.get(resolved_tag, resolved_tag),
            "tools": tools,
            "toolCount": len(tools),
        }
        return ToolResult.success("modeldesk_list_tools_by_use_case", self._gateway.session_id, data)

    def _create_selector(self, operation_name: str, selector_kind: str | None, selector_value: str | None) -> Selector | ToolResult:
        try:
            return Selector.create(selector_kind, selector_value)
        except ValueError as exception:
            return self._validation_failure(operation_name, public_error_message(exception))

    def _create_optional_selector(self, operation_name: str, selector_kind: str | None, selector_value: str | None) -> Selector | None | ToolResult:
        if selector_kind is None or selector_kind.strip() == "":
            return None
        try:
            return Selector.create(selector_kind, selector_value)
        except ValueError as exception:
            return self._validation_failure(operation_name, public_error_message(exception))

    def _validation_failure(self, operation_name: str, message: str) -> ToolResult:
        return _validation_failure(self._gateway.session_id, operation_name, message)


def _validation_failure(session_id: str, operation_name: str, message: str) -> ToolResult:
    from modeldesk_mcp.contracts import ToolError

    error = ToolError("validation", public_error_message(message), operation_name, "Correct the tool input and call the tool again.")
    return ToolResult.failure(operation_name, session_id, error)
