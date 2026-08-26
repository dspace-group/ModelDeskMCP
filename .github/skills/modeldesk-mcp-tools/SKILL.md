---
name: modeldesk-mcp-tools
description: Use when an agent operates the local ModelDesk MCP server to inspect context, plan workflows, author project assets, process experiments, run tests, or compare results with explicit user intent and structured recovery.
---

# ModelDesk MCP Tools

## When to use

Use this skill when an agent needs to operate the ModelDesk MCP server through its local stdio interface. It describes the safe order for discovery, selection, mutation, verification, persistence, execution, and cleanup. The server exposes tools only; it does not imply MCP resources, MCP prompts, dynamic discovery, or a graphical client.

## Preflight: status and capability

1. Read current server, project, experiment, and active-domain state before acting when context is unknown.
2. Read capability flags before a workflow that depends on an optional Automation domain. If a capability is unavailable, stop that branch and report the supported alternative instead of guessing.
3. For an end-to-end request, obtain the dry-run workflow plan first and use its ordered lower-level calls as the execution outline.
4. Re-check status after opening or closing a project, switching an experiment or active asset, and recovering from an error.

## Read before write

Treat every selector as scope-sensitive and potentially stale. Discover the current candidates with the relevant list or summary operation, choose from returned names/selectors, and validate references before assigning them. Before an update or removal, read the target and its parent scope; after a mutation, read the affected summary or list again to verify the result. Never manufacture a selector from memory or reuse a deep child object from an earlier call.

## Persistence and download defaults

Keep save and download controls disabled when the operation exposes them unless the user explicitly asks to persist or transfer state. Group related edits, verify the completed batch, then save once when requested. Do not infer permission to save, download, execute, synchronize, or overwrite from a read-only request. Confirm the target experiment and parameter set before any persistence or download action.

## Read-only and mutating boundaries

Read-only operations include status, capabilities, summaries, lists, current-value reads, reference validation, workflow planning, and comparison preparation. Context activation changes the active scope and should be treated as a state change even when it does not edit a file. Creation, updates, removals, project/experiment persistence, downloads, processing, test execution, maneuver start/stop/reset, and synchronization are mutating or externally visible actions; perform them only when the request authorizes that action and the preflight checks pass.

## Project-pool and environment lookup

Use the dedicated type-specific creator when one exists; use the generic project-pool creator only for an unsupported or less-specific type. The project-pool type mapping is:

| Type | Asset | Typical extension |
| --- | --- | --- |
| `0` | Road Network | `.rd` |
| `1` | Traffic Scenario | `.xml` |
| `2` | Testing Test | `.tst` |
| `3` | Simulation Configuration | `.xml` |
| `4` | Traffic Driver | `.trd` |

Resolve reusable environment assets through the read-only environment listing before assigning a road, scenario, traffic driver, or traffic object reference. Use the available group names `Objects`, `Road`, `Scenario`, and `Traffic Driver`; treat returned paths and selectors as data, not as values to invent.

## Five tool domains

The registry assigns every tool to exactly one of these domains:

- General COM Automation
- Scenario/TrafficScenario
- Road/RoadGenerator
- Plotting/PlotManager
- TrafficObjectManager/TrafficObject/TOM

Stay within the active domain implied by the request, and use the general domain for lifecycle, parameterization, processing, testing, and workflow planning operations that do not belong to a specialized domain.

## Workflow ordering

Use this general sequence unless the returned workflow plan gives a more specific order:

1. Inspect status and capabilities.
2. Open or confirm the project.
3. List and activate the experiment or project-pool asset.
4. Discover selectors and validate external references.
5. Apply the smallest authorized mutation batch.
6. Re-read summaries/lists and report the structured result.
7. Save or download only when explicitly requested.
8. Run processing, tests, plotting, or synchronization only after the active context is verified.
9. Close the project at session end, following the persistence instruction.

For common workflows, keep the domain order coherent: parameterize a vehicle variant before processing and saving its parameter set; create or activate a road before road authoring; create or activate a scenario before fellows and maneuvers; resolve traffic-object references before assigning them; activate plotting before listing captures or layouts; and prepare the active experiment before synchronization. Regression execution requires an activated test and an explicit scope.

## Structured results and recovery

Every call returns a structured `ToolResult`-shaped value. Check the success flag before using result data, and read the error code, safe message, and details when present. On a recoverable failure, do not repeat a mutating call blindly: refresh status, re-list the relevant scope, resolve the selector again, and retry only when the cause and user authorization remain clear. Treat validation failures, unavailable capabilities, missing active context, and timeouts as actionable results to report, not as permission to broaden scope. Do not expose local machine paths, COM exception internals, or secrets in an agent response.

## Timeouts

Keep every long-running operation within the configured timeout. Processing, test execution, downloads, synchronization, and maneuver control need bounded waits. On timeout, report the operation and current context, refresh status before deciding whether it completed, and avoid an automatic retry for an operation that may have reached the external system.

## Safe cleanup

Close the active project when the session is complete or before switching to another project. Save first only when explicitly requested or already authorized by the workflow. Do not remove temporary or project assets as an unrequested cleanup step. Leave the active system in a known state, and use stop or reset only when the user asked for it or the workflow explicitly requires it.

## Complete Tool Index

<!-- BEGIN TOOL INDEX -->

### General COM Automation

| Tool | Agent usage guidance |
| --- | --- |
| `modeldesk_get_status` | Read server + context status; call first when active project/experiment state is unknown. |
| `modeldesk_get_capabilities` | Read capability flags before workflows; use to avoid calling unsupported domains. |
| `modeldesk_open_project` | Open a project file and optionally activate an initial experiment before project-scoped calls. |
| `modeldesk_create_project_pool_file` | Create a generic project-pool file via CreateFile(Type, Name, OverwriteExisting). |
| `modeldesk_list_environment_pool_items` | Read-only list of Environment Pool items for the selected group. |
| `modeldesk_save_project` | Persist active project changes to disk. |
| `modeldesk_close_project` | Close active project, optionally saving first to prevent unsaved state loss. |
| `modeldesk_list_experiments` | List experiments in the active project; usually followed by experiment activation. |
| `modeldesk_activate_experiment` | Activate an experiment by selector; required before parameter-set, processing, and runtime tools. |
| `modeldesk_save_active_experiment` | Persist active experiment state after mutations. |
| `modeldesk_download_active_experiment` | Download active experiment to runtime before execution-dependent operations. |
| `modeldesk_list_parameter_sets` | List parameter sets in active experiment; usually followed by parameter-set activation. |
| `modeldesk_activate_parameter_set` | Activate parameter set by selector before reading/writing parameter values or running processing. |
| `modeldesk_get_parameterization_summary` | Read active parameterization context (experiment, model, parameter set) for validation and reporting. |
| `modeldesk_get_active_model_info` | Read current active-model binding for the active experiment. |
| `modeldesk_set_active_model` | Set active model binding (and optional ML metadata) for the active experiment. |
| `modeldesk_get_parameter_value` | Read one parameter by exact path from the active parameter set. |
| `modeldesk_set_scalar_parameter` | Set a single scalar parameter value in the active parameter set. |
| `modeldesk_set_parameter_value` | Set typed parameter value (`scalar\|text\|vector\|matrix\|table`) from JSON payload. |
| `modeldesk_get_processing_summary` | Read processing readiness summary for the active parameter set. |
| `modeldesk_get_processing_configuration` | Read detailed processing configuration for the active parameter set. |
| `modeldesk_run_processing` | Execute processing for active parameter set; requires active experiment and parameter set. |
| `modeldesk_get_test_summary` | Read active test configuration summary before test listing or execution. |
| `modeldesk_activate_test` | Activate test configuration by name before listing/executing cases. |
| `modeldesk_list_logical_test_cases` | List logical test cases from active test configuration. |
| `modeldesk_list_concrete_test_cases` | List concrete test cases from active test configuration. |
| `modeldesk_execute_test` | Execute full active test or selected logical case based on `scope` and selector arguments. |
| `modeldesk_synchronize_aurelion` | Synchronize active scene to AURELION with optional system/scenario routing values. |
| `modeldesk_get_workflow_plan` | Return dry-run workflow recipe (ordered lower-level tool calls) for planning. |
| `modeldesk_list_tools_by_use_case` | [Supporting] Resolve a use-case query ('3', 'UC3', 'Use Case 3') to its tagged MCP tool names. |

### Scenario/TrafficScenario

| Tool | Agent usage guidance |
| --- | --- |
| `modeldesk_create_traffic_scenario` | Create a Traffic Scenario (.xml) pool file; preferred over generic CreateFile for type 1. |
| `modeldesk_get_scenario_summary` | Read active scenario context before fellow/maneuver mutations. |
| `modeldesk_activate_scenario` | Activate scenario by name before scenario-scoped read/write tools. |
| `modeldesk_list_scenario_fellows` | List fellows/participants and selectors for follow-up update/remove/maneuver calls. |
| `modeldesk_list_scenario_maneuvers` | List maneuvers in active scenario to resolve selectors and indices for edits. |
| `modeldesk_add_scenario_fellow` | Add fellow/participant with optional properties, traffic-object reference, and driver reference. |
| `modeldesk_update_scenario_fellow` | Update selected fellow fields/references; prefer list -> select -> update flow. |
| `modeldesk_remove_scenario_fellow` | Remove selected fellow from active scenario. |
| `modeldesk_add_scenario_maneuver` | Add maneuver to active scenario scope (ego) or selected fellow scope. |
| `modeldesk_update_scenario_maneuver` | Update selected maneuver using `propertiesJson` on ego or fellow scope. |
| `modeldesk_remove_scenario_maneuver` | Remove selected maneuver from ego or selected fellow scope. |
| `modeldesk_set_scenario_maneuver_sequence` | Set maneuver execution order using selector array JSON for ego or fellow scope. |
| `modeldesk_set_maneuver_behavior_profiles` | Set longitudinal/lateral behavior profile JSON on selected maneuver. |
| `modeldesk_get_scenario_road` | Read currently referenced road for the active scenario. |
| `modeldesk_set_scenario_road` | Set scenario road reference by road name after validating available roads. |
| `modeldesk_list_fellow_activities` | List activities for selected fellow or ego (`active` defaults) to discover maneuver targets. |
| `modeldesk_start_maneuver` | Start maneuver execution; optionally download experiment first if runtime is not running. |
| `modeldesk_stop_maneuver` | Stop ongoing maneuver execution. |
| `modeldesk_reset_maneuver` | Reset maneuver execution state to initial condition. |

### Road/RoadGenerator

| Tool | Agent usage guidance |
| --- | --- |
| `modeldesk_create_road_network` | Create a Road Network (.rd) pool file; preferred over generic CreateFile for type 0. |
| `modeldesk_get_road_summary` | Read active road-domain context before road-network mutations. |
| `modeldesk_activate_road` | Activate road/road-network target by selector before road operations. |
| `modeldesk_list_roads` | List roads in the active road network to resolve safe selectors for update/remove/connect. |
| `modeldesk_save_road_network_as` | Save active road network to an absolute `.rd` path. |
| `modeldesk_add_road` | Add a road and initialize first lane section; `save`/`download` should stay false unless explicitly requested. |
| `modeldesk_update_road` | Update selected road properties (currently name); resolve selector from list output first. |
| `modeldesk_remove_road` | Remove selected road from active network; verify selector to avoid accidental deletion. |
| `modeldesk_add_road_segment` | Add typed segment (`Straight\|Circular\|Clothoid\|Spline`) to selected road using `propertiesJson`. |
| `modeldesk_update_road_segment` | Update segment type and/or properties by `segmentIndex` on selected road. |
| `modeldesk_remove_road_segment` | Remove one road segment by index from selected road. |
| `modeldesk_configure_road_lanes` | Configure lane counts/width (and optional length) for selected lane section. |
| `modeldesk_add_road_object` | Add road-local traffic object at road-relative (`s`,`d`) with optional catalog/lane mapping. |
| `modeldesk_update_road_object` | Update selected road-object fields using `propertiesJson` patch semantics. |
| `modeldesk_remove_road_object` | Remove one road-local object by index from selected road. |
| `modeldesk_connect_roads` | Connect source/target road endpoints; `mode` controls geometry adaptation (`Move` or `Modify`). |
| `modeldesk_disconnect_road` | Disconnect selected road connection point (`Start` or `End`). |
| `modeldesk_create_basic_road` | High-level helper: create straight road with lanes and optional traffic objects in one call. |

### Plotting/PlotManager

| Tool | Agent usage guidance |
| --- | --- |
| `modeldesk_get_plotting_summary` | Read plotting activation state and available captures/layouts. |
| `modeldesk_activate_plotting` | Activate plotting configuration by selector before capture/layout listing. |
| `modeldesk_list_plot_captures` | List captures in active plotting configuration. |
| `modeldesk_list_plot_layouts` | List plot layouts in active plotting configuration. |
| `modeldesk_compare_captures` | Compare two captures (currently capability placeholder until numeric backend is available). |

### TrafficObjectManager/TrafficObject/TOM

| Tool | Agent usage guidance |
| --- | --- |
| `modeldesk_get_vehicle_object_type` | Read active 3D vehicle object type for selected fellow/ego maneuver index. |
| `modeldesk_list_vehicle_object_types` | List selectable 3D vehicle object types for selected fellow/ego maneuver index. |
| `modeldesk_set_vehicle_object_type` | Activate 3D vehicle object type by `elementIndex` for selected fellow/ego maneuver index. |
| `modeldesk_get_traffic_objects_summary` | Read traffic-object catalog summary before object/folder operations. |
| `modeldesk_list_traffic_objects` | List reusable traffic objects and selectors from Traffic Object Manager. |
| `modeldesk_list_traffic_object_folders` | List catalog folders from Traffic Object Manager for path/selector discovery. |
| `modeldesk_validate_traffic_object_reference` | Preflight check: validate traffic-object selector resolves before assignment to road/scenario. |
| `modeldesk_add_traffic_object` | Add traffic object entry to Traffic Object Manager (when capability is enabled). |
| `modeldesk_remove_traffic_object` | Remove traffic object by selector; verify target via listing first. |
| `modeldesk_add_traffic_object_folder` | Add folder to Traffic Object Manager hierarchy. |
| `modeldesk_remove_traffic_object_folder` | Remove traffic-object folder by selector; confirm exact folder before delete. |

<!-- END TOOL INDEX -->
