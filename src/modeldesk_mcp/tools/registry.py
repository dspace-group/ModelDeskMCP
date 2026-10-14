"""Register the public ModelDesk MCP tool surface with FastMCP.

``EXPECTED_TOOL_NAMES`` is the public registration contract: names are lowercase
``modeldesk_`` identifiers, remain unique, and are registered in tuple order.
``TOOL_DOMAIN_BY_NAME`` records one owner for every name across the five public
boundaries: General COM Automation, Scenario/TrafficScenario,
Road/RoadGenerator, Plotting/PlotManager, and
TrafficObjectManager/TrafficObject/TOM. General automation also owns lifecycle,
parameter, processing, testing, and workflow tools that do not belong to one of
the specialized domains.

The wrappers below intentionally convert ``ToolResult`` objects to plain data;
they do not call COM directly. COM access remains behind the service and
``modeldesk_mcp.com_bridge`` boundary.
SDK-native field metadata documents the input properties, while a stable
typed output payload documents the data returned by each operation.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict, get_args, get_type_hints

from mcp.types import ToolAnnotations
from pydantic import Field

from modeldesk_mcp.contracts import ToolResult
from modeldesk_mcp.domain import ModelDeskService


EXPECTED_TOOL_NAMES = (
    "modeldesk_get_status",
    "modeldesk_get_capabilities",
    "modeldesk_open_project",
    "modeldesk_create_project_pool_file",
    "modeldesk_create_road_network",
    "modeldesk_create_traffic_scenario",
    "modeldesk_list_environment_pool_items",
    "modeldesk_save_project",
    "modeldesk_close_project",
    "modeldesk_list_experiments",
    "modeldesk_activate_experiment",
    "modeldesk_save_active_experiment",
    "modeldesk_download_active_experiment",
    "modeldesk_list_parameter_sets",
    "modeldesk_activate_parameter_set",
    "modeldesk_get_parameterization_summary",
    "modeldesk_get_active_model_info",
    "modeldesk_set_active_model",
    "modeldesk_get_parameter_value",
    "modeldesk_set_scalar_parameter",
    "modeldesk_set_parameter_value",
    "modeldesk_get_road_summary",
    "modeldesk_activate_road",
    "modeldesk_list_roads",
    "modeldesk_save_road_network_as",
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
    "modeldesk_get_scenario_summary",
    "modeldesk_activate_scenario",
    "modeldesk_list_scenario_fellows",
    "modeldesk_list_scenario_maneuvers",
    "modeldesk_add_scenario_fellow",
    "modeldesk_update_scenario_fellow",
    "modeldesk_remove_scenario_fellow",
    "modeldesk_add_scenario_maneuver",
    "modeldesk_update_scenario_maneuver",
    "modeldesk_remove_scenario_maneuver",
    "modeldesk_set_scenario_maneuver_sequence",
    "modeldesk_set_maneuver_behavior_profiles",
    "modeldesk_get_scenario_road",
    "modeldesk_set_scenario_road",
    "modeldesk_list_fellow_activities",
    "modeldesk_get_vehicle_object_type",
    "modeldesk_list_vehicle_object_types",
    "modeldesk_set_vehicle_object_type",
    "modeldesk_get_traffic_objects_summary",
    "modeldesk_list_traffic_objects",
    "modeldesk_list_traffic_object_folders",
    "modeldesk_validate_traffic_object_reference",
    "modeldesk_add_traffic_object",
    "modeldesk_remove_traffic_object",
    "modeldesk_add_traffic_object_folder",
    "modeldesk_remove_traffic_object_folder",
    "modeldesk_get_processing_summary",
    "modeldesk_get_processing_configuration",
    "modeldesk_run_processing",
    "modeldesk_get_test_summary",
    "modeldesk_activate_test",
    "modeldesk_list_logical_test_cases",
    "modeldesk_list_concrete_test_cases",
    "modeldesk_execute_test",
    "modeldesk_get_plotting_summary",
    "modeldesk_activate_plotting",
    "modeldesk_list_plot_captures",
    "modeldesk_list_plot_layouts",
    "modeldesk_compare_captures",
    "modeldesk_start_maneuver",
    "modeldesk_stop_maneuver",
    "modeldesk_reset_maneuver",
    "modeldesk_synchronize_aurelion",
    "modeldesk_get_workflow_plan",
    "modeldesk_list_tools_by_use_case",
)

TOOL_DOMAINS = (
    "General COM Automation",
    "Scenario/TrafficScenario",
    "Road/RoadGenerator",
    "Plotting/PlotManager",
    "TrafficObjectManager/TrafficObject/TOM",
)


class ToolArtifactEnvelope(TypedDict):
    """Stable artifact fields serialized by ``ToolResult.to_dict``."""

    kind: str
    path: str
    description: str | None


ToolErrorCode = Literal["validation", "not_found", "timeout", "invalid_state", "com_error", "unexpected"]


class ToolErrorEnvelope(TypedDict):
    """Stable structured error fields serialized by ``ToolResult.to_dict``."""

    errorType: ToolErrorCode
    message: str
    operation: str
    recovery: str | None
    isRetryable: bool


class _ItemSummaryData(TypedDict):
    index: int
    name: str
    kind: str | None
    path: str | None


class _DomainSummaryData(TypedDict):
    domain: str
    available: bool
    count: int
    items: list[_ItemSummaryData]
    properties: dict[str, str | None]
    message: str | None
    nextOffset: int | None


class _OperationInfoData(TypedDict):
    operation: str
    completed: bool
    message: str | None
    details: dict[str, str | None] | None


class _ModelDeskStatusData(TypedDict):
    sessionId: str
    modelDeskReachable: bool
    modelDeskVersion: str | None
    hasActiveProject: bool
    activeProjectName: str | None
    activeExperimentName: str | None
    progId: str
    processArchitecture: str


class _CapabilityReportData(TypedDict):
    serverVersion: str
    dotNetVersion: str | None
    operatingSystem: str
    isWindows: bool
    progId: str
    modelDeskReachable: bool
    domains: dict[str, bool]
    disabledCapabilities: list[str]
    pythonVersion: str


class _ProjectInfoData(TypedDict):
    hasActiveProject: bool
    name: str | None
    workingRoot: str | None
    activeExperimentName: str | None


class _ProjectPoolFileCreationInfoData(TypedDict):
    fileType: str
    typeId: int
    name: str
    expectedExtension: str
    overwriteExisting: bool
    createdName: str | None
    createdPath: str | None
    createdTypeName: str | None
    message: str


class _ParameterValueInfoData(TypedDict):
    parameterPath: str
    name: str | None
    typeName: str | None
    unit: str | None
    value: str | None
    numericValue: float | None


class _BasicRoadCreatedTrafficObjectData(TypedDict):
    name: str | None
    catalogPath: str | None
    s: float
    d: float
    laneMapping: list[int]


class _BasicRoadCreationInfoData(TypedDict):
    roadName: str
    length: float
    leftLaneCount: int
    rightLaneCount: int
    laneWidth: float
    segmentCount: int
    laneSectionCount: int
    trafficObjectCount: int
    saved: bool
    downloaded: bool
    trafficObjects: list[_BasicRoadCreatedTrafficObjectData]
    message: str


class _WorkflowPlanData(TypedDict):
    name: str
    useCase: str
    dryRunOnly: bool
    steps: list[str]
    requiredTools: list[str]
    message: str | None


class _CaptureSummaryData(TypedDict):
    name: str
    sizeBytes: int
    sampleCount: int
    signalCount: int
    timeStart: float
    timeEnd: float
    duration: float


class _SignalSetData(TypedDict):
    common: list[str]
    onlyReference: list[str]
    onlyCandidate: list[str]


class _SignalMetricsData(TypedDict):
    meanDifference: float
    meanAbsoluteError: float
    rootMeanSquaredError: float
    maximumAbsoluteError: float


class _SignalComparisonData(TypedDict):
    referenceSignal: str
    candidateSignal: str
    referenceUnit: str
    candidateUnit: str
    alignment: str
    status: str
    sampleCount: int
    timeStart: float
    timeEnd: float
    metrics: _SignalMetricsData
    tolerances: dict[str, float]
    withinTolerance: bool | None


class _CaptureComparisonData(TypedDict):
    referenceCapture: _CaptureSummaryData
    candidateCapture: _CaptureSummaryData
    signalSet: _SignalSetData
    comparisons: list[_SignalComparisonData]
    verdict: str


class _UseCaseToolsData(TypedDict):
    useCase: str
    title: str
    tools: list[str]
    toolCount: int


_DOMAIN_SUMMARY_TOOL_NAMES = frozenset(
    {
        "modeldesk_list_environment_pool_items",
        "modeldesk_list_experiments",
        "modeldesk_list_parameter_sets",
        "modeldesk_get_parameterization_summary",
        "modeldesk_get_active_model_info",
        "modeldesk_get_road_summary",
        "modeldesk_list_roads",
        "modeldesk_get_scenario_summary",
        "modeldesk_list_scenario_fellows",
        "modeldesk_list_scenario_maneuvers",
        "modeldesk_list_fellow_activities",
        "modeldesk_list_vehicle_object_types",
        "modeldesk_get_traffic_objects_summary",
        "modeldesk_list_traffic_objects",
        "modeldesk_list_traffic_object_folders",
        "modeldesk_get_processing_summary",
        "modeldesk_get_processing_configuration",
        "modeldesk_get_test_summary",
        "modeldesk_list_logical_test_cases",
        "modeldesk_list_concrete_test_cases",
        "modeldesk_get_plotting_summary",
        "modeldesk_list_plot_captures",
        "modeldesk_list_plot_layouts",
    }
)
_TOOL_DATA_TYPE_BY_NAME: dict[str, Any] = {name: _OperationInfoData for name in EXPECTED_TOOL_NAMES}
_TOOL_DATA_TYPE_BY_NAME.update({name: _DomainSummaryData for name in _DOMAIN_SUMMARY_TOOL_NAMES})
_TOOL_DATA_TYPE_BY_NAME.update(
    {
        "modeldesk_get_status": _ModelDeskStatusData,
        "modeldesk_get_capabilities": _CapabilityReportData,
        "modeldesk_open_project": _ProjectInfoData,
        "modeldesk_create_project_pool_file": _ProjectPoolFileCreationInfoData,
        "modeldesk_create_road_network": _ProjectPoolFileCreationInfoData,
        "modeldesk_create_traffic_scenario": _ProjectPoolFileCreationInfoData,
        "modeldesk_get_parameter_value": _ParameterValueInfoData,
        "modeldesk_create_basic_road": _BasicRoadCreationInfoData,
        "modeldesk_compare_captures": _CaptureComparisonData,
        "modeldesk_get_workflow_plan": _WorkflowPlanData,
        "modeldesk_list_tools_by_use_case": _UseCaseToolsData,
    }
)


def _tool_result_envelope_for(tool_name: str) -> Any:
    envelope_name = "".join(part.title() for part in tool_name.split("_")) + "ResultEnvelope"
    envelope = TypedDict(
        envelope_name,
        {
            "ok": bool,
            "operation": str,
            "sessionId": str,
            "data": Any,
            "warnings": list[str],
            "artifacts": list[ToolArtifactEnvelope],
            "error": ToolErrorEnvelope | None,
        },
    )
    envelope.__annotations__["data"] = _TOOL_DATA_TYPE_BY_NAME[tool_name] | None
    envelope.__module__ = __name__
    return envelope


_READ_ONLY_TOOL_NAMES = frozenset(
    {
        "modeldesk_get_status",
        "modeldesk_get_capabilities",
        "modeldesk_list_environment_pool_items",
        "modeldesk_list_experiments",
        "modeldesk_list_parameter_sets",
        "modeldesk_get_parameterization_summary",
        "modeldesk_get_active_model_info",
        "modeldesk_get_parameter_value",
        "modeldesk_get_road_summary",
        "modeldesk_list_roads",
        "modeldesk_get_scenario_summary",
        "modeldesk_list_scenario_fellows",
        "modeldesk_list_scenario_maneuvers",
        "modeldesk_get_scenario_road",
        "modeldesk_list_fellow_activities",
        "modeldesk_get_vehicle_object_type",
        "modeldesk_list_vehicle_object_types",
        "modeldesk_get_traffic_objects_summary",
        "modeldesk_list_traffic_objects",
        "modeldesk_list_traffic_object_folders",
        "modeldesk_validate_traffic_object_reference",
        "modeldesk_get_processing_summary",
        "modeldesk_get_processing_configuration",
        "modeldesk_get_test_summary",
        "modeldesk_list_logical_test_cases",
        "modeldesk_list_concrete_test_cases",
        "modeldesk_get_plotting_summary",
        "modeldesk_list_plot_captures",
        "modeldesk_list_plot_layouts",
        "modeldesk_compare_captures",
        "modeldesk_get_workflow_plan",
        "modeldesk_list_tools_by_use_case",
    }
)
_ADDITIVE_TOOL_NAMES = frozenset(
    {
        "modeldesk_add_road",
        "modeldesk_create_basic_road",
        "modeldesk_add_road_segment",
        "modeldesk_add_road_object",
        "modeldesk_add_scenario_fellow",
        "modeldesk_add_scenario_maneuver",
        "modeldesk_add_traffic_object",
        "modeldesk_add_traffic_object_folder",
    }
)
_OPEN_WORLD_TOOL_NAMES = frozenset({"modeldesk_synchronize_aurelion"})
_TOOLS_WITHOUT_COM_PRECONDITIONS = frozenset(
    {"modeldesk_get_workflow_plan", "modeldesk_list_tools_by_use_case"}
)
_REPLAY_RISK_NOTES = {
    "modeldesk_create_project_pool_file": "Replay risk: with overwriteExisting=true, retrying can overwrite an existing pool file.",
    "modeldesk_create_road_network": "Replay risk: with overwriteExisting=true, retrying can overwrite an existing road network.",
    "modeldesk_create_traffic_scenario": "Replay risk: with overwriteExisting=true, retrying can overwrite an existing traffic scenario.",
    "modeldesk_add_road": "Replay risk: retrying may add a duplicate road; inspect the active network first.",
    "modeldesk_add_road_segment": "Replay risk: retrying may add a duplicate segment; inspect the selected road first.",
    "modeldesk_add_road_object": "Replay risk: retrying may add a duplicate road object; inspect the selected road first.",
    "modeldesk_connect_roads": "Replay risk: the first call may already have changed road geometry; inspect both endpoints before retrying.",
    "modeldesk_create_basic_road": "Replay risk: retrying may add a duplicate road and traffic objects; inspect the active network first.",
    "modeldesk_add_scenario_fellow": "Replay risk: retrying may add a duplicate fellow; inspect the active scenario first.",
    "modeldesk_add_scenario_maneuver": "Replay risk: retrying may add a duplicate maneuver; inspect the selected scope first.",
    "modeldesk_add_traffic_object": "Replay risk: retrying may add a duplicate catalog object; inspect the catalog first.",
    "modeldesk_add_traffic_object_folder": "Replay risk: retrying may add a duplicate folder; inspect the catalog first.",
    "modeldesk_run_processing": "Replay risk: retrying runs processing again; inspect the active experiment and results first.",
    "modeldesk_execute_test": "Replay risk: retrying starts another test run; inspect the active test state and outputs first.",
    "modeldesk_start_maneuver": "Replay risk: retrying may start another runtime action; inspect current maneuver state first.",
}
_TOOL_FAILURE_CODES = get_args(ToolErrorCode)


# Examples are omitted only for installed test names, whose valid values are
# environment-specific; nullable references use null to show their safe omission.
_INPUT_FIELD_METADATA: dict[str, tuple[str, tuple[Any, ...] | None]] = {
    "candidateCapture": ("Candidate MAT capture file name in the active project's Measurements folder.", ("candidate.mat",)),
    "catalogPath": ("Optional Traffic Object Manager catalog path; use a value returned by catalog listing, or null to leave it unchanged.", (None,)),
    "connectionPoint": ("Road endpoint to disconnect: Start or End.", ("End",)),
    "d": ("Lateral road-relative traffic-object offset in meters.", (-1.75,)),
    "download": ("Whether to download the active experiment after the requested changes; false avoids runtime synchronization.", (False,)),
    "downloadIfNotRunning": ("Whether to download the active experiment before starting a maneuver when it is not running.", (True,)),
    "dryRun": ("Preview the target and intended effect without applying a mutation.", (False,)),
    "elementIndex": ("Zero-based vehicle-object type index returned by the type-list tool.", (0,)),
    "fellowSelectorKind": ("Optional fellow selector kind; active identifies the ego, otherwise use index or name.", ("active",)),
    "fellowSelectorValue": ("Value paired with the fellow selector; use active for the ego or a listed index/name value.", ("active",)),
    "fileName": ("Absolute destination path for the saved Road Network; the path must end in .rd.", ("C:/ModelDesk/Projects/Vehicle/Roads/City.rd",)),
    "fileType": ("Project-pool content type ID: 0 RoadNetwork, 1 TrafficScenario, 2 TestingTest, 3 LayoutConfiguration, 4 TrafficDriver.", ("0",)),
    "group": ("Environment Pool group to inspect: Objects, Road, Scenario, or TrafficDriver.", ("Road",)),
    "initialExperiment": ("Optional experiment name to activate after opening the project.", ("Baseline",)),
    "initializationCommand": ("Optional model initialization command passed to SetActiveModel.", ("initialize_vehicle",)),
    "insertAfterSegmentIndex": ("Zero-based segment index to insert after; -1 retains the tool's default placement behavior.", (-1,)),
    "laneMappingJson": ("JSON array of lane indices for the road traffic object.", ("[1]",)),
    "laneSectionIndex": ("Zero-based lane-section index in the selected road.", (0,)),
    "laneSectionLength": ("Requested lane-section length in meters; 0.0 selects the operation's automatic length behavior.", (0.0,)),
    "laneWidth": ("Lane width in meters.", (3.5,)),
    "lateralProfileJson": ("JSON object of COM-defined lateral assignments; {} requests no lateral changes because this interface has no universal lateral schema.", ("{}",)),
    "leftLaneCount": ("Number of left-side lanes to configure.", (1,)),
    "length": ("Road or segment length in meters, as supported by the selected operation.", (100.0,)),
    "logicalTestCaseSelectorKind": ("Selector kind for the logical test case: index or name.", ("index",)),
    "logicalTestCaseSelectorValue": ("Value paired with logicalTestCaseSelectorKind; use a decimal string for an index.", ("0",)),
    "longitudinalProfileJson": ("Ego-only initial properties: StartPosition (Start position on route, meters) and InitialLongitudinalVelocity (km/h). Fellows require explicit Position.YawAngleConstant.Constant or Velocity.Constant.Constant behavior-profile JSON; these are not aliases for ego initial properties.", ('{"StartPosition":70.0,"InitialLongitudinalVelocity":20.0}', '{"Position":{"YawAngleConstant":{"Constant":70.0}}}', '{"Velocity":{"Constant":{"Constant":20.0}}}')),
    "maneuverIndex": ("Zero-based ego maneuver index used to read or set its vehicle object type.", (0,)),
    "maneuverSelectorKind": ("Selector kind for a maneuver in the selected scope; use index or name.", ("index",)),
    "maneuverSelectorValue": ("Value paired with maneuverSelectorKind; use a decimal string for an index.", ("0",)),
    "maneuverSelectorsJson": ("JSON array of maneuver selectors. The current interface can confirm an existing order but cannot change it.", ('[{"selectorKind":"index","selectorValue":"0"}]',)),
    "mlWorkingDirectory": ("Optional MATLAB working directory for the active model.", ("C:/models/work",)),
    "mode": ("Road connection mode: Move or Modify.", ("Move",)),
    "modelFilePath": ("Path to the model file to bind to the active experiment.", ("C:/models/vehicle.slx",)),
    "name": ("Name to create or assign to the ModelDesk item; uniqueness and accepted characters are domain-specific.", ("Road",)),
    "object3D": ("Traffic Object Manager 3D asset reference; empty is accepted for no 3D object.", ("Cube.obj",)),
    "objectIndex": ("Zero-based road traffic-object index.", (0,)),
    "offset": ("Zero-based item offset for paginated list results; page size is bounded by the configured collection limit.", (0,)),
    "overwriteExisting": ("Whether an existing project-pool file may be overwritten.", (False,)),
    "parameterPath": ("Exact parameter path in the active parameter set.", ("Vehicle.Speed",)),
    "platformName": ("Optional model platform name passed to SetActiveModel.", ("ASM",)),
    "projectFile": ("Path to the ModelDesk project file (.prj) to open.", ("C:/ModelDesk/Projects/Vehicle/Vehicle.prj",)),
    "propertiesJson": ("JSON object of tool-specific property changes; accepted names and values belong to the selected COM object. {} means no property assignments.", ("{}",)),
    "recursive": ("Whether to include descendant items when listing an Environment Pool group.", (True,)),
    "referenceCapture": ("Reference MAT capture file name in the active project's Measurements folder.", ("reference.mat",)),
    "rightLaneCount": ("Number of right-side lanes to configure.", (1,)),
    "roadName": ("Name of the Road Network road to assign to the active scenario.", ("Road",)),
    "roadSelectorKind": ("Selector kind for a road in the active network; use index or name.", ("index",)),
    "roadSelectorValue": ("Value paired with roadSelectorKind; use a decimal string for an index.", ("0",)),
    "s": ("Longitudinal road-relative traffic-object position in meters.", (25.0,)),
    "save": ("Whether to save the affected experiment after the requested changes; false avoids persistence.", (False,)),
    "saveActive": ("Whether to save the currently active project or experiment before switching context.", (True,)),
    "scenario": ("Optional installation-specific AURELION scenario routing value; null leaves selection to the connector.", (None,)),
    "scenarioName": ("Exact scenario name to activate in the active experiment.", ("CutIn",)),
    "scope": ("Test execution scope; test runs the complete active test configuration.", ("test",)),
    "segmentIndex": ("Zero-based segment index on the selected road.", (0,)),
    "segmentType": ("Road segment type: Straight, Circular, Clothoid, or Spline.", ("Straight",)),
    "selectorKind": ("Selector kind for the target collection; use index or name where supported.", ("index",)),
    "selectorValue": ("Value paired with selectorKind; use a decimal string for an index.", ("0",)),
    "signalSpecsJson": ("JSON array of signal names or reference/candidate name objects; [] selects all common signal names.", ("[]",)),
    "sourcePoint": ("Source road endpoint to connect: Start or End.", ("End",)),
    "sourceRoadSelectorKind": ("Selector kind for the source road; use index or name.", ("index",)),
    "sourceRoadSelectorValue": ("Value paired with sourceRoadSelectorKind; use a decimal string for an index.", ("0",)),
    "system": ("Optional installation-specific AURELION system routing value; null leaves selection to the connector.", (None,)),
    "targetPoint": ("Target road endpoint to connect: Start or End.", ("Start",)),
    "targetRoadSelectorKind": ("Selector kind for the target road; use index or name.", ("index",)),
    "targetRoadSelectorValue": ("Value paired with targetRoadSelectorKind; use a decimal string for an index.", ("1",)),
    "testName": ("Exact name of a test configuration available in the installed ModelDesk project.", None),
    "tolerancesJson": ("JSON object of non-negative comparison thresholds, optionally keyed by signal.", ('{"rootMeanSquaredError":0.1}',)),
    "trafficDriverReference": ("Optional installed traffic-driver reference; use a reference returned by the active scenario tools, or null to leave it unchanged.", (None,)),
    "trafficObjectCatalogPath": ("Optional installed Traffic Object Manager catalog path for the scenario participant, or null to omit the reference.", (None,)),
    "trafficObjectSelectorKind": ("Optional traffic-object selector kind; use index or name when selecting a listed catalog object.", ("index",)),
    "trafficObjectSelectorValue": ("Value paired with trafficObjectSelectorKind; use a decimal string for an index.", ("0",)),
    "trafficObjectsJson": ("JSON array of traffic objects for basic-road creation, with road-relative s and d coordinates in meters.", ('[{"s":25.0,"d":-1.75}]',)),
    "useCase": ("Use-case identifier to resolve, such as UC2 or UC3.", ("UC3",)),
    "value": ("Scalar value expressed as invariant-culture text for the active parameter.", ("1200.0",)),
    "valueJson": ("JSON value whose shape is selected by valueKind; this example is a scalar number.", ("1200.0",)),
    "valueKind": ("Typed parameter shape: Scalar, Text, Vector, Matrix, or Table.", ("Scalar",)),
    "workflowName": ("Exact workflow recipe name returned by workflow discovery.", ("create_basic_traffic_scenario",)),
}


def _documented_tool_registrar(mcp: Any) -> Any:
    """Apply SDK-supported field/output annotations before registering each handler."""

    class DocumentedToolRegistrar:
        def tool(self, name: str) -> Any:
            sdk_decorator = mcp.tool(
                name=name,
                annotations=ToolAnnotations(
                    read_only_hint=True if name in _READ_ONLY_TOOL_NAMES else None,
                    destructive_hint=False if name in _ADDITIVE_TOOL_NAMES else None,
                    idempotent_hint=True if name in _READ_ONLY_TOOL_NAMES else None,
                    open_world_hint=name in _OPEN_WORLD_TOOL_NAMES,
                ),
            )

            def decorate(function: Any) -> Any:
                function.__doc__ = _document_tool_description(name, function.__doc__)
                annotations = get_type_hints(function, include_extras=True)
                for parameter_name in tuple(key for key in annotations if key != "return"):
                    if parameter_name not in _INPUT_FIELD_METADATA:
                        raise ValueError(f"Missing input schema metadata for {name}.{parameter_name}.")
                    description, examples = _INPUT_FIELD_METADATA[parameter_name]
                    field_metadata: dict[str, Any] = {"description": description}
                    if examples is not None:
                        field_metadata["examples"] = list(examples)
                    annotations[parameter_name] = Annotated[
                        annotations[parameter_name],
                        Field(**field_metadata),
                    ]
                annotations["return"] = _tool_result_envelope_for(name)
                function.__annotations__ = annotations
                return sdk_decorator(function)

            return decorate

    return DocumentedToolRegistrar()


def _document_tool_description(name: str, description: str | None) -> str:
    purpose = (description or "").strip()
    if name in _TOOLS_WITHOUT_COM_PRECONDITIONS:
        preconditions = "The requested workflow or use case must be registered; no active ModelDesk context is required."
    else:
        preconditions = "ModelDesk COM must be registered; any active project, experiment, and domain required by this operation must be available."
    clauses = [
        purpose,
        f"Preconditions: {preconditions}",
        f"Possible failure codes: {', '.join(_TOOL_FAILURE_CODES)}.",
    ]
    replay_risk = _REPLAY_RISK_NOTES.get(name)
    if replay_risk is not None:
        clauses.append(replay_risk)
    return "\n\n".join(clauses)


def _tool_domain_for_name(tool_name: str) -> str:
    """Assign each registered name to exactly one documented domain."""

    if (
        "_scenario_" in tool_name
        or tool_name.endswith("_scenario")
        or "maneuver" in tool_name
        or tool_name == "modeldesk_list_fellow_activities"
    ):
        return "Scenario/TrafficScenario"
    if "_traffic_object" in tool_name or "_vehicle_object" in tool_name:
        return "TrafficObjectManager/TrafficObject/TOM"
    if "_road" in tool_name:
        return "Road/RoadGenerator"
    if "_plot" in tool_name or "_capture" in tool_name:
        return "Plotting/PlotManager"
    return "General COM Automation"


TOOL_DOMAIN_BY_NAME = {name: _tool_domain_for_name(name) for name in EXPECTED_TOOL_NAMES}


def register_tools(mcp: Any, service: ModelDeskService) -> None:
    """Register the public tools with documented input and stable result schemas."""

    if mcp is None:
        raise ValueError("mcp must not be None")
    if service is None:
        raise ValueError("service must not be None")
    mcp = _documented_tool_registrar(mcp)

    @mcp.tool(name="modeldesk_get_status")
    def modeldesk_get_status() -> dict[str, Any]:
        """Read server + context status; call first when active project/experiment state is unknown."""

        return _to_dict(service.get_status())

    @mcp.tool(name="modeldesk_get_capabilities")
    def modeldesk_get_capabilities() -> dict[str, Any]:
        """Read capability flags before workflows; use to avoid calling unsupported domains."""

        return _to_dict(service.get_capabilities())

    @mcp.tool(name="modeldesk_open_project")
    def modeldesk_open_project(projectFile: str, initialExperiment: str | None = None, saveActive: bool = True) -> dict[str, Any]:
        """Open a project file and optionally activate an initial experiment before project-scoped calls."""

        return _to_dict(service.open_project(projectFile, initialExperiment, saveActive))

    @mcp.tool(name="modeldesk_create_project_pool_file")
    def modeldesk_create_project_pool_file(fileType: str, name: str, overwriteExisting: bool = False) -> dict[str, Any]:
        """Create a generic project-pool file via CreateFile(Type, Name, OverwriteExisting)."""

        return _to_dict(service.create_project_pool_file(fileType, name, overwriteExisting))

    @mcp.tool(name="modeldesk_create_road_network")
    def modeldesk_create_road_network(name: str, overwriteExisting: bool = False) -> dict[str, Any]:
        """Create a Road Network (.rd) pool file; preferred over generic CreateFile for type 0."""

        return _to_dict(service.create_road_network(name, overwriteExisting))

    @mcp.tool(name="modeldesk_create_traffic_scenario")
    def modeldesk_create_traffic_scenario(name: str, overwriteExisting: bool = False) -> dict[str, Any]:
        """Create a Traffic Scenario (.xml) pool file; preferred over generic CreateFile for type 1."""

        return _to_dict(service.create_traffic_scenario(name, overwriteExisting))

    @mcp.tool(name="modeldesk_list_environment_pool_items")
    def modeldesk_list_environment_pool_items(group: str, recursive: bool = True, offset: int = 0) -> dict[str, Any]:
        """Read-only list of Environment Pool items for the selected group."""

        return _to_dict(service.list_environment_pool_items(group, recursive, offset))

    @mcp.tool(name="modeldesk_save_project")
    def modeldesk_save_project() -> dict[str, Any]:
        """Persist active project changes to disk."""

        return _to_dict(service.save_project())

    @mcp.tool(name="modeldesk_close_project")
    def modeldesk_close_project(save: bool = True, dryRun: bool = False) -> dict[str, Any]:
        """Close active project, optionally saving first; dry-run previews without closing."""

        return _to_dict(service.close_project(save, dryRun))

    @mcp.tool(name="modeldesk_list_experiments")
    def modeldesk_list_experiments(offset: int = 0) -> dict[str, Any]:
        """List experiments in the active project; usually followed by experiment activation."""

        return _to_dict(service.list_experiments(offset))

    @mcp.tool(name="modeldesk_activate_experiment")
    def modeldesk_activate_experiment(selectorKind: str, selectorValue: str, saveActive: bool = True) -> dict[str, Any]:
        """Activate an experiment by selector; required before parameter-set, processing, and runtime tools."""

        return _to_dict(service.activate_experiment(selectorKind, selectorValue, saveActive))

    @mcp.tool(name="modeldesk_save_active_experiment")
    def modeldesk_save_active_experiment() -> dict[str, Any]:
        """Persist active experiment state after mutations."""

        return _to_dict(service.save_active_experiment())

    @mcp.tool(name="modeldesk_download_active_experiment")
    def modeldesk_download_active_experiment() -> dict[str, Any]:
        """Download active experiment to runtime before execution-dependent operations."""

        return _to_dict(service.download_active_experiment())

    @mcp.tool(name="modeldesk_list_parameter_sets")
    def modeldesk_list_parameter_sets(offset: int = 0) -> dict[str, Any]:
        """List parameter sets in active experiment; usually followed by parameter-set activation."""

        return _to_dict(service.list_parameter_sets(offset))

    @mcp.tool(name="modeldesk_activate_parameter_set")
    def modeldesk_activate_parameter_set(selectorKind: str, selectorValue: str, saveActive: bool = True) -> dict[str, Any]:
        """Activate parameter set by selector before reading/writing parameter values or running processing."""

        return _to_dict(service.activate_parameter_set(selectorKind, selectorValue, saveActive))

    @mcp.tool(name="modeldesk_get_parameterization_summary")
    def modeldesk_get_parameterization_summary() -> dict[str, Any]:
        """Read active parameterization context (experiment, model, parameter set) for validation and reporting."""

        return _to_dict(service.get_parameterization_summary())

    @mcp.tool(name="modeldesk_get_active_model_info")
    def modeldesk_get_active_model_info() -> dict[str, Any]:
        """Read current active-model binding for the active experiment."""

        return _to_dict(service.get_active_model_info())

    @mcp.tool(name="modeldesk_set_active_model")
    def modeldesk_set_active_model(modelFilePath: str, mlWorkingDirectory: str | None = None, initializationCommand: str | None = None, platformName: str | None = None) -> dict[str, Any]:
        """Set active model binding (and optional ML metadata) for the active experiment."""

        return _to_dict(service.set_active_model(modelFilePath, mlWorkingDirectory, initializationCommand, platformName))

    @mcp.tool(name="modeldesk_get_parameter_value")
    def modeldesk_get_parameter_value(parameterPath: str) -> dict[str, Any]:
        """Read one parameter by exact path from the active parameter set."""

        return _to_dict(service.get_parameter_value(parameterPath))

    @mcp.tool(name="modeldesk_set_scalar_parameter")
    def modeldesk_set_scalar_parameter(parameterPath: str, value: str) -> dict[str, Any]:
        """Set a single scalar parameter value in the active parameter set."""

        return _to_dict(service.set_scalar_parameter(parameterPath, value))

    @mcp.tool(name="modeldesk_set_parameter_value")
    def modeldesk_set_parameter_value(parameterPath: str, valueKind: str, valueJson: str) -> dict[str, Any]:
        """Set typed parameter value (`scalar|text|vector|matrix|table`) from JSON payload."""

        return _to_dict(service.set_parameter_value(parameterPath, valueKind, valueJson))

    @mcp.tool(name="modeldesk_get_road_summary")
    def modeldesk_get_road_summary() -> dict[str, Any]:
        """Read active road-domain context before road-network mutations."""

        return _to_dict(service.get_road_summary())

    @mcp.tool(name="modeldesk_activate_road")
    def modeldesk_activate_road(selectorKind: str, selectorValue: str) -> dict[str, Any]:
        """Activate road/road-network target by selector before road operations."""

        return _to_dict(service.activate_road(selectorKind, selectorValue))

    @mcp.tool(name="modeldesk_list_roads")
    def modeldesk_list_roads(offset: int = 0) -> dict[str, Any]:
        """List roads in the active road network to resolve safe selectors for update/remove/connect."""

        return _to_dict(service.list_roads(offset))

    @mcp.tool(name="modeldesk_save_road_network_as")
    def modeldesk_save_road_network_as(fileName: str, overwriteExisting: bool = False) -> dict[str, Any]:
        """Save active road network to an absolute `.rd` path."""

        return _to_dict(service.save_road_network_as(fileName, overwriteExisting))

    @mcp.tool(name="modeldesk_add_road")
    def modeldesk_add_road(name: str | None = None, leftLaneCount: int = 1, rightLaneCount: int = 1, laneWidth: float = 3.5, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Add a road and initialize first lane section; `save`/`download` should stay false unless explicitly requested."""

        return _to_dict(service.add_road(name, leftLaneCount, rightLaneCount, laneWidth, save, download))

    @mcp.tool(name="modeldesk_update_road")
    def modeldesk_update_road(roadSelectorKind: str = "index", roadSelectorValue: str = "0", name: str | None = None, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Update selected road properties (currently name); resolve selector from list output first."""

        return _to_dict(service.update_road(roadSelectorKind, roadSelectorValue, name, save, download))

    @mcp.tool(name="modeldesk_remove_road")
    def modeldesk_remove_road(roadSelectorKind: str = "index", roadSelectorValue: str = "0", save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Remove selected road from active network; verify selector to avoid accidental deletion."""

        return _to_dict(service.remove_road(roadSelectorKind, roadSelectorValue, save, download, dryRun))

    @mcp.tool(name="modeldesk_add_road_segment")
    def modeldesk_add_road_segment(roadSelectorKind: str = "index", roadSelectorValue: str = "0", segmentType: str = "Straight", propertiesJson: str = "{}", insertAfterSegmentIndex: int = -1, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Add typed segment (`Straight|Circular|Clothoid|Spline`) to selected road using `propertiesJson`."""

        return _to_dict(service.add_road_segment(roadSelectorKind, roadSelectorValue, segmentType, propertiesJson, insertAfterSegmentIndex, save, download))

    @mcp.tool(name="modeldesk_update_road_segment")
    def modeldesk_update_road_segment(roadSelectorKind: str = "index", roadSelectorValue: str = "0", segmentIndex: int = 0, segmentType: str | None = None, propertiesJson: str = "{}", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Update segment type and/or properties by `segmentIndex` on selected road."""

        return _to_dict(service.update_road_segment(roadSelectorKind, roadSelectorValue, segmentIndex, segmentType, propertiesJson, save, download))

    @mcp.tool(name="modeldesk_remove_road_segment")
    def modeldesk_remove_road_segment(roadSelectorKind: str = "index", roadSelectorValue: str = "0", segmentIndex: int = 0, save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Remove one road segment by index from selected road."""

        return _to_dict(service.remove_road_segment(roadSelectorKind, roadSelectorValue, segmentIndex, save, download, dryRun))

    @mcp.tool(name="modeldesk_configure_road_lanes")
    def modeldesk_configure_road_lanes(roadSelectorKind: str = "index", roadSelectorValue: str = "0", laneSectionIndex: int = 0, leftLaneCount: int = 1, rightLaneCount: int = 1, laneWidth: float = 3.5, laneSectionLength: float = 0.0, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Configure lane counts/width (and optional length) for selected lane section."""

        return _to_dict(service.configure_road_lanes(roadSelectorKind, roadSelectorValue, laneSectionIndex, leftLaneCount, rightLaneCount, laneWidth, laneSectionLength, save, download))

    @mcp.tool(name="modeldesk_add_road_object")
    def modeldesk_add_road_object(roadSelectorKind: str = "index", roadSelectorValue: str = "0", s: float = 0.0, d: float = 0.0, name: str | None = None, catalogPath: str | None = None, laneMappingJson: str = "[]", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Add road-local traffic object at road-relative (`s`,`d`) with optional catalog/lane mapping."""

        return _to_dict(service.add_road_object(roadSelectorKind, roadSelectorValue, s, d, name, catalogPath, laneMappingJson, save, download))

    @mcp.tool(name="modeldesk_update_road_object")
    def modeldesk_update_road_object(roadSelectorKind: str = "index", roadSelectorValue: str = "0", objectIndex: int = 0, propertiesJson: str = "{}", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Update selected road-object fields using `propertiesJson` patch semantics."""

        return _to_dict(service.update_road_object(roadSelectorKind, roadSelectorValue, objectIndex, propertiesJson, save, download))

    @mcp.tool(name="modeldesk_remove_road_object")
    def modeldesk_remove_road_object(roadSelectorKind: str = "index", roadSelectorValue: str = "0", objectIndex: int = 0, save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Remove one road-local object by index from selected road."""

        return _to_dict(service.remove_road_object(roadSelectorKind, roadSelectorValue, objectIndex, save, download, dryRun))

    @mcp.tool(name="modeldesk_connect_roads")
    def modeldesk_connect_roads(sourceRoadSelectorKind: str = "index", sourceRoadSelectorValue: str = "0", sourcePoint: str = "End", targetRoadSelectorKind: str = "index", targetRoadSelectorValue: str = "1", targetPoint: str = "Start", mode: str = "Move", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Connect source/target road endpoints; `mode` controls geometry adaptation (`Move` or `Modify`)."""

        return _to_dict(service.connect_roads(sourceRoadSelectorKind, sourceRoadSelectorValue, sourcePoint, targetRoadSelectorKind, targetRoadSelectorValue, targetPoint, mode, save, download))

    @mcp.tool(name="modeldesk_disconnect_road")
    def modeldesk_disconnect_road(roadSelectorKind: str = "index", roadSelectorValue: str = "0", connectionPoint: str = "End", save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Disconnect selected road connection point (`Start` or `End`)."""

        return _to_dict(service.disconnect_road(roadSelectorKind, roadSelectorValue, connectionPoint, save, download, dryRun))

    @mcp.tool(name="modeldesk_create_basic_road")
    def modeldesk_create_basic_road(name: str, length: float, leftLaneCount: int, rightLaneCount: int, laneWidth: float = 3.5, trafficObjectsJson: str = "[]", save: bool = False, download: bool = False) -> dict[str, Any]:
        """High-level helper: create straight road with lanes and optional traffic objects in one call."""

        return _to_dict(service.create_basic_road(name, length, leftLaneCount, rightLaneCount, laneWidth, trafficObjectsJson, save, download))

    @mcp.tool(name="modeldesk_get_scenario_summary")
    def modeldesk_get_scenario_summary() -> dict[str, Any]:
        """Read active scenario context before fellow/maneuver mutations."""

        return _to_dict(service.get_scenario_summary())

    @mcp.tool(name="modeldesk_activate_scenario")
    def modeldesk_activate_scenario(scenarioName: str) -> dict[str, Any]:
        """Activate scenario by name before scenario-scoped read/write tools."""

        return _to_dict(service.activate_scenario(scenarioName))

    @mcp.tool(name="modeldesk_list_scenario_fellows")
    def modeldesk_list_scenario_fellows(offset: int = 0) -> dict[str, Any]:
        """List fellows/participants and selectors for follow-up update/remove/maneuver calls."""

        return _to_dict(service.list_scenario_fellows(offset))

    @mcp.tool(name="modeldesk_list_scenario_maneuvers")
    def modeldesk_list_scenario_maneuvers(offset: int = 0) -> dict[str, Any]:
        """List maneuvers in active scenario to resolve selectors and indices for edits."""

        return _to_dict(service.list_scenario_maneuvers(offset))

    @mcp.tool(name="modeldesk_add_scenario_fellow")
    def modeldesk_add_scenario_fellow(name: str | None = None, propertiesJson: str = "{}", trafficObjectSelectorKind: str | None = None, trafficObjectSelectorValue: str | None = None, trafficObjectCatalogPath: str | None = None, trafficDriverReference: str | None = None, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Add fellow/participant with optional properties, traffic-object reference, and driver reference."""

        return _to_dict(service.add_scenario_fellow(name, propertiesJson, trafficObjectSelectorKind, trafficObjectSelectorValue, trafficObjectCatalogPath, trafficDriverReference, save, download))

    @mcp.tool(name="modeldesk_update_scenario_fellow")
    def modeldesk_update_scenario_fellow(fellowSelectorKind: str = "index", fellowSelectorValue: str = "0", name: str | None = None, propertiesJson: str = "{}", trafficObjectSelectorKind: str | None = None, trafficObjectSelectorValue: str | None = None, trafficObjectCatalogPath: str | None = None, trafficDriverReference: str | None = None, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Update selected fellow fields/references; prefer list -> select -> update flow."""

        return _to_dict(service.update_scenario_fellow(fellowSelectorKind, fellowSelectorValue, name, propertiesJson, trafficObjectSelectorKind, trafficObjectSelectorValue, trafficObjectCatalogPath, trafficDriverReference, save, download))

    @mcp.tool(name="modeldesk_remove_scenario_fellow")
    def modeldesk_remove_scenario_fellow(fellowSelectorKind: str = "index", fellowSelectorValue: str = "0", save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Remove selected fellow from active scenario."""

        return _to_dict(service.remove_scenario_fellow(fellowSelectorKind, fellowSelectorValue, save, download, dryRun))

    @mcp.tool(name="modeldesk_add_scenario_maneuver")
    def modeldesk_add_scenario_maneuver(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, propertiesJson: str = "{}", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Add maneuver to active scenario scope (ego) or selected fellow scope."""

        return _to_dict(service.add_scenario_maneuver(fellowSelectorKind, fellowSelectorValue, propertiesJson, save, download))

    @mcp.tool(name="modeldesk_update_scenario_maneuver")
    def modeldesk_update_scenario_maneuver(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverSelectorKind: str = "index", maneuverSelectorValue: str = "0", propertiesJson: str = "{}", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Update selected maneuver using `propertiesJson` on ego or fellow scope."""

        return _to_dict(service.update_scenario_maneuver(fellowSelectorKind, fellowSelectorValue, maneuverSelectorKind, maneuverSelectorValue, propertiesJson, save, download))

    @mcp.tool(name="modeldesk_remove_scenario_maneuver")
    def modeldesk_remove_scenario_maneuver(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverSelectorKind: str = "index", maneuverSelectorValue: str = "0", save: bool = False, download: bool = False, dryRun: bool = False) -> dict[str, Any]:
        """Remove selected maneuver from ego or selected fellow scope."""

        return _to_dict(service.remove_scenario_maneuver(fellowSelectorKind, fellowSelectorValue, maneuverSelectorKind, maneuverSelectorValue, save, download, dryRun))

    @mcp.tool(name="modeldesk_set_scenario_maneuver_sequence")
    def modeldesk_set_scenario_maneuver_sequence(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverSelectorsJson: str = "[]", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Set maneuver execution order using selector array JSON for ego or fellow scope."""

        return _to_dict(service.set_scenario_maneuver_sequence(fellowSelectorKind, fellowSelectorValue, maneuverSelectorsJson, save, download))

    @mcp.tool(name="modeldesk_set_maneuver_behavior_profiles")
    def modeldesk_set_maneuver_behavior_profiles(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverSelectorKind: str = "index", maneuverSelectorValue: str = "0", longitudinalProfileJson: str = "{}", lateralProfileJson: str = "{}", save: bool = False, download: bool = False) -> dict[str, Any]:
        """Apply and read back maneuver values. Only the ego (active) supports StartPosition (Start position on route, m) and InitialLongitudinalVelocity (km/h). Fellows do not have these initial properties; their JSON must explicitly select {"Position":{"YawAngleConstant":{"Constant":70.0}}} or {"Velocity":{"Constant":{"Constant":20.0}}} on the first segment. These are mutually exclusive behavior profiles, not ego initial fields. Fellow creation requires no yaw or profile values. Verify longitudinalPosition or longitudinalVelocity before persistence."""

        return _to_dict(service.set_maneuver_behavior_profiles(fellowSelectorKind, fellowSelectorValue, maneuverSelectorKind, maneuverSelectorValue, longitudinalProfileJson, lateralProfileJson, save, download))

    @mcp.tool(name="modeldesk_get_scenario_road")
    def modeldesk_get_scenario_road() -> dict[str, Any]:
        """Read currently referenced road for the active scenario."""

        return _to_dict(service.get_scenario_road())

    @mcp.tool(name="modeldesk_set_scenario_road")
    def modeldesk_set_scenario_road(roadName: str, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Set scenario road reference by road name after validating available roads."""

        return _to_dict(service.set_scenario_road(roadName, save, download))

    @mcp.tool(name="modeldesk_list_fellow_activities")
    def modeldesk_list_fellow_activities(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, offset: int = 0) -> dict[str, Any]:
        """List activities for selected fellow or ego (`active` defaults) to discover maneuver targets."""

        kind = fellowSelectorKind if fellowSelectorKind is not None else "active"
        value = fellowSelectorValue if fellowSelectorValue is not None else "active"
        return _to_dict(service.list_fellow_activities(kind, value, offset))

    @mcp.tool(name="modeldesk_get_vehicle_object_type")
    def modeldesk_get_vehicle_object_type(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverIndex: int = 0) -> dict[str, Any]:
        """Read active 3D vehicle object type for selected fellow/ego maneuver index."""

        kind = fellowSelectorKind if fellowSelectorKind is not None else "active"
        value = fellowSelectorValue if fellowSelectorValue is not None else "active"
        return _to_dict(service.get_vehicle_object_type(kind, value, maneuverIndex))

    @mcp.tool(name="modeldesk_list_vehicle_object_types")
    def modeldesk_list_vehicle_object_types(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverIndex: int = 0, offset: int = 0) -> dict[str, Any]:
        """List selectable 3D vehicle object types for selected fellow/ego maneuver index."""

        kind = fellowSelectorKind if fellowSelectorKind is not None else "active"
        value = fellowSelectorValue if fellowSelectorValue is not None else "active"
        return _to_dict(service.list_vehicle_object_types(kind, value, maneuverIndex, offset))

    @mcp.tool(name="modeldesk_set_vehicle_object_type")
    def modeldesk_set_vehicle_object_type(fellowSelectorKind: str | None = None, fellowSelectorValue: str | None = None, maneuverIndex: int = 0, elementIndex: int = 0, save: bool = False, download: bool = False) -> dict[str, Any]:
        """Activate 3D vehicle object type by `elementIndex` for selected fellow/ego maneuver index."""

        kind = fellowSelectorKind if fellowSelectorKind is not None else "active"
        value = fellowSelectorValue if fellowSelectorValue is not None else "active"
        return _to_dict(service.set_vehicle_object_type(kind, value, maneuverIndex, elementIndex, save, download))

    @mcp.tool(name="modeldesk_get_traffic_objects_summary")
    def modeldesk_get_traffic_objects_summary() -> dict[str, Any]:
        """Read traffic-object catalog summary before object/folder operations."""

        return _to_dict(service.get_traffic_objects_summary())

    @mcp.tool(name="modeldesk_list_traffic_objects")
    def modeldesk_list_traffic_objects(offset: int = 0) -> dict[str, Any]:
        """List reusable traffic objects and selectors from Traffic Object Manager."""

        return _to_dict(service.list_traffic_objects(offset))

    @mcp.tool(name="modeldesk_list_traffic_object_folders")
    def modeldesk_list_traffic_object_folders(offset: int = 0) -> dict[str, Any]:
        """List catalog folders from Traffic Object Manager for path/selector discovery."""

        return _to_dict(service.list_traffic_object_folders(offset))

    @mcp.tool(name="modeldesk_validate_traffic_object_reference")
    def modeldesk_validate_traffic_object_reference(selectorKind: str, selectorValue: str) -> dict[str, Any]:
        """Preflight check: validate traffic-object selector resolves before assignment to road/scenario."""

        return _to_dict(service.validate_traffic_object_reference(selectorKind, selectorValue))

    @mcp.tool(name="modeldesk_add_traffic_object")
    def modeldesk_add_traffic_object(name: str, object3D: str) -> dict[str, Any]:
        """Add traffic object entry to Traffic Object Manager (when capability is enabled)."""

        return _to_dict(service.add_traffic_object(name, object3D))

    @mcp.tool(name="modeldesk_remove_traffic_object")
    def modeldesk_remove_traffic_object(selectorKind: str, selectorValue: str, dryRun: bool = False) -> dict[str, Any]:
        """Remove traffic object by selector; verify target via listing first."""

        return _to_dict(service.remove_traffic_object(selectorKind, selectorValue, dryRun))

    @mcp.tool(name="modeldesk_add_traffic_object_folder")
    def modeldesk_add_traffic_object_folder(name: str) -> dict[str, Any]:
        """Add folder to Traffic Object Manager hierarchy."""

        return _to_dict(service.add_traffic_object_folder(name))

    @mcp.tool(name="modeldesk_remove_traffic_object_folder")
    def modeldesk_remove_traffic_object_folder(selectorKind: str, selectorValue: str, dryRun: bool = False) -> dict[str, Any]:
        """Remove traffic-object folder by selector; confirm exact folder before delete."""

        return _to_dict(service.remove_traffic_object_folder(selectorKind, selectorValue, dryRun))

    @mcp.tool(name="modeldesk_get_processing_summary")
    def modeldesk_get_processing_summary() -> dict[str, Any]:
        """Read processing readiness summary for the active parameter set."""

        return _to_dict(service.get_processing_summary())

    @mcp.tool(name="modeldesk_get_processing_configuration")
    def modeldesk_get_processing_configuration() -> dict[str, Any]:
        """Read detailed processing configuration for the active parameter set."""

        return _to_dict(service.get_processing_configuration())

    @mcp.tool(name="modeldesk_run_processing")
    def modeldesk_run_processing() -> dict[str, Any]:
        """Execute processing for active parameter set; requires active experiment and parameter set."""

        return _to_dict(service.run_processing())

    @mcp.tool(name="modeldesk_get_test_summary")
    def modeldesk_get_test_summary() -> dict[str, Any]:
        """Read active test configuration summary before test listing or execution."""

        return _to_dict(service.get_test_summary())

    @mcp.tool(name="modeldesk_activate_test")
    def modeldesk_activate_test(testName: str) -> dict[str, Any]:
        """Activate test configuration by name before listing/executing cases."""

        return _to_dict(service.activate_test(testName))

    @mcp.tool(name="modeldesk_list_logical_test_cases")
    def modeldesk_list_logical_test_cases(offset: int = 0) -> dict[str, Any]:
        """List logical test cases from active test configuration."""

        return _to_dict(service.list_logical_test_cases(offset))

    @mcp.tool(name="modeldesk_list_concrete_test_cases")
    def modeldesk_list_concrete_test_cases(logicalTestCaseSelectorKind: str = "index", logicalTestCaseSelectorValue: str = "0", offset: int = 0) -> dict[str, Any]:
        """List concrete test cases for one logical test case (defaults to index 0) of the active test configuration."""

        return _to_dict(service.list_concrete_test_cases(logicalTestCaseSelectorKind, logicalTestCaseSelectorValue, offset))

    @mcp.tool(name="modeldesk_execute_test")
    def modeldesk_execute_test(scope: str = "test", selectorKind: str | None = None, selectorValue: str | None = None) -> dict[str, Any]:
        """Execute full active test or selected logical case based on `scope` and selector arguments."""

        return _to_dict(service.execute_test(scope, selectorKind, selectorValue))

    @mcp.tool(name="modeldesk_get_plotting_summary")
    def modeldesk_get_plotting_summary() -> dict[str, Any]:
        """Read plotting activation state and available captures/layouts."""

        return _to_dict(service.get_plotting_summary())

    @mcp.tool(name="modeldesk_activate_plotting")
    def modeldesk_activate_plotting(selectorKind: str, selectorValue: str) -> dict[str, Any]:
        """Activate plotting configuration by selector before capture/layout listing."""

        return _to_dict(service.activate_plotting(selectorKind, selectorValue))

    @mcp.tool(name="modeldesk_list_plot_captures")
    def modeldesk_list_plot_captures(offset: int = 0) -> dict[str, Any]:
        """List captures in active plotting configuration."""

        return _to_dict(service.list_plot_captures(offset))

    @mcp.tool(name="modeldesk_list_plot_layouts")
    def modeldesk_list_plot_layouts(offset: int = 0) -> dict[str, Any]:
        """List plot layouts in active plotting configuration."""

        return _to_dict(service.list_plot_layouts(offset))

    @mcp.tool(name="modeldesk_compare_captures")
    def modeldesk_compare_captures(referenceCapture: str, candidateCapture: str, signalSpecsJson: str, tolerancesJson: str) -> dict[str, Any]:
        """Compare project-pool MATLAB captures with signal selection and numeric tolerances."""

        return _to_dict(service.compare_captures(referenceCapture, candidateCapture, signalSpecsJson, tolerancesJson))

    @mcp.tool(name="modeldesk_start_maneuver")
    def modeldesk_start_maneuver(downloadIfNotRunning: bool = True) -> dict[str, Any]:
        """Start maneuver execution; optionally download experiment first if runtime is not running."""

        return _to_dict(service.start_maneuver(downloadIfNotRunning))

    @mcp.tool(name="modeldesk_stop_maneuver")
    def modeldesk_stop_maneuver() -> dict[str, Any]:
        """Stop ongoing maneuver execution."""

        return _to_dict(service.stop_maneuver())

    @mcp.tool(name="modeldesk_reset_maneuver")
    def modeldesk_reset_maneuver() -> dict[str, Any]:
        """Reset maneuver execution state to initial condition."""

        return _to_dict(service.reset_maneuver())

    @mcp.tool(name="modeldesk_synchronize_aurelion")
    def modeldesk_synchronize_aurelion(system: str | None = None, scenario: str | None = None) -> dict[str, Any]:
        """Synchronize active scene to AURELION with optional system/scenario routing values."""

        return _to_dict(service.synchronize_aurelion(system, scenario))

    @mcp.tool(name="modeldesk_get_workflow_plan")
    def modeldesk_get_workflow_plan(workflowName: str) -> dict[str, Any]:
        """Return dry-run workflow recipe (ordered lower-level tool calls) for planning."""

        return _to_dict(service.get_workflow_plan(workflowName))

    @mcp.tool(name="modeldesk_list_tools_by_use_case")
    def modeldesk_list_tools_by_use_case(useCase: str) -> dict[str, Any]:
        """[Supporting] Resolve a use-case query ('3', 'UC3', 'Use Case 3') to its tagged MCP tool names."""

        return _to_dict(service.list_tools_by_use_case(useCase))


def _to_dict(result: ToolResult) -> dict[str, Any]:
    return result.to_dict()
