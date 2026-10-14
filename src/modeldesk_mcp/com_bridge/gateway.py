"""COM-backed implementation of ModelDesk MCP operations.

This module is the ModelDesk COM boundary for the five public domains: general
automation, Scenario/TrafficScenario, Road/RoadGenerator, Plotting/PlotManager,
and TrafficObjectManager. Each operation enters COM through ``ComStaDispatcher``;
the gateway keeps only the root application reference and reacquires child
objects from selectors inside the operation that uses them. Results leave this
boundary as structured ``ToolResult`` values, including recoverable failures.
Maneuver-profile writes validate both JSON sides before COM traversal, verify
requested values by reading them back, and persist only after verification.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
import math
import platform
import sys
import uuid
from typing import Any

from modeldesk_mcp import __version__
import modeldesk_mcp.com_bridge.accessor as com
from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import (
    BasicRoadCreatedTrafficObject,
    BasicRoadCreationInfo,
    BasicRoadCreationRequest,
    CapabilityReport,
    DomainSummary,
    ItemSummary,
    ModelDeskDomain,
    ModelDeskStatus,
    OperationInfo,
    ParameterValueEditRequest,
    ParameterValueInfo,
    ProjectInfo,
    ProjectPoolFileCreationInfo,
    ProjectPoolFileCreationRequest,
    ProjectPoolFileType,
    RoadConnectionMode,
    RoadConnectionPointKind,
    RoadObjectProperties,
    RoadSegmentEditRequest,
    RoadSegmentProperties,
    RoadSegmentType,
    RoadSplineParameterSpec,
    RoadVectorSpec,
    Selector,
    SelectorKind,
    ToolError,
    ToolResult,
    public_error_message,
)
from modeldesk_mcp.contracts.requests import (
    EnvironmentPoolGroupRequest,
    ManeuverBehaviorProfileRequest,
    MAX_LANE_COUNT_PER_SIDE,
    MAX_LANE_MAPPING_COUNT,
    MAX_LANE_WIDTH,
    MAX_ROAD_LENGTH,
    parse_scalar_properties_json,
    parse_selector_array_json,
)


ROAD_SIDE_TYPE_LEFT = 0
ROAD_SIDE_TYPE_RIGHT = 1
MAX_OBSERVED_LANE_COUNT = 256
MAX_CONNECTION_POINT_COUNT = 8


class ModelDeskAutomationGateway:
    """Implements ModelDesk MCP operations through a bounded COM bridge."""

    def add_traffic_object(self, name: str, object3d: str) -> ToolResult:
        """Add a traffic object to the Traffic Object Manager."""
        if not name or name.strip() == "":
            return self._validation_failure("modeldesk_add_traffic_object", "Traffic object name must not be empty.")
        # Accept None or empty string for object3d and normalize to empty string
        normalized_object3d = self._normalize_object3d(object3d)

        def operation(application: Any) -> OperationInfo:
            manager = _get_traffic_object_manager(application)
            result = com.invoke_method(manager, "AddTrafficObject", name, normalized_object3d)
            details = com.read_properties(result, "Name", "Path", "CompleteName", "TypeName", "ObjectID")
            details["object3D"] = normalized_object3d
            return OperationInfo("modeldesk_add_traffic_object", True, f"Traffic object '{name}' added.", details)

        return self._execute_com("modeldesk_add_traffic_object", operation)

    def _normalize_object3d(self, object3d: Any) -> str:
        """Normalize object3d input to an empty string accepted by ModelDesk automation.

        Accepts None, empty string, whitespace, or other values and returns a string.
        """
        if object3d is None:
            return ""
        try:
            s = str(object3d)
        except Exception:
            return ""
        if s.strip() == "":
            return ""
        return s

    def remove_traffic_object(self, selector: Selector, dry_run: bool = False) -> ToolResult:
        """Remove a traffic object from the Traffic Object Manager by selector (index, name, id, ...)."""
        if selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_remove_traffic_object", "Selector must not use active.")

        def operation(application: Any) -> OperationInfo:
            manager = _get_traffic_object_manager(application)
            traffic_objects = _get_first_available_property(manager, "TrafficObjects", "Objects")
            obj = com.resolve_item(traffic_objects, selector)
            object_id = com.get_first_string_property(obj, "ObjectID", "Name", "CompleteName")
            if dry_run:
                return _dry_run_preview(
                    "modeldesk_remove_traffic_object",
                    {"objectId": object_id, "selectorKind": selector.by.value, "selectorValue": selector.value},
                )
            result = com.invoke_method(manager, "RemoveTrafficObject", object_id)
            if isinstance(result, bool) and not result:
                raise RuntimeError("Traffic object removal returned false.")
            details = {"objectId": object_id, "selectorKind": selector.by.value, "selectorValue": selector.value}
            return OperationInfo("modeldesk_remove_traffic_object", True, "Traffic object removed.", details)

        return self._execute_com("modeldesk_remove_traffic_object", operation)

    def add_traffic_object_folder(self, name: str) -> ToolResult:
        """Add a folder to the Traffic Object Manager."""
        if not name or name.strip() == "":
            return self._validation_failure("modeldesk_add_traffic_object_folder", "Folder name must not be empty.")

        def operation(application: Any) -> OperationInfo:
            manager = _get_traffic_object_manager(application)
            result = com.invoke_method(manager, "AddFolder", name)
            details = com.read_properties(result, "Name", "Path", "CompleteName", "TypeName")
            return OperationInfo("modeldesk_add_traffic_object_folder", True, f"Traffic object folder '{name}' added.", details)

        return self._execute_com("modeldesk_add_traffic_object_folder", operation)

    def remove_traffic_object_folder(self, selector: Selector, dry_run: bool = False) -> ToolResult:
        """Remove a folder from the Traffic Object Manager by selector (name, id, ...)."""
        if selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_remove_traffic_object_folder", "Selector must not use active.")

        def operation(application: Any) -> OperationInfo:
            manager = _get_traffic_object_manager(application)
            folders = _get_required_property(manager, "Folders")
            folder = com.resolve_item(folders, selector)
            folder_name = com.get_first_string_property(folder, "Name", "CompleteName")
            if dry_run:
                return _dry_run_preview(
                    "modeldesk_remove_traffic_object_folder",
                    {"folderName": folder_name, "selectorKind": selector.by.value, "selectorValue": selector.value},
                )
            result = com.invoke_method(manager, "RemoveFolder", folder_name)
            if isinstance(result, bool) and not result:
                raise RuntimeError("Traffic object folder removal returned false.")
            details = {"folderName": folder_name, "selectorKind": selector.by.value, "selectorValue": selector.value}
            return OperationInfo("modeldesk_remove_traffic_object_folder", True, "Traffic object folder removed.", details)

        return self._execute_com("modeldesk_remove_traffic_object_folder", operation)

    def __init__(self, dispatcher: ComStaDispatcher, options: ComGatewayOptions) -> None:
        if dispatcher is None:
            raise ValueError("dispatcher must not be None")
        if options is None:
            raise ValueError("options must not be None")
        from modeldesk_mcp.domain.capture_comparison import compare_capture_files

        self._dispatcher = dispatcher
        self._options = options
        self._session_id = uuid.uuid4().hex
        self._application: Any | None = None
        self._compare_capture_files = compare_capture_files

    @property
    def session_id(self) -> str:
        """Return the gateway session identifier."""

        return self._session_id

    def get_status(self) -> ToolResult:
        """Return ModelDesk MCP server status and active project state."""

        return self._execute_com("modeldesk_get_status", self._get_status_core)

    def get_capabilities(self) -> ToolResult:
        """Return ModelDesk Automation capability flags."""

        return self._execute_com("modeldesk_get_capabilities", self._get_capabilities_core)

    def open_project(self, project_file: str, initial_experiment: str | None, save_active: bool) -> ToolResult:
        """Open a ModelDesk project and optionally activate an initial experiment."""

        if project_file.strip() == "":
            return self._validation_failure("modeldesk_open_project", "Project file path must not be empty.")
        if not Path(project_file).is_file():
            return self._validation_failure("modeldesk_open_project", f"Project file '{project_file}' does not exist.")

        def operation(application: Any) -> ProjectInfo:
            com.invoke_method(application, "OpenProject", project_file, initial_experiment or "", save_active)
            return self._get_project_info_core(application)

        return self._execute_com("modeldesk_open_project", operation)

    def create_project_pool_file(self, file_type: str | None, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a project-pool file through ActiveProject.Pool.CreateFile."""

        try:
            request = ProjectPoolFileCreationRequest.create(file_type, name, overwrite_existing)
        except ValueError as exception:
            return self._validation_failure("modeldesk_create_project_pool_file", public_error_message(exception))
        return self._execute_com("modeldesk_create_project_pool_file", lambda application: self._create_project_pool_file_core(application, request))

    def create_road_network(self, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a RoadNetwork file through ActiveProject.Pool.CreateFile."""

        try:
            request = ProjectPoolFileCreationRequest.create(ProjectPoolFileType.ROAD_NETWORK, name, overwrite_existing)
        except ValueError as exception:
            return self._validation_failure("modeldesk_create_road_network", public_error_message(exception))
        return self._execute_com("modeldesk_create_road_network", lambda application: self._create_project_pool_file_core(application, request))

    def create_traffic_scenario(self, name: str, overwrite_existing: bool) -> ToolResult:
        """Create a Traffic Scenario file through ActiveProject.Pool.CreateFile."""

        try:
            request = ProjectPoolFileCreationRequest.create(ProjectPoolFileType.TRAFFIC_SCENARIO, name, overwrite_existing)
        except ValueError as exception:
            return self._validation_failure("modeldesk_create_traffic_scenario", public_error_message(exception))
        return self._execute_com("modeldesk_create_traffic_scenario", lambda application: self._create_project_pool_file_core(application, request))

    def list_environment_pool_items(self, group: str | None, recursive: bool, offset: int = 0) -> ToolResult:
        """List files in one active-project Environment Pool group."""

        try:
            request = EnvironmentPoolGroupRequest.create(group, recursive)
        except ValueError as exception:
            return self._validation_failure("modeldesk_list_environment_pool_items", public_error_message(exception))
        return self._execute_com("modeldesk_list_environment_pool_items", lambda application: self._list_environment_pool_items_core(application, request, offset))

    def save_project(self) -> ToolResult:
        """Save the active project."""

        return self._execute_com("modeldesk_save_project", lambda application: self._invoke_project_method(application, "Save", "Active project saved."))

    def close_project(self, save: bool, dry_run: bool = False) -> ToolResult:
        """Close the active project."""

        def operation(application: Any) -> OperationInfo:
            project = _get_active_project(application)
            if dry_run:
                details = {
                    "projectName": com.get_first_string_property(project, "Name", "ProjectName"),
                    "unsavedChanges": "unknown",
                }
                return _dry_run_preview(
                    "modeldesk_close_project",
                    details,
                    save=save,
                    message="Dry-run preview; project was not closed and unsaved changes were not inspected.",
                )
            com.invoke_method(project, "Close", save)
            return OperationInfo("modeldesk_close_project", True, "Active project closed.")

        return self._execute_com("modeldesk_close_project", operation)

    def list_experiments(self, offset: int = 0) -> ToolResult:
        """List experiments in the active project."""

        return self._execute_com(
            "modeldesk_list_experiments",
            lambda application: self._create_collection_summary("experiments", _get_required_property(_get_active_project(application), "Experiments"), "experiment", offset),
        )

    def activate_experiment(self, selector: Selector, save_active: bool) -> ToolResult:
        """Activate an experiment by selector."""

        def operation(application: Any) -> OperationInfo:
            experiments = _get_required_property(_get_active_project(application), "Experiments")
            experiment = com.resolve_item(experiments, selector)
            com.invoke_method(experiment, "Activate", save_active)
            return OperationInfo("modeldesk_activate_experiment", True, "Experiment activated.")

        return self._execute_com("modeldesk_activate_experiment", operation)

    def list_parameter_sets(self, offset: int = 0) -> ToolResult:
        """List parameter sets in the active experiment."""

        return self._execute_com(
            "modeldesk_list_parameter_sets",
            lambda application: self._create_collection_summary("parameterization.parameterSets", _get_required_property(_get_active_experiment(application), "ParameterSets"), "parameterSet", offset),
        )

    def activate_parameter_set(self, selector: Selector, save_active: bool) -> ToolResult:
        """Activate a parameter set by selector."""

        def operation(application: Any) -> OperationInfo:
            parameter_sets = _get_required_property(_get_active_experiment(application), "ParameterSets")
            parameter_set = com.resolve_item(parameter_sets, selector)
            com.invoke_method(parameter_set, "Activate", save_active)
            return OperationInfo("modeldesk_activate_parameter_set", True, "Parameter set activated.")

        return self._execute_com("modeldesk_activate_parameter_set", operation)

    def get_active_model_info(self) -> ToolResult:
        """Read active model information in the active experiment."""

        def operation(application: Any) -> DomainSummary:
            models = _get_required_property(_get_active_experiment(application), "Models")
            active_model_info = _get_required_property(models, "ActiveModelInfo")
            properties = _read_model_info_properties(active_model_info)
            return self._create_object_summary("parameterization.activeModel", active_model_info, properties)

        return self._execute_com("modeldesk_get_active_model_info", operation)

    def set_active_model(self, model_file_path: str, ml_working_directory: str | None, initialization_command: str | None, platform_name: str | None) -> ToolResult:
        """Set active model in the active experiment."""

        if model_file_path.strip() == "":
            return self._validation_failure("modeldesk_set_active_model", "Model file path must not be empty.")

        normalized_ml_working_directory = "" if ml_working_directory is None else ml_working_directory
        normalized_initialization_command = "" if initialization_command is None else initialization_command
        normalized_platform_name = "" if platform_name is None else platform_name

        def operation(application: Any) -> OperationInfo:
            models = _get_required_property(_get_active_experiment(application), "Models")
            model_info = com.invoke_method(
                models,
                "SetActiveModel",
                model_file_path,
                normalized_ml_working_directory,
                normalized_initialization_command,
                normalized_platform_name,
            )
            details = _read_model_info_properties(model_info)
            return OperationInfo("modeldesk_set_active_model", True, "Active model set.", details)

        return self._execute_com("modeldesk_set_active_model", operation)

    def get_parameter_value(self, parameter_path: str) -> ToolResult:
        """Read one parameter value from the active parameter set."""

        if parameter_path.strip() == "":
            return self._validation_failure("modeldesk_get_parameter_value", "Parameter path must not be empty.")
        return self._execute_com("modeldesk_get_parameter_value", lambda application: self._get_parameter_value_core(application, parameter_path))

    def set_scalar_parameter(self, parameter_path: str, value: str) -> ToolResult:
        """Write a scalar parameter value."""

        if parameter_path.strip() == "":
            return self._validation_failure("modeldesk_set_scalar_parameter", "Parameter path must not be empty.")
        try:
            parsed_value = float(value)
        except ValueError:
            return self._validation_failure("modeldesk_set_scalar_parameter", "Value must be a floating point number using invariant culture.")
        if not math.isfinite(parsed_value):
            return self._validation_failure("modeldesk_set_scalar_parameter", "Value must be a finite floating point number.")

        def operation(application: Any) -> ParameterValueInfo:
            parameter = self._find_parameter(application, parameter_path)
            com.set_property(parameter, "V", parsed_value)
            return self._read_parameter_value(parameter, parameter_path)

        return self._execute_com("modeldesk_set_scalar_parameter", operation)

    def set_parameter_value(self, parameter_path: str, value_kind: str | None, value_json: str) -> ToolResult:
        """Write a scalar, text, vector, matrix, or table parameter value."""

        if parameter_path.strip() == "":
            return self._validation_failure("modeldesk_set_parameter_value", "Parameter path must not be empty.")
        try:
            request = ParameterValueEditRequest.create(value_kind, value_json)
        except ValueError as exception:
            return self._validation_failure("modeldesk_set_parameter_value", public_error_message(exception))

        def operation(application: Any) -> ParameterValueInfo:
            parameter = self._find_parameter(application, parameter_path)
            com.set_property(parameter, "V", request.com_value)
            return self._read_parameter_value(parameter, parameter_path)

        return self._execute_com("modeldesk_set_parameter_value", operation)

    def get_domain_summary(self, domain: ModelDeskDomain, operation_name: str) -> ToolResult:
        """Return a COM-backed domain summary."""

        return self._execute_com(operation_name, lambda application: self._get_domain_summary_core(application, domain))

    def activate_road(self, selector: Selector) -> ToolResult:
        """Activate a road or RoadNetwork by selector."""

        def operation(application: Any) -> OperationInfo:
            active_experiment = _get_active_experiment(application)
            com.invoke_method(active_experiment, "ActivateRoad", selector.to_com_value())
            return OperationInfo("modeldesk_activate_road", True, "Road activated.")

        return self._execute_com("modeldesk_activate_road", operation)

    def list_roads(self, offset: int = 0) -> ToolResult:
        """List roads in the active road network."""

        return self._execute_com(
            "modeldesk_list_roads",
            lambda application: self._create_collection_summary("roads.roads", _get_required_property(_get_active_road_network(application), "Roads"), "road", offset),
        )

    def save_road_network_as(self, file_name: str, overwrite_existing: bool) -> ToolResult:
        """Save the active road network to an absolute .rd path."""

        try:
            normalized_file_name = _normalize_road_network_file_name(file_name, overwrite_existing)
        except (ValueError, OSError) as exception:
            return self._validation_failure("modeldesk_save_road_network_as", public_error_message(exception))

        def operation(application: Any) -> OperationInfo:
            road_network = _get_active_road_network(application)
            com.invoke_method(road_network, "SaveAs", normalized_file_name, overwrite_existing)
            details = {"fileName": normalized_file_name, "overwriteExisting": str(overwrite_existing)}
            return OperationInfo("modeldesk_save_road_network_as", True, "Active road network saved to file.", details)

        return self._execute_com("modeldesk_save_road_network_as", operation)

    def add_road(self, name: str | None, left_lane_count: int, right_lane_count: int, lane_width: float, save: bool, download: bool) -> ToolResult:
        """Add a road to the active road network."""

        try:
            _validate_lane_configuration(left_lane_count, right_lane_count, lane_width)
        except ValueError as exception:
            return self._validation_failure("modeldesk_add_road", public_error_message(exception))
        return self._execute_com("modeldesk_add_road", lambda application: self._add_road_core(application, name, left_lane_count, right_lane_count, lane_width, save, download))

    def update_road(self, selector: Selector, name: str | None, save: bool, download: bool) -> ToolResult:
        """Update a road in the active road network."""

        normalized_name = _normalize_optional_text(name)
        if normalized_name is None:
            return self._validation_failure("modeldesk_update_road", "Road name must not be empty.")
        return self._execute_com("modeldesk_update_road", lambda application: self._update_road_core(application, selector, normalized_name, save, download))

    def remove_road(self, selector: Selector, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a road from the active road network."""

        return self._execute_com("modeldesk_remove_road", lambda application: self._remove_road_core(application, selector, save, download, dry_run))

    def add_road_segment(self, selector: Selector, segment_type: str | None, properties_json: str | None, insert_after_segment_index: int, save: bool, download: bool) -> ToolResult:
        """Add a typed road segment."""

        try:
            request = RoadSegmentEditRequest.create(segment_type, properties_json, insert_after_segment_index, save, download, True)
        except ValueError as exception:
            return self._validation_failure("modeldesk_add_road_segment", public_error_message(exception))
        return self._execute_com("modeldesk_add_road_segment", lambda application: self._add_road_segment_core(application, selector, request))

    def update_road_segment(self, selector: Selector, segment_index: int, segment_type: str | None, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update a selected road segment."""

        if segment_index < 0:
            return self._validation_failure("modeldesk_update_road_segment", "Segment index must be a non-negative integer.")
        try:
            request = RoadSegmentEditRequest.create(segment_type, properties_json, -1, save, download, False)
        except ValueError as exception:
            return self._validation_failure("modeldesk_update_road_segment", public_error_message(exception))
        return self._execute_com("modeldesk_update_road_segment", lambda application: self._update_road_segment_core(application, selector, segment_index, request))

    def remove_road_segment(self, selector: Selector, segment_index: int, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a selected road segment."""

        if segment_index < 0:
            return self._validation_failure("modeldesk_remove_road_segment", "Segment index must be a non-negative integer.")
        return self._execute_com("modeldesk_remove_road_segment", lambda application: self._remove_road_segment_core(application, selector, segment_index, save, download, dry_run))

    def configure_road_lanes(self, selector: Selector, lane_section_index: int, left_lane_count: int, right_lane_count: int, lane_width: float, lane_section_length: float, save: bool, download: bool) -> ToolResult:
        """Configure lane counts and lane width for a selected lane section."""

        try:
            if lane_section_index < 0:
                raise ValueError("Lane section index must be a non-negative integer.")
            _validate_lane_configuration(left_lane_count, right_lane_count, lane_width)
            if lane_section_length < 0.0 or not _is_finite(lane_section_length):
                raise ValueError("Lane section length must be finite and >= 0. Use 0 to keep the current length.")
        except ValueError as exception:
            return self._validation_failure("modeldesk_configure_road_lanes", public_error_message(exception))
        return self._execute_com(
            "modeldesk_configure_road_lanes",
            lambda application: self._configure_road_lanes_core(application, selector, lane_section_index, left_lane_count, right_lane_count, lane_width, lane_section_length, save, download),
        )

    def add_road_object(self, selector: Selector, s: float, d: float, name: str | None, catalog_path: str | None, lane_mapping_json: str | None, save: bool, download: bool) -> ToolResult:
        """Add a road object at road-relative coordinates."""

        try:
            _validate_road_object_position(s, d, MAX_ROAD_LENGTH)
            lane_mapping = RoadObjectProperties.parse_lane_mapping(lane_mapping_json)
        except ValueError as exception:
            return self._validation_failure("modeldesk_add_road_object", public_error_message(exception))
        return self._execute_com("modeldesk_add_road_object", lambda application: self._add_road_object_core(application, selector, s, d, name, catalog_path, lane_mapping, save, download))

    def update_road_object(self, selector: Selector, object_index: int, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update a road-local traffic object."""

        if object_index < 0:
            return self._validation_failure("modeldesk_update_road_object", "Road object index must be a non-negative integer.")
        try:
            properties = RoadObjectProperties.create(properties_json)
        except ValueError as exception:
            return self._validation_failure("modeldesk_update_road_object", public_error_message(exception))
        return self._execute_com("modeldesk_update_road_object", lambda application: self._update_road_object_core(application, selector, object_index, properties, save, download))

    def remove_road_object(self, selector: Selector, object_index: int, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a road-local traffic object."""

        if object_index < 0:
            return self._validation_failure("modeldesk_remove_road_object", "Road object index must be a non-negative integer.")
        return self._execute_com("modeldesk_remove_road_object", lambda application: self._remove_road_object_core(application, selector, object_index, save, download, dry_run))

    def connect_roads(self, source_selector: Selector, source_point: str | None, target_selector: Selector, target_point: str | None, mode: str | None, save: bool, download: bool) -> ToolResult:
        """Connect two road connection points."""

        try:
            parsed_source_point = _parse_connection_point(source_point, RoadConnectionPointKind.END)
            parsed_target_point = _parse_connection_point(target_point, RoadConnectionPointKind.START)
            parsed_mode = _parse_connection_mode(mode)
        except ValueError as exception:
            return self._validation_failure("modeldesk_connect_roads", public_error_message(exception))
        return self._execute_com("modeldesk_connect_roads", lambda application: self._connect_roads_core(application, source_selector, parsed_source_point, target_selector, parsed_target_point, parsed_mode, save, download))

    def disconnect_road(self, selector: Selector, connection_point: str | None, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Disconnect a selected road connection point."""

        try:
            parsed_connection_point = _parse_connection_point(connection_point, RoadConnectionPointKind.END)
        except ValueError as exception:
            return self._validation_failure("modeldesk_disconnect_road", public_error_message(exception))
        return self._execute_com("modeldesk_disconnect_road", lambda application: self._disconnect_road_core(application, selector, parsed_connection_point, save, download, dry_run))

    def create_basic_road(self, name: str | None, length: float, left_lane_count: int, right_lane_count: int, lane_width: float, traffic_objects_json: str | None, save: bool, download: bool) -> ToolResult:
        """Create a simple straight road in the active road network."""

        try:
            request = BasicRoadCreationRequest.create(name, length, left_lane_count, right_lane_count, lane_width, traffic_objects_json, save, download)
        except ValueError as exception:
            return self._validation_failure("modeldesk_create_basic_road", public_error_message(exception))
        return self._execute_com("modeldesk_create_basic_road", lambda application: self._create_basic_road_core(application, request))

    def activate_scenario(self, scenario_name: str) -> ToolResult:
        """Activate a traffic scenario by name."""

        if scenario_name.strip() == "":
            return self._validation_failure("modeldesk_activate_scenario", "Scenario name must not be empty.")
        return self._execute_com("modeldesk_activate_scenario", lambda application: self._activate_experiment_named_method(application, "ActivateTrafficScenario", scenario_name, "modeldesk_activate_scenario", "Traffic scenario activated."))

    def list_scenario_fellows(self, offset: int = 0) -> ToolResult:
        """List fellows or traffic participants in the active scenario."""

        return self._execute_com("modeldesk_list_scenario_fellows", lambda application: self._create_collection_summary("scenarios.fellows", _get_scenario_fellows_collection(application), "fellow", offset))

    def list_scenario_maneuvers(self, offset: int = 0) -> ToolResult:
        """List maneuvers in the active traffic scenario."""

        return self._execute_com("modeldesk_list_scenario_maneuvers", lambda application: self._create_first_available_collection_summary("scenarios.maneuvers", _get_active_traffic_scenario(application), "maneuver", "Maneuvers", "Maneuver", offset=offset))

    def add_scenario_fellow(self, name: str | None, properties_json: str | None, traffic_object_selector: Selector | None, traffic_object_catalog_path: str | None, traffic_driver_reference: str | None, save: bool, download: bool) -> ToolResult:
        """Add a fellow or traffic participant to the active scenario."""

        if traffic_object_selector is not None and traffic_object_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_add_scenario_fellow", "Traffic object selector must not use active.")
        return self._execute_com("modeldesk_add_scenario_fellow", lambda application: self._add_scenario_fellow_core(application, Selector.active(), name, properties_json, traffic_object_selector, traffic_object_catalog_path, traffic_driver_reference, save, download))

    def update_scenario_fellow(self, fellow_selector: Selector, name: str | None, properties_json: str | None, traffic_object_selector: Selector | None, traffic_object_catalog_path: str | None, traffic_driver_reference: str | None, save: bool, download: bool) -> ToolResult:
        """Update a fellow or traffic participant in the active scenario."""

        if fellow_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_update_scenario_fellow", "Fellow selector must not use active.")
        if traffic_object_selector is not None and traffic_object_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_update_scenario_fellow", "Traffic object selector must not use active.")
        return self._execute_com("modeldesk_update_scenario_fellow", lambda application: self._add_scenario_fellow_core(application, fellow_selector, name, properties_json, traffic_object_selector, traffic_object_catalog_path, traffic_driver_reference, save, download))

    def remove_scenario_fellow(self, fellow_selector: Selector, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a fellow or traffic participant."""

        if fellow_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_remove_scenario_fellow", "Fellow selector must not use active.")

        def operation(application: Any) -> OperationInfo:
            fellows = _get_scenario_fellows_collection(application)
            index_selector = _fellow_selector_to_index_selector(fellows, fellow_selector)
            if dry_run:
                fellow = com.resolve_item(fellows, index_selector)
                details = {
                    "fellowName": com.get_first_string_property(fellow, "Name", "CompleteName"),
                    "fellowSelectorKind": fellow_selector.by.value,
                    "fellowSelectorValue": fellow_selector.value,
                }
                return _dry_run_preview("modeldesk_remove_scenario_fellow", details, save, download)
            _remove_collection_item(fellows, index_selector, "fellow")
            details = {"fellowSelectorKind": fellow_selector.by.value, "fellowSelectorValue": fellow_selector.value}
            _apply_scenario_save_download(application, save, download, details)
            return OperationInfo("modeldesk_remove_scenario_fellow", True, "Scenario fellow removed.", details)

        return self._execute_com("modeldesk_remove_scenario_fellow", operation)

    def add_scenario_maneuver(self, fellow_selector: Selector, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Add a maneuver to the active scenario or selected fellow."""

        return self._execute_com("modeldesk_add_scenario_maneuver", lambda application: self._add_or_update_scenario_maneuver_core(application, fellow_selector, Selector.active(), properties_json, save, download, "modeldesk_add_scenario_maneuver", True))

    def update_scenario_maneuver(self, fellow_selector: Selector, maneuver_selector: Selector, properties_json: str | None, save: bool, download: bool) -> ToolResult:
        """Update a maneuver in the active scenario or selected fellow."""

        if maneuver_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_update_scenario_maneuver", "Maneuver selector must not use active.")
        return self._execute_com("modeldesk_update_scenario_maneuver", lambda application: self._add_or_update_scenario_maneuver_core(application, fellow_selector, maneuver_selector, properties_json, save, download, "modeldesk_update_scenario_maneuver", False))

    def remove_scenario_maneuver(self, fellow_selector: Selector, maneuver_selector: Selector, save: bool, download: bool, dry_run: bool = False) -> ToolResult:
        """Remove a maneuver from the active scenario or selected fellow."""

        if maneuver_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_remove_scenario_maneuver", "Maneuver selector must not use active.")

        def operation(application: Any) -> OperationInfo:
            maneuvers = _get_scenario_maneuvers_collection(application, fellow_selector)
            if dry_run:
                maneuver = com.resolve_item(maneuvers, maneuver_selector)
                details = {
                    "fellowSelectorKind": fellow_selector.by.value,
                    "fellowSelectorValue": fellow_selector.value,
                    "maneuverSelectorKind": maneuver_selector.by.value,
                    "maneuverSelectorValue": maneuver_selector.value,
                    "maneuverName": com.get_first_string_property(maneuver, "Name", "CompleteName"),
                }
                return _dry_run_preview("modeldesk_remove_scenario_maneuver", details, save, download)
            _remove_collection_item(maneuvers, maneuver_selector, "maneuver")
            details = {
                "fellowSelectorKind": fellow_selector.by.value,
                "fellowSelectorValue": fellow_selector.value,
                "maneuverSelectorKind": maneuver_selector.by.value,
                "maneuverSelectorValue": maneuver_selector.value,
            }
            _apply_scenario_save_download(application, save, download, details)
            return OperationInfo("modeldesk_remove_scenario_maneuver", True, "Scenario maneuver removed.", details)

        return self._execute_com("modeldesk_remove_scenario_maneuver", operation)

    def set_scenario_maneuver_sequence(self, fellow_selector: Selector, maneuver_selectors_json: str, save: bool, download: bool) -> ToolResult:
        """Confirm an existing order or report that reordering is unsupported.

        The verified automation interface exposes an immutable maneuver Index
        and no reorder member. This method never writes ordering properties:
        changed order fails before persistence, while a matching order is a no-op.
        """

        def operation(application: Any) -> OperationInfo:
            maneuver_selectors = parse_selector_array_json(maneuver_selectors_json, "maneuverSelectorsJson")
            if len(maneuver_selectors) == 0:
                raise ValueError("At least one maneuver selector is required.")
            maneuvers = _get_scenario_maneuvers_collection(application, fellow_selector)
            for sequence_index, selector in enumerate(maneuver_selectors):
                current_maneuver = _invoke_required_item(maneuvers, sequence_index, "maneuver")
                requested_maneuver = com.resolve_item(maneuvers, selector)
                current_index = _read_int_property(current_maneuver, "Index")
                requested_index = _read_int_property(requested_maneuver, "Index")
                if requested_index != current_index:
                    raise RuntimeError(
                        "Reordering is unsupported: the verified automation interface exposes only immutable "
                        "Maneuver.Index and no reorder member."
                    )
            details = {
                "fellowSelectorKind": fellow_selector.by.value,
                "fellowSelectorValue": fellow_selector.value,
                "assignedCount": "0",
            }
            _apply_scenario_save_download(application, save, download, details)
            return OperationInfo(
                "modeldesk_set_scenario_maneuver_sequence",
                True,
                "Requested maneuver order already matches the current order; no reorder was applied.",
                details,
            )

        return self._execute_com("modeldesk_set_scenario_maneuver_sequence", operation)

    def set_maneuver_behavior_profiles(self, fellow_selector: Selector, maneuver_selector: Selector, longitudinal_profile_json: str | None, lateral_profile_json: str | None, save: bool, download: bool) -> ToolResult:
        """Apply and verify ego sequence or fellow profile values before persistence.

        The active fellow selector targets the ego sequence's direct StartPosition and
        InitialLongitudinalVelocity members; values are passed through unchanged (meters
        along the route and km/h). A fellow selector targets only Segments.Item(0).Activity
        and selects either Position -> YawAngleConstant or Velocity -> Constant; a segment
        has only one active longitudinal profile. Both JSON sides are
        validated before COM traversal; failures after profile activation or assignment may
        leave partial in-memory changes, which this operation does not roll back. Save and
        Download run only after every requested value has been read back successfully.
        """

        try:
            fellow_selector.validate()
            maneuver_selector.validate()
            if maneuver_selector.by == SelectorKind.ACTIVE:
                raise ValueError("Maneuver selector must not use active.")
            request = ManeuverBehaviorProfileRequest.create(
                fellow_selector,
                longitudinal_profile_json,
                lateral_profile_json,
            )
        except ValueError as exception:
            return self._validation_failure(
                "modeldesk_set_maneuver_behavior_profiles",
                public_error_message(exception),
            )

        def operation(application: Any) -> OperationInfo:
            mutation_started = False
            save_completed = False
            phase = "resolving the selected maneuver sequence"

            def mark_mutation() -> None:
                nonlocal mutation_started
                mutation_started = True

            try:
                maneuvers = _get_scenario_maneuvers_collection(application, fellow_selector)
                sequence = com.resolve_item(maneuvers, maneuver_selector)
                updated_count = 0
                details: dict[str, str | None] = {
                    "fellowSelectorKind": fellow_selector.by.value,
                    "fellowSelectorValue": fellow_selector.value,
                    "maneuverSelectorKind": maneuver_selector.by.value,
                    "maneuverSelectorValue": maneuver_selector.value,
                }

                if request.longitudinal_properties:
                    if fellow_selector.by == SelectorKind.ACTIVE:
                        ego_sequence = _resolve_ego_maneuver_sequence(sequence)
                        detail_names = {
                            "StartPosition": "startPosition",
                            "InitialLongitudinalVelocity": "initialLongitudinalVelocity",
                        }
                        for property_name, requested_value in request.longitudinal_properties.items():
                            phase = f"setting ego sequence {property_name}"
                            mark_mutation()
                            actual_value = _set_and_verify_profile_property(
                                ego_sequence,
                                property_name,
                                requested_value,
                                "ego sequence",
                            )
                            details[detail_names[property_name]] = str(actual_value)
                            updated_count += 1
                    else:
                        phase = "reading the selected fellow sequence segments"
                        segments = _get_required_property(sequence, "Segments")
                        if com.get_count(segments) <= 0:
                            raise RuntimeError("The selected fellow sequence has no segments; no segment was created.")
                        segment = com.invoke_item(segments, 0)
                        if segment is None:
                            raise RuntimeError("The selected fellow sequence's first segment could not be read.")
                        activity = _get_required_property(segment, "Activity")
                        longitudinal_type = _get_required_property(activity, "LongitudinalType")
                        profile_name, source_properties = next(iter(request.longitudinal_properties.items()))
                        source_name, constant_properties = next(iter(source_properties.items()))

                        phase = f"activating the fellow {profile_name} profile"
                        longitudinal_profile = _activate_available_profile_element(
                            longitudinal_type,
                            profile_name,
                            "longitudinal profile",
                            mark_mutation,
                        )
                        source_type = _get_required_property(longitudinal_profile, "SourceType")
                        phase = f"activating the fellow {source_name} source"
                        longitudinal_source = _activate_available_profile_element(
                            source_type,
                            source_name,
                            f"{profile_name} source",
                            mark_mutation,
                        )
                        requested_value = constant_properties["Constant"]
                        phase = f"setting and reading back fellow {profile_name}.Constant"
                        actual_value = _set_and_verify_profile_property(
                            longitudinal_source,
                            "Constant",
                            requested_value,
                            f"fellow {profile_name}.{source_name}",
                        )
                        detail_name = "longitudinalPosition" if profile_name == "Position" else "longitudinalVelocity"
                        details[detail_name] = str(actual_value)
                        updated_count += 1

                if request.lateral_properties:
                    phase = "resolving the existing lateral profile target"
                    lateral_target = _get_first_available_property(
                        sequence,
                        "LateralBehavior",
                        "LateralProfile",
                        "Lateral",
                    )
                    phase = "applying and reading back lateral profile properties"
                    updated_count += _apply_verified_scalar_properties(
                        lateral_target,
                        request.lateral_properties,
                        "lateralProfileJson",
                        mark_mutation,
                    )

                details["updatedPropertyCount"] = str(updated_count)
                active_experiment = None
                if save or download:
                    phase = "resolving the active experiment for persistence"
                    active_experiment = _get_active_experiment(application)
                if save:
                    phase = "Save"
                    _invoke_boolean_aware_method(active_experiment, "Save")
                    save_completed = True
                if download:
                    phase = "Download"
                    _invoke_boolean_aware_method(active_experiment, "Download")
                details["saved"] = str(save)
                details["downloaded"] = str(download)
                return OperationInfo("modeldesk_set_maneuver_behavior_profiles", True, "Maneuver behavior profiles updated and verified.", details)
            except Exception as exception:
                if mutation_started:
                    if phase == "Download":
                        save_status = "Save succeeded and remains complete" if save_completed else "no Save was requested"
                        message = f"Download failed after profile verification; {save_status}. No rollback was attempted: {exception}"
                    elif phase == "Save":
                        message = f"Save failed after profile verification; in-memory COM changes may be partial and were not rolled back: {exception}"
                    else:
                        message = f"{phase} failed; in-memory COM changes may be partial and were not rolled back: {exception}"
                    raise RuntimeError(message) from exception
                raise

        return self._execute_com("modeldesk_set_maneuver_behavior_profiles", operation)

    def get_scenario_road(self) -> ToolResult:
        """Return the road reference currently set on the active traffic scenario."""

        def operation(application: Any) -> OperationInfo:
            scenario = _get_active_traffic_scenario(application)
            has_road, road = com.try_get_property(scenario, "Road")
            if not has_road or road is None:
                return OperationInfo("modeldesk_get_scenario_road", True, "Traffic scenario has no road reference.", {})
            details = com.read_properties(road, "Name", "Path", "FileName", "CompleteName")
            return OperationInfo("modeldesk_get_scenario_road", True, "Traffic scenario road reference read.", details)

        return self._execute_com("modeldesk_get_scenario_road", operation)

    def set_scenario_road(self, road_name: str, save: bool, download: bool) -> ToolResult:
        """Set the road reference on the active traffic scenario via TrafficScenario.Road."""

        if road_name.strip() == "":
            return self._validation_failure("modeldesk_set_scenario_road", "Road name must not be empty.")

        def operation(application: Any) -> OperationInfo:
            scenario = _get_active_traffic_scenario(application)
            com.set_property(scenario, "Road", road_name)
            has_road, road = com.try_get_property(scenario, "Road")
            details: dict[str, str | None] = {"requestedRoad": road_name}
            if has_road and road is not None:
                details.update(com.read_properties(road, "Name", "Path", "FileName"))
            _apply_scenario_save_download(application, save, download, details)
            return OperationInfo("modeldesk_set_scenario_road", True, "Traffic scenario road reference set.", details)

        return self._execute_com("modeldesk_set_scenario_road", operation)

    def list_fellow_activities(self, fellow_selector: Selector, offset: int = 0) -> ToolResult:
        """List maneuvers/activities for a specific fellow or for the ego vehicle."""

        def operation(application: Any) -> DomainSummary:
            maneuvers = _get_scenario_maneuvers_collection(application, fellow_selector)
            label = "scenarios.egoActivities" if fellow_selector.by == SelectorKind.ACTIVE else f"scenarios.fellowActivities[{fellow_selector.by.value}={fellow_selector.value}]"
            return self._create_collection_summary(label, maneuvers, "activity", offset)

        return self._execute_com("modeldesk_list_fellow_activities", operation)

    def get_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int) -> ToolResult:
        """Return the active 3D object type path for a fellow or ego maneuver."""

        def operation(application: Any) -> OperationInfo:
            type_manager, domain = _get_vehicle_object_type_manager(application, fellow_selector, maneuver_index)
            has_active, active_element = com.try_get_property(type_manager, "ActiveElement")
            if not has_active or active_element is None:
                return OperationInfo("modeldesk_get_vehicle_object_type", True, f"No active object type for {domain}.", {"domain": domain})
            details = com.read_properties(active_element, "Name", "Path", "CompleteName", "TypeName")
            details["domain"] = domain
            return OperationInfo("modeldesk_get_vehicle_object_type", True, f"Active object type for {domain}.", details)

        return self._execute_com("modeldesk_get_vehicle_object_type", operation)

    def list_vehicle_object_types(self, fellow_selector: Selector, maneuver_index: int, offset: int = 0) -> ToolResult:
        """List all available 3D object types for a fellow or ego maneuver."""

        def operation(application: Any) -> DomainSummary:
            type_manager, domain = _get_vehicle_object_type_manager(application, fellow_selector, maneuver_index)
            elements = _available_type_elements(type_manager)
            return _summarize_type_elements(f"scenarios.objectTypes.{domain}", elements, "object type", self._options.max_collection_items, offset)

        return self._execute_com("modeldesk_list_vehicle_object_types", operation)

    def set_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int, element_index: int, save: bool, download: bool) -> ToolResult:
        """Activate a 3D object type by index for a fellow or ego maneuver."""

        if element_index < 0:
            return self._validation_failure("modeldesk_set_vehicle_object_type", "Element index must be a non-negative integer.")

        def operation(application: Any) -> OperationInfo:
            type_manager, domain = _get_vehicle_object_type_manager(application, fellow_selector, maneuver_index)
            elements = _available_type_elements(type_manager)
            if element_index >= len(elements):
                raise IndexError(f"Element index {element_index} is out of range (collection has {len(elements)} elements).")
            element = elements[element_index]
            com.invoke_method(type_manager, "Activate", element)
            has_active, active_element = com.try_get_property(type_manager, "ActiveElement")
            details: dict[str, str | None] = {"domain": domain, "requestedElementIndex": str(element_index)}
            if has_active and active_element is not None:
                details.update(com.read_properties(active_element, "Name", "Path", "CompleteName"))
            _apply_scenario_save_download(application, save, download, details)
            return OperationInfo("modeldesk_set_vehicle_object_type", True, f"Vehicle object type activated for {domain}.", details)

        return self._execute_com("modeldesk_set_vehicle_object_type", operation)

    def list_traffic_objects(self, offset: int = 0) -> ToolResult:
        """List reusable traffic objects from the active project."""

        return self._execute_com("modeldesk_list_traffic_objects", lambda application: self._create_first_available_collection_summary("trafficObjects.objects", _get_traffic_object_manager(application), "traffic object", "TrafficObjects", "Objects", offset=offset))

    def list_traffic_object_folders(self, offset: int = 0) -> ToolResult:
        """List traffic-object catalog folders."""

        return self._execute_com("modeldesk_list_traffic_object_folders", lambda application: self._create_collection_summary("trafficObjects.folders", _get_required_property(_get_traffic_object_manager(application), "Folders"), "traffic object folder", offset))

    def validate_traffic_object_reference(self, selector: Selector) -> ToolResult:
        """Validate a traffic-object catalog reference."""

        if selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_validate_traffic_object_reference", "Traffic object reference validation requires index, name, path, completeName, or id.")
        return self._execute_com("modeldesk_validate_traffic_object_reference", lambda application: self._validate_traffic_object_reference_core(application, selector))

    def get_processing_configuration(self) -> ToolResult:
        """Return processing configuration details."""

        def operation(application: Any) -> DomainSummary:
            processing = _get_active_parameter_set_processing(application)
            configuration = _get_required_property(processing, "Configuration")
            properties = com.read_properties(configuration, "Name", "TypeName", "Path")
            return self._create_object_summary("processing.configuration", configuration, properties, "Inputs", "Mappings", "MeasurementFiles", "Files", "Parameters")

        return self._execute_com("modeldesk_get_processing_configuration", operation)

    def activate_test(self, test_name: str) -> ToolResult:
        """Activate a ModelDesk test configuration by name."""

        if test_name.strip() == "":
            return self._validation_failure("modeldesk_activate_test", "Test name must not be empty.")
        return self._execute_com("modeldesk_activate_test", lambda application: self._activate_experiment_named_method(application, "ActivateTest", test_name, "modeldesk_activate_test", "Test activated."))

    def list_logical_test_cases(self, offset: int = 0) -> ToolResult:
        """List logical test cases."""

        return self._execute_com("modeldesk_list_logical_test_cases", lambda application: self._create_collection_summary("testing.logicalTestCases", _get_required_property(_get_active_test(application), "LogicalTestCases"), "logical test case", offset))

    def list_concrete_test_cases(self, logical_test_case_selector: Selector, offset: int = 0) -> ToolResult:
        """List concrete test cases for one logical test case of the active test configuration."""

        if logical_test_case_selector.by == SelectorKind.ACTIVE:
            return self._validation_failure("modeldesk_list_concrete_test_cases", "Logical test case selector must not use active.")

        def operation(application: Any) -> DomainSummary:
            # ConcreteTestCases is a property of each LogicalTestCase, not of the
            # active Test root object, so the logical test case must be resolved first.
            logical_test_cases = _get_required_property(_get_active_test(application), "LogicalTestCases")
            logical_test_case = com.resolve_item(logical_test_cases, logical_test_case_selector)
            concrete_test_cases = _get_required_property(logical_test_case, "ConcreteTestCases")
            summary = self._create_collection_summary("testing.concreteTestCases", concrete_test_cases, "concrete test case", offset)
            properties = dict(summary.properties)
            properties["logicalTestCaseSelectorKind"] = logical_test_case_selector.by.value
            properties["logicalTestCaseSelectorValue"] = logical_test_case_selector.value
            properties["logicalTestCaseName"] = com.get_string_property(logical_test_case, "Name")
            return DomainSummary(summary.domain, summary.available, summary.count, summary.items, properties, summary.message, summary.next_offset)

        return self._execute_com("modeldesk_list_concrete_test_cases", operation)

    def activate_plotting(self, selector: Selector) -> ToolResult:
        """Activate a plotting configuration by selector."""

        def operation(application: Any) -> OperationInfo:
            active_experiment = _get_active_experiment(application)
            com.invoke_method(active_experiment, "ActivatePlotting", selector.to_com_value())
            return OperationInfo("modeldesk_activate_plotting", True, "Plotting configuration activated.")

        return self._execute_com("modeldesk_activate_plotting", operation)

    def list_plot_captures(self, offset: int = 0) -> ToolResult:
        """List captures in the active plotting configuration."""

        return self._execute_com(
            "modeldesk_list_plot_captures",
            lambda application: self._create_first_available_collection_summary(
                "plotting.captures",
                _get_required_property(_get_active_plotting(application), "Captures"),
                "capture",
                "OpenCaptures",
                "AvailableElements",
                offset=offset,
            ),
        )

    def list_plot_layouts(self, offset: int = 0) -> ToolResult:
        """List plot layouts in the active plotting configuration."""

        return self._execute_com(
            "modeldesk_list_plot_layouts",
            lambda application: self._create_first_available_collection_summary(
                "plotting.layouts",
                _get_required_property(_get_active_plotting(application), "Layouts"),
                "plot layout",
                "ActiveLayouts",
                "AvailableElements",
                offset=offset,
            ),
        )

    def compare_captures(
        self,
        reference_capture: str,
        candidate_capture: str,
        signal_specs_json: str,
        tolerances_json: str,
    ) -> ToolResult:
        """Compare two MATLAB captures from the active project's measurement pool."""

        def operation(application: Any) -> dict[str, Any]:
            project = _get_active_project(application)
            working_root = com.get_string_property(project, "WorkingRoot")
            if working_root is None or working_root.strip() == "":
                raise ValueError("Application.ActiveProject.WorkingRoot is not available.")
            return self._compare_capture_files(
                working_root,
                reference_capture,
                candidate_capture,
                signal_specs_json,
                tolerances_json,
            )

        return self._execute_com("modeldesk_compare_captures", operation)

    def save_active_experiment(self) -> ToolResult:
        """Save the active experiment."""

        return self._execute_active_experiment_method("modeldesk_save_active_experiment", "Save")

    def download_active_experiment(self) -> ToolResult:
        """Download the active experiment."""

        return self._execute_active_experiment_method("modeldesk_download_active_experiment", "Download")

    def run_processing(self) -> ToolResult:
        """Execute parameter-set processing."""

        def operation(application: Any) -> OperationInfo:
            processing = _get_active_parameter_set_processing(application)
            com.invoke_method(processing, "Execute")
            return OperationInfo("modeldesk_run_processing", True, "Parameter-set processing executed.")

        return self._execute_com("modeldesk_run_processing", operation)

    def execute_test(self, scope: str, selector_kind: str | None, selector_value: str | None) -> ToolResult:
        """Execute the active test or a selected logical test case."""

        def operation(application: Any) -> OperationInfo:
            normalized_scope = "test" if scope.strip() == "" else scope.strip().lower()
            active_experiment = _get_active_experiment(application)
            target = _get_required_property(active_experiment, "Test")
            if normalized_scope == "logical":
                logical_cases = _get_required_property(target, "LogicalTestCases")
                selector = Selector.create(selector_kind, selector_value)
                target = com.resolve_item(logical_cases, selector)
            elif normalized_scope != "test":
                raise ValueError("Supported test execution scopes are 'test' and 'logical'.")
            verdict = com.invoke_method(target, "Execute")
            details = {"scope": normalized_scope, "verdict": None if verdict is None else str(verdict)}
            return OperationInfo("modeldesk_execute_test", True, "Test execution finished.", details)

        return self._execute_com("modeldesk_execute_test", operation)

    def start_maneuver(self, download_if_not_running: bool) -> ToolResult:
        """Start maneuver execution."""

        return self._execute_maneuver_control_method("modeldesk_start_maneuver", "Start", download_if_not_running)

    def stop_maneuver(self) -> ToolResult:
        """Stop maneuver execution."""

        return self._execute_maneuver_control_method("modeldesk_stop_maneuver", "Stop")

    def reset_maneuver(self) -> ToolResult:
        """Reset maneuver execution."""

        return self._execute_maneuver_control_method("modeldesk_reset_maneuver", "Reset")

    def synchronize_aurelion(self, system: str | None, scenario: str | None) -> ToolResult:
        """Synchronize the active ModelDesk scene to AURELION."""

        def operation(application: Any) -> OperationInfo:
            active_experiment = _get_active_experiment(application)
            result = com.invoke_method(active_experiment, "Synchronize", system or "", scenario or "")
            details = {"system": system, "scenario": scenario, "result": None if result is None else str(result)}
            return OperationInfo("modeldesk_synchronize_aurelion", True, "AURELION synchronization finished.", details)

        return self._execute_com("modeldesk_synchronize_aurelion", operation)

    def _execute_com(self, operation_name: str, operation: Callable[[Any], Any]) -> ToolResult:
        try:
            result = self._dispatcher.invoke(lambda: operation(self._get_or_create_application()), self._options.operation_timeout_seconds)
            return ToolResult.success(operation_name, self._session_id, result)
        except Exception as exception:  # noqa: BLE001 - converted to ToolResult at boundary.
            return self._create_failure(operation_name, exception)

    def _get_or_create_application(self) -> Any:
        if self._application is not None:
            return self._application
        if self._options.prog_id.strip() == "":
            raise RuntimeError("ModelDesk COM ProgId is not configured.")
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("pywin32 is required for ModelDesk COM automation. Install the project dependencies with Python 3.14.") from exc

        try:
            self._application = win32com.client.GetActiveObject(self._options.prog_id)
        except Exception:
            self._application = win32com.client.Dispatch(self._options.prog_id)
        if self._application is None:
            raise RuntimeError(f"Could not create ModelDesk COM application '{self._options.prog_id}'.")
        return self._application

    def _get_status_core(self, application: Any) -> ModelDeskStatus:
        version = com.get_string_property(application, "Version")
        has_project, project = com.try_get_property(application, "ActiveProject")
        project_name = com.get_first_string_property(project, "Name", "ProjectName", "WorkingRoot") if has_project and project is not None else None
        experiment_name = None
        if has_project and project is not None:
            has_experiment, active_experiment = com.try_get_property(project, "ActiveExperiment")
            if has_experiment and active_experiment is not None:
                experiment_name = com.get_first_string_property(active_experiment, "Name", "CompleteName")
        return ModelDeskStatus(self._session_id, True, version, bool(has_project and project is not None), project_name, experiment_name, self._options.prog_id, platform.machine())

    def _get_capabilities_core(self, application: Any) -> CapabilityReport:
        domains = {
            "project": True,
            "experiments": _has_active_project(application),
            "parameterization": _can_resolve_domain(application, ModelDeskDomain.PARAMETERIZATION),
            "parameterValueEditing": _can_resolve_domain(application, ModelDeskDomain.PARAMETERIZATION),
            "roads": _can_resolve_domain(application, ModelDeskDomain.ROADS),
            "scenarios": _can_resolve_domain(application, ModelDeskDomain.SCENARIOS),
            "scenarioInspection": _can_resolve_domain(application, ModelDeskDomain.SCENARIOS),
            "scenarioAuthoringMutation": _can_resolve_domain(application, ModelDeskDomain.SCENARIOS),
            "trafficObjects": _can_resolve_domain(application, ModelDeskDomain.TRAFFIC_OBJECTS),
            "trafficObjectInspection": _can_resolve_domain(application, ModelDeskDomain.TRAFFIC_OBJECTS),
            "trafficObjectCatalogMutation": False,
            "processing": _can_resolve_domain(application, ModelDeskDomain.PROCESSING),
            "processingConfiguration": _can_resolve_domain(application, ModelDeskDomain.PROCESSING),
            # Testing flags describe API support, so never resolve the lazy ActiveExperiment.Test getter here.
            "testing": True,
            "testCaseInspection": True,
            "plotting": _can_resolve_domain(application, ModelDeskDomain.PLOTTING),
            "plotArtifactInspection": _can_resolve_domain(application, ModelDeskDomain.PLOTTING),
            "comparison": True,
            "automationJobs": False,
            "workflow": True,
        }
        disabled = (
            "Traffic object catalog mutation (AddTrafficObject, RemoveTrafficObject, AddFolder, RemoveFolder) is COM-capable but not yet exposed as MCP tools.",
            "Persistent automation jobs are disabled until the job registry is implemented.",
        )
        python_version = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return CapabilityReport(__version__, None, platform.platform(), sys.platform.startswith("win"), self._options.prog_id, True, domains, disabled, python_version)

    def _get_project_info_core(self, application: Any) -> ProjectInfo:
        has_project, project = com.try_get_property(application, "ActiveProject")
        if not has_project or project is None:
            return ProjectInfo(False, None, None, None)
        active_experiment_name = None
        has_experiment, active_experiment = com.try_get_property(project, "ActiveExperiment")
        if has_experiment and active_experiment is not None:
            active_experiment_name = com.get_first_string_property(active_experiment, "Name", "CompleteName")
        return ProjectInfo(True, com.get_first_string_property(project, "Name", "ProjectName"), com.get_string_property(project, "WorkingRoot"), active_experiment_name)

    def _create_project_pool_file_core(self, application: Any, request: ProjectPoolFileCreationRequest) -> ProjectPoolFileCreationInfo:
        project = _get_active_project(application)
        pool = _get_required_property(project, "Pool")
        created_file = com.invoke_method(pool, "CreateFile", request.to_com_type(), request.name, request.overwrite_existing)
        if isinstance(created_file, bool) and not created_file:
            raise RuntimeError("Project pool CreateFile returned false.")
        created_name = None
        created_path = None
        created_type_name = None
        if created_file is not None and not isinstance(created_file, bool):
            created_name = com.get_first_string_property(created_file, "Name", "CompleteName", "FileName", "Path")
            created_path = com.get_first_string_property(created_file, "Path", "CompleteName", "FileName")
            created_type_name = com.get_first_string_property(created_file, "TypeName", "Kind", "ObjectType")
        message = f"Created project pool file '{request.name}{request.expected_extension()}' with CreateFile type {request.to_com_type()} ({request.file_type.display_name})."
        return ProjectPoolFileCreationInfo(request.file_type.display_name, request.to_com_type(), request.name, request.expected_extension(), request.overwrite_existing, created_name, created_path, created_type_name, message)

    def _list_environment_pool_items_core(self, application: Any, request: EnvironmentPoolGroupRequest, offset: int = 0) -> DomainSummary:
        project = _get_active_project(application)
        working_root = com.get_string_property(project, "WorkingRoot")
        if working_root is None or working_root.strip() == "":
            raise RuntimeError("Application.ActiveProject.WorkingRoot is not available.")
        environment_root = Path(working_root) / "Pool" / "Environment"
        group_path = environment_root / request.folder_name()
        max_items = max(1, self._options.max_collection_items)
        properties = {
            "workingRoot": working_root,
            "environmentRoot": str(environment_root),
            "group": request.folder_name(),
            "groupPath": str(group_path),
            "extension": request.file_extension(),
            "recursive": str(request.recursive),
            "maxItems": str(max_items),
            "offset": str(offset),
            "environmentRootExists": str(environment_root.exists()),
            "groupDirectoryExists": str(group_path.exists()),
        }
        if not group_path.exists():
            message = f"Environment Pool group directory '{group_path}' does not exist."
            return DomainSummary(request.domain_name(), False, 0, (), properties, message)
        file_paths, total_count, next_offset = _enumerate_environment_pool_files(group_path, request, max_items, offset)
        items = tuple(ItemSummary(index, _environment_pool_item_name(group_path, path), request.item_kind(), str(path)) for index, path in enumerate(file_paths, start=offset))
        properties["matchedItemCount"] = str(total_count)
        properties["pageItemCount"] = str(len(items))
        properties["truncated"] = str(next_offset is not None)
        message = f"More items available; request offset {next_offset}." if next_offset is not None else None
        return DomainSummary(request.domain_name(), True, total_count, items, properties, message, next_offset)

    def _invoke_project_method(self, application: Any, method_name: str, message: str) -> OperationInfo:
        project = _get_active_project(application)
        com.invoke_method(project, method_name)
        operation = "modeldesk_save_project" if method_name == "Save" else method_name
        return OperationInfo(operation, True, message)

    def _get_domain_summary_core(self, application: Any, domain: ModelDeskDomain) -> DomainSummary:
        if domain == ModelDeskDomain.EXPERIMENTS:
            return self._create_collection_summary("experiments", _get_required_property(_get_active_project(application), "Experiments"), "experiment")
        if domain == ModelDeskDomain.PARAMETERIZATION:
            active_parameter_set = _get_required_property(_get_active_experiment(application), "ActiveParameterSet")
            properties = com.read_properties(active_parameter_set, "Name")
            return self._create_object_summary("parameterization", active_parameter_set, properties, "MainComponents", "ParameterSetProcessing")
        if domain == ModelDeskDomain.ROADS:
            road = _get_required_property(_get_active_experiment(application), "Road")
            return self._create_object_summary("roads", road, com.read_properties(road, "Name", "FileName", "Path"), "Roads", "Segments", "Lanes", "RoadTrafficObjects")
        if domain == ModelDeskDomain.SCENARIOS:
            scenario = _get_required_property(_get_active_experiment(application), "TrafficScenario")
            return self._create_object_summary("scenarios", scenario, com.read_properties(scenario, "Name", "Author", "Comment"), "Fellows", "Maneuver", "Maneuvers")
        if domain == ModelDeskDomain.TRAFFIC_OBJECTS:
            manager = _get_required_property(_get_active_project(application), "TrafficObjectManager")
            return self._create_object_summary("trafficObjects", manager, com.read_properties(manager, "Name"), "TrafficObjects", "Objects", "Folders")
        if domain == ModelDeskDomain.PROCESSING:
            processing = _get_active_parameter_set_processing(application)
            return self._create_object_summary("processing", processing, com.read_properties(processing, "Name"), "Configuration")
        if domain == ModelDeskDomain.TESTING:
            test = _get_required_property(_get_active_experiment(application), "Test")
            return self._create_object_summary("testing", test, com.read_properties(test, "Name", "Verdict"), "LogicalTestCases", "ConcreteTestCases")
        if domain == ModelDeskDomain.PLOTTING:
            return self._create_plotting_summary(application)
        raise ValueError(f"Domain '{domain.value}' is not a COM-backed summary domain.")

    def _create_plotting_summary(self, application: Any) -> DomainSummary:
        plotting = _get_active_plotting(application)
        properties = com.read_properties(plotting, "Name")
        nested_collections = (
            ("captures.open", _get_required_property(plotting, "Captures"), "OpenCaptures"),
            ("layouts.active", _get_required_property(plotting, "Layouts"), "ActiveLayouts"),
            ("signals.simulation", plotting, "SimulationSignals"),
        )
        for label, instance, property_name in nested_collections:
            has_collection, collection = com.try_get_property(instance, property_name)
            if not has_collection or collection is None:
                properties[f"collection.{label}.available"] = "False"
                continue
            try:
                properties[f"collection.{label}.count"] = str(com.snapshot_collection(collection, label, self._options.max_collection_items).count)
            except Exception as exception:  # noqa: BLE001 - records late-bound collection failures.
                properties[f"collection.{label}.error"] = public_error_message(exception)
        item = ItemSummary(0, com.read_display_name(plotting, "plotting", 0), com.get_string_property(plotting, "TypeName"), com.get_string_property(plotting, "Path"))
        return DomainSummary("plotting", True, 1, (item,), properties)

    def _get_parameter_value_core(self, application: Any, parameter_path: str) -> ParameterValueInfo:
        parameter = self._find_parameter(application, parameter_path)
        return self._read_parameter_value(parameter, parameter_path)

    def _find_parameter(self, application: Any, parameter_path: str) -> Any:
        active_parameter_set = _get_required_property(_get_active_experiment(application), "ActiveParameterSet")
        try:
            parameter = com.invoke_method(active_parameter_set, "Find", parameter_path)
        except Exception as first_exception:
            # One bounded retry: refresh active model metadata and retry Find once.
            _try_refresh_active_model(application)
            try:
                parameter = com.invoke_method(active_parameter_set, "Find", parameter_path)
            except Exception as second_exception:
                raise RuntimeError(
                    f"Parameter lookup failed for '{parameter_path}' after one model-refresh retry. "
                    f"First error: {first_exception}; retry error: {second_exception}"
                ) from second_exception
        if parameter is None:
            _try_refresh_active_model(application)
            parameter = com.invoke_method(active_parameter_set, "Find", parameter_path)
            if parameter is None:
                raise RuntimeError(f"Parameter '{parameter_path}' was not found.")
        return parameter

    def _read_parameter_value(self, parameter: Any, parameter_path: str) -> ParameterValueInfo:
        text_value = None
        numeric_value = None
        has_value, raw_value = com.try_get_property(parameter, "V")
        if has_value and raw_value is not None:
            text_value = str(raw_value)
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError, OverflowError):
                numeric_value = None
        return ParameterValueInfo(parameter_path, com.get_string_property(parameter, "Name"), com.get_string_property(parameter, "TypeName"), com.get_string_property(parameter, "Unit"), text_value, numeric_value)

    def _add_road_core(self, application: Any, name: str | None, left_lane_count: int, right_lane_count: int, lane_width: float, save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        roads = _get_required_property(road_network, "Roads")
        road = _invoke_required_method(roads, "Add")
        normalized_name = _normalize_optional_text(name)
        if normalized_name is not None:
            com.set_property(road, "Name", normalized_name)
        _configure_road_lane_section(road, 0, left_lane_count, right_lane_count, lane_width, 0.0)
        details = _create_road_details(road, roads)
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_add_road", True, "Road added to the active road network.", details)

    def _update_road_core(self, application: Any, selector: Selector, name: str, save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        roads = _get_required_property(road_network, "Roads")
        road = _resolve_road(road_network, selector)
        com.set_property(road, "Name", name)
        details = _create_road_details(road, roads)
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_update_road", True, "Road updated.", details)

    def _remove_road_core(self, application: Any, selector: Selector, save: bool, download: bool, dry_run: bool = False) -> OperationInfo:
        road_network = _get_active_road_network(application)
        roads = _get_required_property(road_network, "Roads")
        road = _resolve_road(road_network, selector)
        road_name = _read_road_name(road)
        if dry_run:
            details = {"roadName": road_name, "wouldRemainRoadCount": str(max(0, com.get_count(roads) - 1))}
            return _dry_run_preview("modeldesk_remove_road", details, save, download)
        result = com.invoke_method(roads, "Remove", road)
        if isinstance(result, bool) and not result:
            raise RuntimeError("Road removal returned false.")
        details = {"roadName": road_name, "roadCount": str(com.get_count(roads))}
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_remove_road", True, "Road removed from the active road network.", details)

    def _add_road_segment_core(self, application: Any, selector: Selector, request: RoadSegmentEditRequest) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        segments = _get_required_property(road, "Segments")
        assert request.segment_type is not None
        active_segment = _invoke_required_method(segments, "InsertAfter", request.insert_after_segment_index, request.segment_type.display_name) if request.insert_after_segment_index >= 0 else _invoke_required_method(segments, "Add", request.segment_type.display_name)
        typed_segment = _activate_segment(active_segment, request.segment_type)
        _apply_segment_properties(typed_segment, request.segment_type, request.properties)
        details = _create_segment_details(road, segments, typed_segment)
        _apply_road_network_save_download(road_network, request.save, request.download, details)
        return OperationInfo("modeldesk_add_road_segment", True, "Road segment added.", details)

    def _update_road_segment_core(self, application: Any, selector: Selector, segment_index: int, request: RoadSegmentEditRequest) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        segments = _get_required_property(road, "Segments")
        active_segment = _invoke_required_item(segments, segment_index, "segment")
        typed_segment = _activate_segment(active_segment, request.segment_type) if request.segment_type is not None else _get_active_segment_element(active_segment)
        segment_type = request.segment_type or _read_segment_type(typed_segment)
        _apply_segment_properties(typed_segment, segment_type, request.properties)
        details = _create_segment_details(road, segments, typed_segment)
        _apply_road_network_save_download(road_network, request.save, request.download, details)
        return OperationInfo("modeldesk_update_road_segment", True, "Road segment updated.", details)

    def _remove_road_segment_core(self, application: Any, selector: Selector, segment_index: int, save: bool, download: bool, dry_run: bool = False) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        segments = _get_required_property(road, "Segments")
        active_segment = _invoke_required_item(segments, segment_index, "segment")
        typed_segment = _get_active_segment_element(active_segment)
        segment_name = com.get_string_property(typed_segment, "Name") or f"Segment {segment_index}"
        if dry_run:
            details = {
                "roadName": _read_road_name(road),
                "segmentName": segment_name,
                "segmentIndex": str(segment_index),
                "wouldRemainSegmentCount": str(max(0, com.get_count(segments) - 1)),
            }
            return _dry_run_preview("modeldesk_remove_road_segment", details, save, download)
        result = com.invoke_method(segments, "Remove", segment_index)
        if isinstance(result, bool) and not result:
            raise RuntimeError("Segment removal returned false.")
        details = {"roadName": _read_road_name(road), "segmentName": segment_name, "segmentIndex": str(segment_index), "segmentCount": str(com.get_count(segments))}
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_remove_road_segment", True, "Road segment removed.", details)

    def _configure_road_lanes_core(self, application: Any, selector: Selector, lane_section_index: int, left_lane_count: int, right_lane_count: int, lane_width: float, lane_section_length: float, save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        lane_section = _configure_road_lane_section(road, lane_section_index, left_lane_count, right_lane_count, lane_width, lane_section_length)
        details = _create_lane_section_details(road, lane_section, lane_section_index)
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_configure_road_lanes", True, "Road lanes configured.", details)

    def _add_road_object_core(self, application: Any, selector: Selector, s: float, d: float, name: str | None, catalog_path: str | None, lane_mapping: tuple[int, ...], save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        road_length = _read_double_property(road, "Length")
        _validate_road_object_position(s, d, road_length)
        road_objects = _get_required_property(road, "Objects")
        road_object = _invoke_required_method(road_objects, "Add", s, d)
        _apply_road_object_base_properties(road_object, name, catalog_path, lane_mapping)
        details = _create_road_object_details(road, road_objects, road_object)
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_add_road_object", True, "Road traffic object added.", details)

    def _update_road_object_core(self, application: Any, selector: Selector, object_index: int, properties: RoadObjectProperties, save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        road_length = _read_double_property(road, "Length")
        road_objects = _get_required_property(road, "Objects")
        road_object = _invoke_required_item(road_objects, object_index, "road object")
        _apply_road_object_properties(road_object, properties, road_length)
        details = _create_road_object_details(road, road_objects, road_object)
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_update_road_object", True, "Road traffic object updated.", details)

    def _remove_road_object_core(self, application: Any, selector: Selector, object_index: int, save: bool, download: bool, dry_run: bool = False) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        road_objects = _get_required_property(road, "Objects")
        road_object = _invoke_required_item(road_objects, object_index, "road object")
        object_name = com.get_string_property(road_object, "Name") or f"Road object {object_index}"
        if dry_run:
            details = {
                "roadName": _read_road_name(road),
                "objectName": object_name,
                "objectIndex": str(object_index),
                "wouldRemainObjectCount": str(max(0, com.get_count(road_objects) - 1)),
            }
            return _dry_run_preview("modeldesk_remove_road_object", details, save, download)
        result = com.invoke_method(road_objects, "Remove", road_object)
        if isinstance(result, bool) and not result:
            raise RuntimeError("Road object removal returned false.")
        details = {"roadName": _read_road_name(road), "objectName": object_name, "objectIndex": str(object_index), "objectCount": str(com.get_count(road_objects))}
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_remove_road_object", True, "Road traffic object removed.", details)

    def _connect_roads_core(self, application: Any, source_selector: Selector, source_point: RoadConnectionPointKind, target_selector: Selector, target_point: RoadConnectionPointKind, mode: RoadConnectionMode, save: bool, download: bool) -> OperationInfo:
        road_network = _get_active_road_network(application)
        source_road = _resolve_road(road_network, source_selector)
        target_road = _resolve_road(road_network, target_selector)
        source_connection_point = _resolve_road_connection_point(source_road, source_point)
        target_connection_point = _resolve_road_connection_point(target_road, target_point)
        method_name = "ModifyAndConnect" if mode == RoadConnectionMode.MODIFY else "MoveAndConnect"
        result = com.invoke_method(source_connection_point, method_name, target_connection_point)
        if isinstance(result, bool) and not result:
            raise RuntimeError(f"Road connection method '{method_name}' returned false.")
        details = {"sourceRoad": _read_road_name(source_road), "sourcePoint": source_point.display_name, "targetRoad": _read_road_name(target_road), "targetPoint": target_point.display_name, "mode": mode.value}
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_connect_roads", True, "Road connection created.", details)

    def _disconnect_road_core(self, application: Any, selector: Selector, connection_point: RoadConnectionPointKind, save: bool, download: bool, dry_run: bool = False) -> OperationInfo:
        road_network = _get_active_road_network(application)
        road = _resolve_road(road_network, selector)
        road_connection_point = _resolve_road_connection_point(road, connection_point)
        details = {"roadName": _read_road_name(road), "connectionPoint": connection_point.display_name}
        if dry_run:
            return _dry_run_preview("modeldesk_disconnect_road", details, save, download)
        com.invoke_method(road_connection_point, "Disconnect")
        _apply_road_network_save_download(road_network, save, download, details)
        return OperationInfo("modeldesk_disconnect_road", True, "Road connection point disconnected.", details)

    def _create_basic_road_core(self, application: Any, request: BasicRoadCreationRequest) -> BasicRoadCreationInfo:
        road_network = _get_active_road_network(application)
        roads = _get_required_property(road_network, "Roads")
        road = _invoke_required_method(roads, "Add")
        com.set_property(road, "Name", request.name)
        segments = _get_required_property(road, "Segments")
        straight_segment = _get_or_create_first_typed_segment(segments, RoadSegmentType.STRAIGHT)
        com.set_property(straight_segment, "Length", request.length)
        lane_sections = _get_required_property(road, "LaneSections")
        lane_section = _get_or_create_first_collection_item(lane_sections, "lane section")
        com.set_property(lane_section, "Length", request.length)
        lanes = _get_required_property(lane_section, "Lanes")
        _configure_lanes(lanes, request.left_lane_count, request.right_lane_count, request.lane_width)
        road_objects = _get_required_property(road, "Objects")
        created_objects = _create_traffic_objects(road_objects, request)
        saved = False
        downloaded = False
        if request.save:
            _invoke_boolean_aware_method(road_network, "Save")
            saved = True
        if request.download:
            _invoke_boolean_aware_method(road_network, "Download")
            downloaded = True
        message = f"Created straight road '{request.name}' in the active road network."
        return BasicRoadCreationInfo(request.name, request.length, request.left_lane_count, request.right_lane_count, request.lane_width, com.get_count(segments), com.get_count(lane_sections), com.get_count(road_objects), saved, downloaded, created_objects, message)

    def _validate_traffic_object_reference_core(self, application: Any, selector: Selector) -> OperationInfo:
        manager = _get_traffic_object_manager(application)
        traffic_objects = _get_first_available_property(manager, "TrafficObjects", "Objects")
        traffic_object = com.resolve_item(traffic_objects, selector)
        details = com.read_properties(traffic_object, "Name", "Path", "CompleteName", "TypeName", "ObjectID")
        details["selectorKind"] = selector.by.value
        details["selectorValue"] = selector.value
        return OperationInfo("modeldesk_validate_traffic_object_reference", True, "Traffic object reference resolved.", details)

    def _add_scenario_fellow_core(self, application: Any, fellow_selector: Selector, name: str | None, properties_json: str | None, traffic_object_selector: Selector | None, traffic_object_catalog_path: str | None, traffic_driver_reference: str | None, save: bool, download: bool) -> OperationInfo:
        fellows = _get_scenario_fellows_collection(application)
        add_mode = fellow_selector.by == SelectorKind.ACTIVE
        fellow = _invoke_required_method(fellows, "Add") if add_mode else _resolve_fellow(fellows, fellow_selector)
        normalized_name = _normalize_optional_text(name)
        if normalized_name is not None:
            com.set_property(fellow, "Name", normalized_name)
        updated_count = _apply_scalar_properties_from_json(fellow, properties_json, "propertiesJson")
        _apply_traffic_object_reference(application, fellow, traffic_object_selector, traffic_object_catalog_path)
        _apply_traffic_driver_reference(fellow, traffic_driver_reference)
        details = com.read_properties(fellow, "Name", "Path", "TypeName", "ObjectID")
        details["mode"] = "add" if add_mode else "update"
        details["updatedPropertyCount"] = str(updated_count)
        if not add_mode:
            details["fellowSelectorKind"] = fellow_selector.by.value
            details["fellowSelectorValue"] = fellow_selector.value
        if traffic_object_selector is not None:
            details["trafficObjectSelectorKind"] = traffic_object_selector.by.value
            details["trafficObjectSelectorValue"] = traffic_object_selector.value
        if traffic_object_catalog_path is not None and traffic_object_catalog_path.strip() != "":
            details["trafficObjectCatalogPath"] = traffic_object_catalog_path
        if traffic_driver_reference is not None and traffic_driver_reference.strip() != "":
            details["trafficDriverReference"] = traffic_driver_reference
        _apply_scenario_save_download(application, save, download, details)
        operation = "modeldesk_add_scenario_fellow" if add_mode else "modeldesk_update_scenario_fellow"
        message = "Scenario fellow added." if add_mode else "Scenario fellow updated."
        return OperationInfo(operation, True, message, details)

    def _add_or_update_scenario_maneuver_core(self, application: Any, fellow_selector: Selector, maneuver_selector: Selector, properties_json: str | None, save: bool, download: bool, operation_name: str, add_mode: bool) -> OperationInfo:
        maneuvers = _get_scenario_maneuvers_collection(application, fellow_selector)
        maneuver = _invoke_required_method(maneuvers, "Add") if add_mode else com.resolve_item(maneuvers, maneuver_selector)
        updated_count = _apply_scalar_properties_from_json(maneuver, properties_json, "propertiesJson")
        details = com.read_properties(maneuver, "Name", "TypeName", "Path", "ObjectID")
        details["fellowSelectorKind"] = fellow_selector.by.value
        details["fellowSelectorValue"] = fellow_selector.value
        if not add_mode:
            details["maneuverSelectorKind"] = maneuver_selector.by.value
            details["maneuverSelectorValue"] = maneuver_selector.value
        details["updatedPropertyCount"] = str(updated_count)
        _apply_scenario_save_download(application, save, download, details)
        message = "Scenario maneuver added." if add_mode else "Scenario maneuver updated."
        return OperationInfo(operation_name, True, message, details)

    def _activate_experiment_named_method(self, application: Any, method_name: str, name: str, operation_name: str, message: str) -> OperationInfo:
        active_experiment = _get_active_experiment(application)
        com.invoke_method(active_experiment, method_name, name)
        return OperationInfo(operation_name, True, message)

    def _execute_active_experiment_method(self, operation_name: str, method_name: str) -> ToolResult:
        def operation(application: Any) -> OperationInfo:
            active_experiment = _get_active_experiment(application)
            com.invoke_method(active_experiment, method_name)
            return OperationInfo(operation_name, True, f"Active experiment method '{method_name}' completed.")

        return self._execute_com(operation_name, operation)

    def _execute_maneuver_control_method(self, operation_name: str, method_name: str, *arguments: Any) -> ToolResult:
        def operation(application: Any) -> OperationInfo:
            active_experiment = _get_active_experiment(application)
            maneuver_control = _get_required_property(active_experiment, "ManeuverControl")
            result = com.invoke_method(maneuver_control, method_name, *arguments)
            details = {"result": None if result is None else str(result)}
            return OperationInfo(operation_name, True, f"Maneuver control method '{method_name}' completed.", details)

        return self._execute_com(operation_name, operation)

    def _create_collection_summary(self, domain: str, collection: Any, item_kind: str, offset: int = 0) -> DomainSummary:
        snapshot = com.snapshot_collection(collection, item_kind, self._options.max_collection_items, offset)
        properties = com.read_properties(collection, "Name", "TypeName")
        message = f"Result was truncated to {self._options.max_collection_items} items." if snapshot.is_truncated else None
        return DomainSummary(domain, True, snapshot.count, snapshot.items, properties, message, snapshot.next_offset)

    def _create_first_available_collection_summary(self, domain: str, instance: Any, item_kind: str, *property_candidates: str, offset: int = 0) -> DomainSummary:
        properties: dict[str, str | None] = {}
        for property_name in property_candidates:
            has_collection, collection = com.try_get_property(instance, property_name)
            if not has_collection or collection is None:
                properties[f"collection.{property_name}.available"] = "False"
                continue
            try:
                summary = self._create_collection_summary(domain, collection, item_kind, offset)
                merged = dict(summary.properties)
                merged["collection.selected"] = property_name
                return DomainSummary(summary.domain, summary.available, summary.count, summary.items, merged, summary.message, summary.next_offset)
            except Exception as exception:  # noqa: BLE001 - records per-candidate late-bound failures.
                properties[f"collection.{property_name}.error"] = public_error_message(exception)
        message = f"None of the expected COM collection properties could be summarized: {', '.join(property_candidates)}."
        return DomainSummary(domain, False, 0, (), properties, message)

    def _create_object_summary(self, domain: str, instance: Any, properties: dict[str, str | None], *collection_property_candidates: str) -> DomainSummary:
        for property_name in collection_property_candidates:
            has_collection, collection = com.try_get_property(instance, property_name)
            if has_collection and collection is not None:
                try:
                    snapshot = com.snapshot_collection(collection, property_name, self._options.max_collection_items)
                    updated_properties = dict(properties)
                    updated_properties[f"collection.{property_name}.count"] = str(snapshot.count)
                    message = f"Result was truncated to {self._options.max_collection_items} items." if snapshot.is_truncated else None
                    return DomainSummary(domain, True, snapshot.count, snapshot.items, updated_properties, message)
                except Exception as exception:  # noqa: BLE001 - records late-bound collection failures.
                    properties[f"collection.{property_name}.error"] = public_error_message(exception)
        display_name = com.read_display_name(instance, domain, 0)
        item = ItemSummary(0, display_name, com.get_string_property(instance, "TypeName"), com.get_string_property(instance, "Path"))
        return DomainSummary(domain, True, 1, (item,), properties)

    def _create_failure(self, operation_name: str, exception: Exception) -> ToolResult:
        error_type = _classify_error(exception)
        retryable = error_type in ("timeout", "com_error")
        error = ToolError(error_type, public_error_message(exception), operation_name, "Check ModelDesk state, active project, active experiment, and COM registration.", retryable)
        return ToolResult.failure(operation_name, self._session_id, error)

    def _validation_failure(self, operation_name: str, message: str) -> ToolResult:
        error = ToolError("validation", public_error_message(message), operation_name, "Correct the tool input and call the tool again.")
        return ToolResult.failure(operation_name, self._session_id, error)


def _get_active_project(application: Any) -> Any:
    project = com.get_property(application, "ActiveProject")
    if project is None:
        raise RuntimeError("No active ModelDesk project is available.")
    return project


def _get_active_experiment(application: Any) -> Any:
    project = _get_active_project(application)
    active_experiment = com.get_property(project, "ActiveExperiment")
    if active_experiment is None:
        raise RuntimeError("No active ModelDesk experiment is available.")
    return active_experiment


def _read_model_info_properties(model_info: Any) -> dict[str, str | None]:
    """Map verified COM model-info names to stable public response keys.

    The automation interface exposes ``Path`` and ``MATLABWorkingDirectory``;
    callers continue to receive ``ModelFilePath`` and ``MLWorkingDirectory``.
    COM read failures propagate to the gateway's structured error boundary.
    """

    source_properties = com.read_properties(
        model_info,
        "ModelName",
        "Path",
        "ModelType",
        "PlatformName",
        "Validity",
        "MATLABWorkingDirectory",
    )
    return {
        "ModelName": source_properties.get("ModelName"),
        "ModelFilePath": source_properties.get("Path"),
        "ModelType": source_properties.get("ModelType"),
        "PlatformName": source_properties.get("PlatformName"),
        "Validity": source_properties.get("Validity"),
        "MLWorkingDirectory": source_properties.get("MATLABWorkingDirectory"),
    }


def _get_required_property(instance: Any, property_name: str) -> Any:
    value = com.get_property(instance, property_name)
    if value is None:
        raise RuntimeError(f"Required COM property '{property_name}' is not available.")
    return value


def _has_active_project(application: Any) -> bool:
    has_project, project = com.try_get_property(application, "ActiveProject")
    return has_project and project is not None


def _can_resolve_domain(application: Any, domain: ModelDeskDomain) -> bool:
    try:
        if domain == ModelDeskDomain.PARAMETERIZATION:
            active_experiment = _get_active_experiment(application)
            has_value, value = com.try_get_property(active_experiment, "ActiveParameterSet")
            return has_value and value is not None
        if domain == ModelDeskDomain.ROADS:
            active_experiment = _get_active_experiment(application)
            has_value, value = com.try_get_property(active_experiment, "Road")
            return has_value and value is not None
        if domain == ModelDeskDomain.SCENARIOS:
            active_experiment = _get_active_experiment(application)
            has_value, value = com.try_get_property(active_experiment, "TrafficScenario")
            return has_value and value is not None
        if domain == ModelDeskDomain.TRAFFIC_OBJECTS:
            project = _get_active_project(application)
            has_value, value = com.try_get_property(project, "TrafficObjectManager")
            return has_value and value is not None
        if domain == ModelDeskDomain.PROCESSING:
            processing = _get_active_parameter_set_processing(application)
            return processing is not None
        if domain == ModelDeskDomain.TESTING:
            test = _get_active_test(application)
            return test is not None
        if domain == ModelDeskDomain.PLOTTING:
            plotting = _get_active_plotting(application)
            return plotting is not None
        return False
    except Exception:
        return False


def _get_active_road_network(application: Any) -> Any:
    return _get_required_property(_get_active_experiment(application), "Road")


def _get_active_traffic_scenario(application: Any) -> Any:
    return _get_required_property(_get_active_experiment(application), "TrafficScenario")


def _get_active_parameter_set_processing(application: Any) -> Any:
    active_parameter_set = _get_required_property(_get_active_experiment(application), "ActiveParameterSet")
    return _get_required_property(active_parameter_set, "ParameterSetProcessing")


def _get_traffic_object_manager(application: Any) -> Any:
    return _get_required_property(_get_active_project(application), "TrafficObjectManager")


def _get_active_test(application: Any) -> Any:
    return _get_required_property(_get_active_experiment(application), "Test")


def _get_active_plotting(application: Any) -> Any:
    return _get_required_property(_get_active_experiment(application), "Plotting")


def _try_refresh_active_model(application: Any) -> None:
    """Best-effort refresh of active model metadata before parameter lookup retry."""

    try:
        active_experiment = _get_active_experiment(application)
        has_models, models = com.try_get_property(active_experiment, "Models")
        if not has_models or models is None:
            return
        com.invoke_method(models, "UpdateActiveModel")
    except Exception:
        # Retry path must remain bounded and non-fatal.
        return


def _get_first_available_property(instance: Any, *property_candidates: str) -> Any:
    for property_name in property_candidates:
        has_value, value = com.try_get_property(instance, property_name)
        if has_value and value is not None:
            return value
    raise RuntimeError(f"None of the expected COM properties is available: {', '.join(property_candidates)}.")


def _resolve_road(road_network: Any, selector: Selector) -> Any:
    roads = _get_required_property(road_network, "Roads")
    if selector.by == SelectorKind.ACTIVE:
        return _invoke_required_item(roads, 0, "road")
    return com.resolve_item(roads, selector)


def _normalize_road_network_file_name(file_name: str, overwrite_existing: bool) -> str:
    if file_name.strip() == "":
        raise ValueError("Road network file name must not be empty.")
    full_path = Path(file_name).expanduser().resolve()
    if not full_path.is_absolute():
        raise ValueError("Road network file name must be an absolute path.")
    if full_path.suffix.lower() != ".rd":
        raise ValueError("Road network file name must end with .rd.")
    if not full_path.parent.exists():
        raise FileNotFoundError(f"Directory '{full_path.parent}' does not exist.")
    if full_path.exists() and not overwrite_existing:
        raise FileExistsError(f"Road network file '{full_path}' already exists. Set overwriteExisting=true to replace it.")
    return str(full_path)


def _configure_road_lane_section(road: Any, lane_section_index: int, left_lane_count: int, right_lane_count: int, lane_width: float, lane_section_length: float) -> Any:
    lane_sections = _get_required_property(road, "LaneSections")
    lane_section = _get_or_create_collection_item(lane_sections, lane_section_index, "lane section")
    effective_length = lane_section_length if lane_section_length > 0.0 else _read_double_property(road, "Length")
    if effective_length > 0.0:
        com.set_property(lane_section, "Length", effective_length)
    lanes = _get_required_property(lane_section, "Lanes")
    _configure_lanes(lanes, left_lane_count, right_lane_count, lane_width)
    return lane_section


def _get_or_create_collection_item(collection: Any, index: int, item_kind: str) -> Any:
    count = com.get_count(collection)
    if index < count:
        return _invoke_required_item(collection, index, item_kind)
    if index == count:
        return _invoke_required_method(collection, "Add")
    raise IndexError(f"Cannot create {item_kind} at index {index}; next valid index is {count}.")


def _get_or_create_first_typed_segment(segments: Any, segment_type: RoadSegmentType) -> Any:
    active_segment = _invoke_required_item(segments, 0, "segment") if com.get_count(segments) > 0 else _invoke_required_method(segments, "Add", segment_type.display_name)
    return _activate_segment(active_segment, segment_type)


def _activate_segment(active_segment: Any, segment_type: RoadSegmentType) -> Any:
    return _invoke_required_method(active_segment, "Activate", segment_type.display_name)


def _get_active_segment_element(active_segment: Any) -> Any:
    active_element = com.get_property(active_segment, "ActiveElement")
    if active_element is None:
        raise RuntimeError("Active segment did not expose an active element.")
    return active_element


def _read_segment_type(typed_segment: Any) -> RoadSegmentType:
    type_value = _read_int_property(typed_segment, "Type")
    try:
        return RoadSegmentType(type_value)
    except ValueError as exc:
        raise RuntimeError(f"Unsupported road segment type value '{type_value}'.") from exc


def _apply_segment_properties(typed_segment: Any, segment_type: RoadSegmentType, properties: RoadSegmentProperties) -> None:
    _validate_segment_properties_for_type(segment_type, properties)
    name = _normalize_optional_text(properties.name)
    if name is not None:
        com.set_property(typed_segment, "Name", name)
    if segment_type == RoadSegmentType.STRAIGHT:
        _set_optional_property(typed_segment, "Length", properties.length)
    elif segment_type == RoadSegmentType.CIRCULAR:
        _set_optional_property(typed_segment, "Length", properties.length)
        _set_optional_property(typed_segment, "Radius", properties.radius)
        _set_optional_property(typed_segment, "Angle", properties.angle)
    elif segment_type == RoadSegmentType.CLOTHOID:
        _set_optional_property(typed_segment, "Length", properties.length)
        _set_optional_property(typed_segment, "Radius", properties.radius)
        if properties.is_infinite is not None:
            com.set_property(typed_segment, "IsInfinite", properties.is_infinite)
    elif segment_type == RoadSegmentType.SPLINE:
        _apply_spline_properties(typed_segment, properties)
    else:
        raise ValueError("Unsupported segment type.")


def _validate_segment_properties_for_type(segment_type: RoadSegmentType, properties: RoadSegmentProperties) -> None:
    if segment_type != RoadSegmentType.CIRCULAR and properties.angle is not None:
        raise ValueError("Angle can only be set for Circular segments.")
    if segment_type not in (RoadSegmentType.CIRCULAR, RoadSegmentType.CLOTHOID) and properties.radius is not None:
        raise ValueError("Radius can only be set for Circular or Clothoid segments.")
    if segment_type != RoadSegmentType.CLOTHOID and properties.is_infinite is not None:
        raise ValueError("IsInfinite can only be set for Clothoid segments.")
    has_spline_property = any(item is not None for item in (properties.spline_definition_type, properties.relative_end_vector, properties.absolute_end_vector, properties.spline_parameter_x, properties.spline_parameter_y))
    if segment_type != RoadSegmentType.SPLINE and has_spline_property:
        raise ValueError("Spline properties can only be set for Spline segments.")
    if segment_type == RoadSegmentType.SPLINE and properties.length is not None:
        raise ValueError("Spline length is calculated by ModelDesk and cannot be set directly through Automation.")


def _apply_spline_properties(typed_segment: Any, properties: RoadSegmentProperties) -> None:
    definition_type_text = _normalize_optional_text(properties.spline_definition_type)
    if definition_type_text is not None:
        definition_type = 1 if definition_type_text.lower() == "parameterbased" else 0
        com.set_property(typed_segment, "DefintionType", definition_type)
    if properties.relative_end_vector is not None:
        _apply_vector_properties(_get_required_property(typed_segment, "RelativeEndVector"), properties.relative_end_vector)
    if properties.absolute_end_vector is not None:
        _apply_vector_properties(_get_required_property(typed_segment, "AbsoluteEndVector"), properties.absolute_end_vector)
    if properties.spline_parameter_x is not None or properties.spline_parameter_y is not None:
        spline_parameters = _get_required_property(typed_segment, "Parameters")
        if properties.spline_parameter_x is not None:
            _apply_spline_parameter_properties(_get_required_property(spline_parameters, "X"), properties.spline_parameter_x)
        if properties.spline_parameter_y is not None:
            _apply_spline_parameter_properties(_get_required_property(spline_parameters, "Y"), properties.spline_parameter_y)


def _apply_vector_properties(vector: Any, properties: RoadVectorSpec) -> None:
    _set_optional_property(vector, "X", properties.x)
    _set_optional_property(vector, "Y", properties.y)
    _set_optional_property(vector, "Tangent", properties.tangent)


def _apply_spline_parameter_properties(parameter: Any, properties: RoadSplineParameterSpec) -> None:
    _set_optional_property(parameter, "B", properties.b)
    _set_optional_property(parameter, "C", properties.c)
    _set_optional_property(parameter, "D", properties.d)


def _apply_road_object_base_properties(road_object: Any, name: str | None, catalog_path: str | None, lane_mapping: tuple[int, ...]) -> None:
    normalized_name = _normalize_optional_text(name)
    if normalized_name is not None:
        com.set_property(road_object, "Name", normalized_name)
    normalized_catalog_path = _normalize_optional_text(catalog_path)
    if normalized_catalog_path is not None:
        traffic_object_type = _get_required_property(road_object, "TrafficObjectType")
        _invoke_required_method(traffic_object_type, "Activate", normalized_catalog_path)
    if len(lane_mapping) > 0:
        com.set_property(road_object, "LaneMapping", list(lane_mapping))
        com.set_property(road_object, "LaneMappingEnabled", True)


def _apply_road_object_properties(road_object: Any, properties: RoadObjectProperties, road_length: float) -> None:
    position = None
    if properties.s is not None or properties.d is not None:
        position = _get_required_property(road_object, "Position")
        s = properties.s if properties.s is not None else _read_double_property(position, "S")
        d = properties.d if properties.d is not None else _read_double_property(position, "D")
        _validate_road_object_position(s, d, road_length)

    # Validate the complete road-relative position before writing any other field.
    _apply_road_object_base_properties(road_object, properties.name, properties.catalog_path, properties.lane_mapping or ())
    if position is not None:
        if properties.s is not None:
            com.set_property(position, "S", properties.s)
        if properties.d is not None:
            com.set_property(position, "D", properties.d)


def _resolve_road_connection_point(road: Any, connection_point: RoadConnectionPointKind) -> Any:
    connection_points = _get_required_property(road, "ConnectionPoints")
    count = com.get_count(connection_points)
    if count > MAX_CONNECTION_POINT_COUNT:
        raise RuntimeError(f"Road connection point collection has {count} entries, which exceeds the supported safety limit of {MAX_CONNECTION_POINT_COUNT}.")
    for index in range(count):
        candidate = _invoke_required_item(connection_points, index, "connection point")
        if _read_int_property(candidate, "Type") == int(connection_point):
            return candidate
    raise RuntimeError(f"Road '{_read_road_name(road)}' does not expose a {connection_point.display_name} connection point.")


def _parse_connection_point(value: str | None, default_value: RoadConnectionPointKind) -> RoadConnectionPointKind:
    if value is None or value.strip() == "":
        return default_value
    normalized = value.strip().lower()
    if normalized == "start":
        return RoadConnectionPointKind.START
    if normalized == "end":
        return RoadConnectionPointKind.END
    raise ValueError(f"Unsupported road connection point '{value}'. Use Start or End.")


def _parse_connection_mode(value: str | None) -> RoadConnectionMode:
    if value is None or value.strip() == "":
        return RoadConnectionMode.MOVE
    normalized = value.strip().lower()
    if normalized == "move":
        return RoadConnectionMode.MOVE
    if normalized == "modify":
        return RoadConnectionMode.MODIFY
    raise ValueError(f"Unsupported road connection mode '{value}'. Use Move or Modify.")


def _get_scenario_fellows_collection(application: Any) -> Any:
    return _get_first_available_property(_get_active_traffic_scenario(application), "Fellows", "TrafficParticipants", "Participants")


def _resolve_fellow_index_by_name(fellows: Any, name: str) -> int:
    """Resolve a fellow's 0-based collection position by its plain Name.

    ModelDesk's Fellows.Item(string)/Remove(string) only match against
    CompleteName ("F{Index}: {Name}") or the bare "F{Index}" pattern, never
    the plain Name that modeldesk_list_scenario_fellows exposes as a name
    selector value, so a plain name must be resolved to a position here first.
    """
    count = com.get_count(fellows)
    for index in range(count):
        candidate = _invoke_required_item(fellows, index, "fellow")
        if com.get_string_property(candidate, "Name") == name:
            return index
    raise RuntimeError(f"No fellow found with name '{name}'.")


def _resolve_fellow(fellows: Any, fellow_selector: Selector) -> Any:
    """Resolve a fellow selector against the Fellows collection."""

    fellow_selector.validate()
    if fellow_selector.by == SelectorKind.NAME:
        index = _resolve_fellow_index_by_name(fellows, fellow_selector.value)
        return _invoke_required_item(fellows, index, "fellow")
    return com.resolve_item(fellows, fellow_selector)


def _fellow_selector_to_index_selector(fellows: Any, fellow_selector: Selector) -> Selector:
    """Return an index-based selector equivalent, translating a name selector first."""

    if fellow_selector.by == SelectorKind.NAME:
        return Selector(SelectorKind.INDEX, str(_resolve_fellow_index_by_name(fellows, fellow_selector.value)))
    return fellow_selector


def _get_scenario_maneuvers_collection(application: Any, fellow_selector: Selector) -> Any:
    if fellow_selector.by == SelectorKind.ACTIVE:
        return _get_first_available_property(_get_active_traffic_scenario(application), "Maneuvers", "Maneuver", "ManeuverSequence")
    fellows = _get_scenario_fellows_collection(application)
    fellow = _resolve_fellow(fellows, fellow_selector)
    # A fellow's maneuver-like data lives under Sequences, not under the ego's
    # Maneuvers/Maneuver/ManeuverSequence property names (FellowAutomation has none of those).
    return _get_first_available_property(fellow, "Sequences")


def _resolve_ego_maneuver_sequence(maneuver: Any) -> Any:
    """Resolve the only unambiguous sequence beneath a selected ego maneuver.

    The public selector identifies ``TrafficScenario.Maneuver[index]`` but has
    no sequence index. Empty or multiple source sequences therefore fail before
    mutation instead of silently targeting an unrelated sequence.
    """

    sequences = _get_required_property(maneuver, "Sequences")
    sequence_count = com.get_count(sequences)
    if sequence_count == 0:
        raise RuntimeError("The selected ego maneuver has no sequences.")
    if sequence_count > 1:
        raise RuntimeError(
            "The selected ego maneuver has multiple sequences; this operation has no sequence selector."
        )
    sequence = com.invoke_item(sequences, 0)
    if sequence is None:
        raise RuntimeError("The selected ego maneuver's sequence could not be read.")
    return sequence


def _get_vehicle_object_type_manager(application: Any, fellow_selector: Selector, maneuver_index: int) -> tuple[Any, str]:
    """Return (type_manager, domain_label) for the given fellow or ego maneuver."""

    scenario = _get_active_traffic_scenario(application)
    if fellow_selector.by == SelectorKind.ACTIVE:
        # Ego vehicle: TrafficScenario.Maneuver[maneuver_index].ContourLineObjectType
        maneuver_collection = _get_first_available_property(scenario, "Maneuvers", "Maneuver", "ManeuverSequence")
        maneuver = _invoke_required_item(maneuver_collection, maneuver_index, "ego maneuver")
        type_manager = _get_first_available_property(maneuver, "ContourLineObjectType", "ObjectType", "TrafficObjectType")
        return type_manager, f"ego.maneuver[{maneuver_index}]"
    # Fellow: TrafficScenario.Fellows[i].TrafficObjectType
    fellows = _get_scenario_fellows_collection(application)
    fellow = _resolve_fellow(fellows, fellow_selector)
    type_manager = _get_first_available_property(fellow, "TrafficObjectType", "ContourLineObjectType", "ObjectType")
    return type_manager, f"fellow[{fellow_selector.by.value}={fellow_selector.value}]"


def _available_type_elements(type_manager: Any) -> list[Any]:
    """Return available type elements as a Python list.

    Some COM automation layers return AvailableElements as a Python SAFEARRAY
    (tuple/list) instead of a COM collection object. This helper normalises both
    cases so callers never need to distinguish them.
    """

    available = _get_first_available_property(type_manager, "AvailableElements", "Elements", "Available")
    if isinstance(available, (tuple, list)):
        return list(available)
    count = com.get_count(available)
    return [_invoke_required_item(available, i, "type element") for i in range(count)]


def _summarize_type_elements(
    domain: str,
    elements: list[Any],
    item_kind: str,
    max_items: int,
    offset: int = 0,
) -> DomainSummary:
    """Build a DomainSummary from a Python list of type elements."""

    if max_items <= 0:
        raise ValueError("Maximum item count must be greater than zero.")
    if offset < 0:
        raise ValueError("Collection offset must not be negative.")
    end_offset = min(len(elements), offset + max_items)
    bounded = elements[offset:end_offset]
    items: list[ItemSummary] = []
    for index, element in enumerate(bounded, start=offset):
        name = com.read_display_name(element, item_kind, index) if element is not None else f"{item_kind} {index}"
        path = com.get_first_string_property(element, "Path", "CompleteName", "FileName") if element is not None else None
        kind = com.get_first_string_property(element, "TypeName", "Kind", "ObjectType") if element is not None else None
        items.append(ItemSummary(index, name, kind, path))
    next_offset = end_offset if end_offset < len(elements) else None
    message = f"More items available; request offset {next_offset}." if next_offset is not None else None
    return DomainSummary(domain, True, len(elements), tuple(items), {}, message, next_offset)


def _apply_traffic_object_reference(application: Any, fellow: Any, traffic_object_selector: Selector | None, traffic_object_catalog_path: str | None) -> None:
    reference_path = _normalize_optional_text(traffic_object_catalog_path)
    if traffic_object_selector is not None:
        manager = _get_traffic_object_manager(application)
        traffic_objects = _get_first_available_property(manager, "TrafficObjects", "Objects")
        traffic_object = com.resolve_item(traffic_objects, traffic_object_selector)
        reference_path = com.get_first_string_property(traffic_object, "Path", "CompleteName", "Name")
    if reference_path is None:
        return
    activated = _try_activate_reference(fellow, reference_path, "TrafficObjectType", "ObjectType", "VehicleType")
    if not activated:
        assigned = _try_set_first_available_string_property(fellow, reference_path, "TrafficObject", "TrafficObjectName", "TrafficObjectPath")
        if not assigned:
            raise RuntimeError("Could not assign traffic object reference on fellow.")


def _apply_traffic_driver_reference(fellow: Any, traffic_driver_reference: str | None) -> None:
    normalized_reference = _normalize_optional_text(traffic_driver_reference)
    if normalized_reference is None:
        return
    activated = _try_activate_reference(fellow, normalized_reference, "TrafficDriverType", "DriverType", "Driver")
    if not activated:
        assigned = _try_set_first_available_string_property(fellow, normalized_reference, "TrafficDriver", "TrafficDriverName", "Driver", "DriverName")
        if not assigned:
            raise RuntimeError("Could not assign traffic driver reference on fellow.")


def _try_activate_reference(owner: Any, reference: str, *type_property_candidates: str) -> bool:
    for property_name in type_property_candidates:
        has_value, type_object = com.try_get_property(owner, property_name)
        if not has_value or type_object is None:
            continue
        result = com.invoke_method(type_object, "Activate", reference)
        if isinstance(result, bool) and not result:
            raise RuntimeError(f"Activation via '{property_name}.Activate' returned false.")
        return True
    return False


def _try_set_first_available_string_property(owner: Any, value: str, *property_candidates: str) -> bool:
    for property_name in property_candidates:
        has_value, _ = com.try_get_property(owner, property_name)
        if not has_value:
            continue
        com.set_property(owner, property_name, value)
        return True
    return False


def _activate_available_profile_element(
    selection_manager: Any,
    element_name: str,
    selection_label: str,
    mark_mutation: Callable[[], None],
) -> Any:
    available_elements = com.get_property(selection_manager, "AvailableElements")
    if isinstance(available_elements, str):
        normalized_available_elements = (available_elements,)
    else:
        try:
            normalized_available_elements = tuple(available_elements)
        except TypeError as exception:
            raise RuntimeError(f"Could not read available {selection_label} elements.") from exception
    if element_name not in normalized_available_elements:
        raise RuntimeError(f"{selection_label} '{element_name}' is unavailable.")
    mark_mutation()
    com.invoke_method(selection_manager, "Activate", element_name)
    return _get_required_property(selection_manager, "ActiveElement")


def _set_and_verify_profile_property(target: Any, property_name: str, requested_value: Any, target_label: str) -> Any:
    try:
        com.set_property(target, property_name, requested_value)
        actual_value = com.get_property(target, property_name)
    except Exception as exception:
        raise RuntimeError(f"{target_label}.{property_name} could not be assigned and read back: {exception}") from exception

    if isinstance(requested_value, int | float) and not isinstance(requested_value, bool):
        try:
            actual_is_finite_number = (
                isinstance(actual_value, int | float)
                and not isinstance(actual_value, bool)
                and math.isfinite(actual_value)
            )
        except OverflowError:
            actual_is_finite_number = False
        values_match = actual_is_finite_number and actual_value == requested_value
    else:
        values_match = type(actual_value) is type(requested_value) and actual_value == requested_value
    if not values_match:
        raise RuntimeError(f"{target_label}.{property_name} read-back did not match the requested value.")
    return actual_value


def _apply_verified_scalar_properties(
    target: Any,
    properties: dict[str, Any],
    parameter_name: str,
    mark_mutation: Callable[[], None],
    depth: int = 0,
) -> int:
    if depth > 4:
        raise ValueError("Nested profile depth greater than 4 is not supported.")
    updated_count = 0
    for property_name, value in properties.items():
        if isinstance(value, dict):
            nested_target = _get_required_property(target, property_name)
            updated_count += _apply_verified_scalar_properties(
                nested_target,
                value,
                parameter_name,
                mark_mutation,
                depth + 1,
            )
        else:
            mark_mutation()
            _set_and_verify_profile_property(target, property_name, value, parameter_name)
            updated_count += 1
    return updated_count


def _apply_scalar_properties_from_json(target: Any, properties_json: str | None, parameter_name: str) -> int:
    properties = parse_scalar_properties_json(properties_json, parameter_name)
    updated_count = 0
    for property_name, value in properties.items():
        if isinstance(value, dict):
            nested_target = _get_required_property(target, property_name)
            updated_count += _apply_scalar_property_dict(nested_target, value, parameter_name, 1)
        else:
            com.set_property(target, property_name, value)
            updated_count += 1
    return updated_count


def _apply_scalar_property_dict(target: Any, properties: dict[str, Any], parameter_name: str, depth: int) -> int:
    if depth > 4:
        raise ValueError("Nested profile depth greater than 4 is not supported.")
    if len(properties) > 64:
        raise ValueError("At most 64 properties are supported per JSON object.")
    updated_count = 0
    for property_name, value in properties.items():
        if isinstance(value, dict):
            nested_target = _get_required_property(target, property_name)
            updated_count += _apply_scalar_property_dict(nested_target, value, parameter_name, depth + 1)
        elif isinstance(value, list):
            raise ValueError(f"Array values are not supported for property '{property_name}'.")
        else:
            com.set_property(target, property_name, value)
            updated_count += 1
    return updated_count


def _remove_collection_item(collection: Any, selector: Selector, item_kind: str) -> None:
    selector.validate()
    if selector.by == SelectorKind.ACTIVE:
        raise ValueError(f"Active selector is not supported for removing {item_kind}.")
    remove_result = com.invoke_method(collection, "Remove", selector.to_com_value())
    if isinstance(remove_result, bool):
        if not remove_result:
            raise RuntimeError(f"Removing {item_kind} returned false.")
    return


def _apply_scenario_save_download(application: Any, save: bool, download: bool, details: dict[str, str | None]) -> None:
    active_experiment = _get_active_experiment(application)
    if save:
        _invoke_boolean_aware_method(active_experiment, "Save")
    if download:
        _invoke_boolean_aware_method(active_experiment, "Download")
    details["saved"] = str(save)
    details["downloaded"] = str(download)


def _create_road_details(road: Any, roads: Any) -> dict[str, str | None]:
    segments = _get_required_property(road, "Segments")
    lane_sections = _get_required_property(road, "LaneSections")
    road_objects = _get_required_property(road, "Objects")
    return {
        "roadName": _read_road_name(road),
        "roadCount": str(com.get_count(roads)),
        "roadLength": str(_read_double_property(road, "Length")),
        "segmentCount": str(com.get_count(segments)),
        "laneSectionCount": str(com.get_count(lane_sections)),
        "objectCount": str(com.get_count(road_objects)),
    }


def _create_segment_details(road: Any, segments: Any, typed_segment: Any) -> dict[str, str | None]:
    details = {
        "roadName": _read_road_name(road),
        "segmentName": com.get_string_property(typed_segment, "Name"),
        "segmentIndex": str(_read_int_property(typed_segment, "Index")),
        "segmentType": _read_segment_type(typed_segment).display_name,
        "segmentS": str(_read_double_property(typed_segment, "S")),
        "segmentCount": str(com.get_count(segments)),
        "roadLength": str(_read_double_property(road, "Length")),
    }
    has_length, length = com.try_get_property(typed_segment, "Length")
    if has_length and length is not None:
        details["segmentLength"] = str(float(length))
    return details


def _create_lane_section_details(road: Any, lane_section: Any, lane_section_index: int) -> dict[str, str | None]:
    lanes = _get_required_property(lane_section, "Lanes")
    left_count, right_count = _count_lane_sides(lanes)
    return {
        "roadName": _read_road_name(road),
        "laneSectionIndex": str(lane_section_index),
        "laneSectionName": com.get_string_property(lane_section, "Name"),
        "laneSectionLength": str(_read_double_property(lane_section, "Length")),
        "leftLaneCount": str(left_count),
        "rightLaneCount": str(right_count),
        "laneCount": str(com.get_count(lanes)),
    }


def _create_road_object_details(road: Any, road_objects: Any, road_object: Any) -> dict[str, str | None]:
    position = _get_required_property(road_object, "Position")
    return {
        "roadName": _read_road_name(road),
        "objectName": com.get_string_property(road_object, "Name"),
        "objectId": com.get_string_property(road_object, "ObjectID"),
        "objectCount": str(com.get_count(road_objects)),
        "s": str(_read_double_property(position, "S")),
        "d": str(_read_double_property(position, "D")),
    }


def _apply_road_network_save_download(road_network: Any, save: bool, download: bool, details: dict[str, str | None]) -> None:
    if save:
        _invoke_boolean_aware_method(road_network, "Save")
    if download:
        _invoke_boolean_aware_method(road_network, "Download")
    details["saved"] = str(save)
    details["downloaded"] = str(download)


def _read_road_name(road: Any) -> str:
    return com.get_string_property(road, "Name") or "Road"


def _read_double_property(instance: Any, property_name: str) -> float:
    value = com.get_property(instance, property_name)
    if value is None:
        raise RuntimeError(f"Required numeric COM property '{property_name}' is not available.")
    return float(value)


def _read_int_property(instance: Any, property_name: str) -> int:
    value = com.get_property(instance, property_name)
    if value is None:
        raise RuntimeError(f"Required integer COM property '{property_name}' is not available.")
    return int(value)


def _set_optional_property(instance: Any, property_name: str, value: float | None) -> None:
    if value is not None:
        com.set_property(instance, property_name, value)


def _validate_lane_configuration(left_lane_count: int, right_lane_count: int, lane_width: float) -> None:
    _validate_lane_count(left_lane_count, "leftLaneCount")
    _validate_lane_count(right_lane_count, "rightLaneCount")
    if left_lane_count + right_lane_count == 0:
        raise ValueError("At least one left or right lane is required.")
    if not _is_finite(lane_width) or lane_width <= 0.0 or lane_width > MAX_LANE_WIDTH:
        raise ValueError(f"Lane width must be finite, > 0 and <= {MAX_LANE_WIDTH}.")


def _validate_lane_count(lane_count: int, parameter_name: str) -> None:
    if lane_count < 0 or lane_count > MAX_LANE_COUNT_PER_SIDE:
        raise ValueError(f"{parameter_name} must be between 0 and {MAX_LANE_COUNT_PER_SIDE}.")


def _validate_road_object_position(s: float, d: float, road_length: float) -> None:
    if not _is_finite(s) or not _is_finite(d):
        raise ValueError("Road object s and d values must be finite.")
    maximum_s = road_length if road_length > 0.0 else MAX_ROAD_LENGTH
    if s < 0.0 or s > maximum_s:
        raise ValueError(f"Road object s must be >= 0 and <= road length {maximum_s}.")


def _configure_lanes(lanes: Any, left_lane_count: int, right_lane_count: int, lane_width: float) -> None:
    left_count, right_count = _count_lane_sides(lanes)
    _remove_lane_side(lanes, ROAD_SIDE_TYPE_LEFT, left_count, left_lane_count)
    _remove_lane_side(lanes, ROAD_SIDE_TYPE_RIGHT, right_count, right_lane_count)
    reduced_left_count, reduced_right_count = _count_lane_sides(lanes)
    _add_lane_side(lanes, ROAD_SIDE_TYPE_LEFT, reduced_left_count, left_lane_count, lane_width)
    _add_lane_side(lanes, ROAD_SIDE_TYPE_RIGHT, reduced_right_count, right_lane_count, lane_width)
    _set_all_lane_widths(lanes, lane_width)


def _count_lane_sides(lanes: Any) -> tuple[int, int]:
    lane_count = com.get_count(lanes)
    if lane_count > MAX_OBSERVED_LANE_COUNT:
        raise RuntimeError(f"Lane collection has {lane_count} entries, which exceeds the supported safety limit of {MAX_OBSERVED_LANE_COUNT}.")
    left_count = 0
    right_count = 0
    for lane_index in range(lane_count):
        lane = _invoke_required_item(lanes, lane_index, "lane")
        road_lane_index = _read_int_property(lane, "LaneIndex")
        if road_lane_index > 0:
            left_count += 1
        elif road_lane_index < 0:
            right_count += 1
    return left_count, right_count


def _remove_lane_side(lanes: Any, road_side_type: int, existing_count: int, requested_count: int) -> None:
    for _ in range(existing_count, requested_count, -1):
        result = com.invoke_method(lanes, "Remove", road_side_type)
        if isinstance(result, bool) and not result:
            raise RuntimeError("Lane removal returned false.")


def _add_lane_side(lanes: Any, road_side_type: int, existing_count: int, requested_count: int, lane_width: float) -> None:
    for _ in range(existing_count, requested_count):
        lane = _invoke_required_method(lanes, "Add", road_side_type)
        com.set_property(lane, "Width", lane_width)


def _set_all_lane_widths(lanes: Any, lane_width: float) -> None:
    lane_count = com.get_count(lanes)
    if lane_count > MAX_OBSERVED_LANE_COUNT:
        raise RuntimeError(f"Lane collection has {lane_count} entries, which exceeds the supported safety limit of {MAX_OBSERVED_LANE_COUNT}.")
    for lane_index in range(lane_count):
        lane = _invoke_required_item(lanes, lane_index, "lane")
        com.set_property(lane, "Width", lane_width)


def _create_traffic_objects(road_objects: Any, request: BasicRoadCreationRequest) -> tuple[BasicRoadCreatedTrafficObject, ...]:
    created: list[BasicRoadCreatedTrafficObject] = []
    for traffic_object in request.traffic_objects:
        road_object = _invoke_required_method(road_objects, "Add", traffic_object.s, traffic_object.d)
        _apply_road_object_base_properties(road_object, traffic_object.name, traffic_object.catalog_path, traffic_object.lane_mapping)
        created.append(BasicRoadCreatedTrafficObject(traffic_object.name, traffic_object.catalog_path, traffic_object.s, traffic_object.d, traffic_object.lane_mapping))
    return tuple(created)


def _get_or_create_first_collection_item(collection: Any, item_kind: str) -> Any:
    if com.get_count(collection) > 0:
        return _invoke_required_item(collection, 0, item_kind)
    return _invoke_required_method(collection, "Add")


def _invoke_required_method(instance: Any, method_name: str, *arguments: Any) -> Any:
    result = com.invoke_method(instance, method_name, *arguments)
    if result is None:
        raise RuntimeError(f"COM method '{method_name}' did not return an object.")
    return result


def _invoke_required_item(collection: Any, index: int, item_kind: str) -> Any:
    item = com.invoke_item(collection, index)
    if item is None:
        raise RuntimeError(f"Could not resolve {item_kind} at index {index}.")
    return item


def _invoke_boolean_aware_method(instance: Any, method_name: str) -> None:
    result = com.invoke_method(instance, method_name)
    if isinstance(result, bool) and not result:
        raise RuntimeError(f"COM method '{method_name}' returned false.")


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _enumerate_environment_pool_files(
    group_path: Path,
    request: EnvironmentPoolGroupRequest,
    max_items: int,
    offset: int = 0,
) -> tuple[tuple[Path, ...], int, int | None]:
    if max_items <= 0:
        raise ValueError("Maximum item count must be greater than zero.")
    if offset < 0:
        raise ValueError("Collection offset must not be negative.")
    pattern = f"*{request.file_extension()}"
    iterator: Iterable[Path] = group_path.rglob(pattern) if request.recursive else group_path.glob(pattern)
    paths: list[Path] = []
    for path in iterator:
        if path.is_file():
            paths.append(path)
    paths.sort(key=lambda value: str(value).lower())
    end_offset = min(len(paths), offset + max_items)
    page_paths = tuple(paths[offset:end_offset])
    next_offset = end_offset if end_offset < len(paths) else None
    return page_paths, len(paths), next_offset


def _environment_pool_item_name(group_path: Path, file_path: Path) -> str:
    try:
        relative_path = file_path.relative_to(group_path)
    except ValueError:
        relative_path = file_path.name
    without_suffix = Path(relative_path).with_suffix("")
    text = str(without_suffix).replace("\\", "/")
    return text if text.strip() != "" else file_path.stem


def _classify_error(exception: Exception) -> str:
    if isinstance(exception, TimeoutError):
        return "timeout"
    if isinstance(exception, FileNotFoundError):
        return "not_found"
    if isinstance(exception, ValueError | TypeError | IndexError):
        return "validation"
    if isinstance(exception, RuntimeError):
        return "invalid_state"
    if isinstance(exception, com.COM_ERROR_TYPES):
        return "com_error"
    return "unexpected"


def _dry_run_preview(
    operation_name: str,
    details: dict[str, str | None],
    save: bool | None = None,
    download: bool | None = None,
    message: str = "Dry-run preview; no changes were applied.",
) -> OperationInfo:
    preview_details = dict(details)
    preview_details["dryRun"] = "true"
    if save is not None:
        preview_details["wouldSave"] = str(save).lower()
    if download is not None:
        preview_details["wouldDownload"] = str(download).lower()
    return OperationInfo(operation_name, True, message, preview_details)
