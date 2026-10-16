# Tool Reference

[../README.md](../README.md) | [use-cases.md](use-cases.md) | [clients.md](clients.md)

The server exposes **83 tools**. Every registered name appears exactly once in the tables below, grouped by workflow rather than internal module ownership. Shared infrastructure includes project-pool tools and AURELION synchronization used across UC2 and UC3.

## Contents

| Group | Count | Purpose |
| --- | ---: | --- |
| [Shared Infrastructure](#shared-infrastructure) | 14 | Discovery, project context, pools, synchronization |
| [UC1: Vehicle Parameterization](#uc1-vehicle-parameterization) | 11 | Models, parameters, processing |
| [UC2: Roads](#uc2-roads) | 18 | Networks and road geometry |
| [UC3: Scenarios and Traffic](#uc3-scenarios-and-traffic) | 22 | Participants, maneuvers, behavior, execution |
| [UC4: Traffic Objects](#uc4-traffic-objects) | 8 | Reusable catalog assets |
| [UC5: Tests and Analysis](#uc5-tests-and-analysis) | 10 | Test configurations, plotting, capture comparison |
| **Total** | **83** | |

## Reading the Tables

| Effect | Meaning |
| --- | --- |
| Inspect | Read context, configuration, or collections; no requested domain mutation. |
| Plan | Return local tool discovery or a dry-run recipe; do not execute its steps. |
| Context | Switch the active object or model binding; some switches save by default. |
| Edit | Create, change, or remove domain content. |
| Persist | Save content or write a project-pool file to disk. |
| Runtime | Download, process, execute, reset, or synchronize runtime state. |
| Analyze | Read capture files and compute comparison results. |

Effects describe the principal operation, not a guarantee of availability or atomicity. Unless stated otherwise, domain tools require a live local ModelDesk context. The MCP input schema provides exact arguments, defaults, descriptions, and examples; the client-visible schema is authoritative for calling a tool.

Keep `save=false` and `download=false` on editing tools until persistence and runtime synchronization are intended. This still allows in-memory changes. `saveActive` and project-close `save` default to true; maneuver startup also defaults to downloading if runtime is not running. Execute dependent calls sequentially and inspect state again after an error.

The static MCP resource `modeldesk://workflow-catalog` lists all workflow names, ordered steps, required tools, and supported use-case identifiers. Read it before calling `modeldesk_get_workflow_plan` or `modeldesk_list_tools_by_use_case` when the exact name or identifier is unknown.

## Shared Infrastructure

**14 tools** for application context and cross-cutting workflows.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_get_status` | Inspect server session, ModelDesk reachability/version, and active project/experiment. | Inspect |
| `modeldesk_get_capabilities` | Inspect supported domains and installation-dependent capability flags. | Inspect |
| `modeldesk_open_project` | Open a project file, optionally selecting an initial experiment and saving the previous context. | Context |
| `modeldesk_create_project_pool_file` | Create a pool file by content-type ID; use the specialized road/scenario creators when applicable. | Persist |
| `modeldesk_list_environment_pool_items` | List a selected Environment Pool group, optionally including descendants. | Inspect |
| `modeldesk_save_project` | Save the active project. | Persist |
| `modeldesk_close_project` | Close the active project, saving first by default. | Context |
| `modeldesk_list_experiments` | List experiments available in the active project. | Inspect |
| `modeldesk_activate_experiment` | Select an experiment by index or name, optionally saving the current one. | Context |
| `modeldesk_save_active_experiment` | Save the active experiment. | Persist |
| `modeldesk_download_active_experiment` | Download the active experiment to the runtime. | Runtime |
| `modeldesk_synchronize_aurelion` | Synchronize the active scene with AURELION using optional routing values. | Runtime |
| `modeldesk_get_workflow_plan` | Return an ordered dry-run recipe for a named workflow; no recipe step is executed. | Plan |
| `modeldesk_list_tools_by_use_case` | Resolve UC1-UC5 or Supporting to the corresponding tagged tool list. | Plan |

Environment Pool files and Traffic Object Manager catalog entries are different collections. Listing one does not prove an object exists in the other.

## UC1: Vehicle Parameterization

**11 tools** for ASM-based vehicle model bindings and parameterization.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_list_parameter_sets` | List parameter sets in the active experiment. | Inspect |
| `modeldesk_activate_parameter_set` | Select a parameter set by index or name, optionally saving the current context. | Context |
| `modeldesk_get_parameterization_summary` | Inspect the experiment, active model, parameter set, and component context. | Inspect |
| `modeldesk_get_active_model_info` | Inspect the active experiment's model binding. | Inspect |
| `modeldesk_set_active_model` | Set the model file and optional working directory, initialization command, and platform. | Context |
| `modeldesk_get_parameter_value` | Read a parameter using its exact path in the active parameter set. | Inspect |
| `modeldesk_set_scalar_parameter` | Assign one scalar value using invariant-culture text. | Edit |
| `modeldesk_set_parameter_value` | Assign Scalar, Text, Vector, Matrix, or Table data from a JSON value. | Edit |
| `modeldesk_get_processing_summary` | Inspect processing readiness for the active parameter set. | Inspect |
| `modeldesk_get_processing_configuration` | Inspect the processing configuration exposed by the active installation. | Inspect |
| `modeldesk_run_processing` | Execute processing for the active parameter set. | Runtime |

Parameter paths must be known exactly; there is no general parameter-path enumeration tool. Summary/configuration fields can be unavailable in a particular installation and must not be treated as readiness proof when null or incomplete.

## UC2: Roads

**18 tools** for road networks, geometry, lanes, road-local objects, and connections.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_create_road_network` | Create a Road Network pool file, with explicit overwrite control. | Persist |
| `modeldesk_get_road_summary` | Inspect the active road-domain context and available content. | Inspect |
| `modeldesk_activate_road` | Activate a road-domain target by selector. | Context |
| `modeldesk_list_roads` | List roads in the active network and discover safe selectors. | Inspect |
| `modeldesk_save_road_network_as` | Save the active road network to an absolute destination ending in `.rd`. | Persist |
| `modeldesk_add_road` | Add a road and configure its first lane section. | Edit |
| `modeldesk_update_road` | Rename a selected road. | Edit |
| `modeldesk_remove_road` | Remove a selected road from the active network. | Edit |
| `modeldesk_add_road_segment` | Add a Straight, Circular, Clothoid, or Spline segment with typed properties. | Edit |
| `modeldesk_update_road_segment` | Change a selected segment's type and/or properties. | Edit |
| `modeldesk_remove_road_segment` | Remove a segment using its zero-based collection index. | Edit |
| `modeldesk_configure_road_lanes` | Configure lane counts, width, and optional lane-section length. | Edit |
| `modeldesk_add_road_object` | Add a road-local traffic object at road-relative `s` and `d`, with optional catalog/lane mapping. | Edit |
| `modeldesk_update_road_object` | Patch selected road-object properties. | Edit |
| `modeldesk_remove_road_object` | Remove a road-local traffic object by index. | Edit |
| `modeldesk_connect_roads` | Connect Start/End endpoints using Move or Modify geometry adaptation. | Edit |
| `modeldesk_disconnect_road` | Disconnect a selected Start/End endpoint. | Edit |
| `modeldesk_create_basic_road` | Create a straight road with lanes and optional road-local traffic objects. | Edit |

Segment inputs use zero-based collection indices even when a returned COM `Index` is one-based. Road creation and other compound edits can leave partial in-memory content if a later step fails. Creating a pool file does not replace the need to inspect and activate the intended road context.

## UC3: Scenarios and Traffic

**22 tools** for scenario participants, maneuver content, behavior profiles, and runtime controls.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_create_traffic_scenario` | Create a Traffic Scenario pool file, with explicit overwrite control. | Persist |
| `modeldesk_get_scenario_summary` | Inspect the active scenario and participant/maneuver context. | Inspect |
| `modeldesk_activate_scenario` | Activate a scenario by its exact name. | Context |
| `modeldesk_list_scenario_fellows` | List Fellows and selectors for subsequent edits. | Inspect |
| `modeldesk_list_scenario_maneuvers` | List ego maneuvers in the active scenario. | Inspect |
| `modeldesk_add_scenario_fellow` | Add a Fellow with optional properties and traffic-object/driver references. | Edit |
| `modeldesk_update_scenario_fellow` | Edit a selected Fellow's name, properties, and optional references. | Edit |
| `modeldesk_remove_scenario_fellow` | Remove the selected Fellow. | Edit |
| `modeldesk_add_scenario_maneuver` | Add an ego maneuver or a sequence in the selected Fellow scope. | Edit |
| `modeldesk_update_scenario_maneuver` | Patch the selected ego maneuver or Fellow sequence. | Edit |
| `modeldesk_remove_scenario_maneuver` | Remove a selected maneuver/sequence; use a freshly listed index for Fellow sequences. | Edit |
| `modeldesk_verify_scenario_maneuver_sequence` | Compare a requested order with the immutable current sequence; no changes are applied. | Inspect |
| `modeldesk_set_maneuver_behavior_profiles` | Set and read back ego initial values or one explicit Fellow behavior profile. | Edit |
| `modeldesk_get_scenario_road` | Inspect the active scenario's referenced road, subject to available identity fields. | Inspect |
| `modeldesk_set_scenario_road` | Assign a listed road by name to the active scenario. | Edit |
| `modeldesk_list_fellow_activities` | Discover activities/sequences in the selected Fellow or ego scope. | Inspect |
| `modeldesk_get_vehicle_object_type` | Inspect the selected ego/Fellow vehicle object type. | Inspect |
| `modeldesk_list_vehicle_object_types` | List selectable vehicle object types and indices exposed by ModelDesk. | Inspect |
| `modeldesk_set_vehicle_object_type` | Activate a vehicle object type using a listed element index. | Edit |
| `modeldesk_start_maneuver` | Start maneuver execution, optionally downloading the experiment first. | Runtime |
| `modeldesk_stop_maneuver` | Stop maneuver execution. | Runtime |
| `modeldesk_reset_maneuver` | Reset maneuver execution to its initial condition. | Runtime |

Fellow creation does not require yaw or behavior-profile values. `StartPosition` (Start position on route, meters) and `InitialLongitudinalVelocity` (km/h) belong only to the ego maneuver sequence. Fellow payloads must explicitly select either `Position.YawAngleConstant.Constant` or `Velocity.Constant.Constant`; these are alternative profiles, not aliases for ego initial fields. See [use-cases.md](use-cases.md) for payload examples.

Fellow maneuver deletion by plain name is currently unreliable; use the index returned by a fresh activities listing. Vehicle-type listings can contain placeholder labels, and scenario-road identity fields can be null; do not invent paths or report those incomplete fields as verified references.

## UC4: Traffic Objects

**8 tools** for reusable Traffic Object Manager catalog entries and folders.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_get_traffic_objects_summary` | Inspect Traffic Object Manager catalog availability and context. | Inspect |
| `modeldesk_list_traffic_objects` | List reusable traffic objects and their selectors. | Inspect |
| `modeldesk_list_traffic_object_folders` | List catalog folders and their hierarchy. | Inspect |
| `modeldesk_validate_traffic_object_reference` | Verify that a catalog selector resolves before assigning the reference elsewhere. | Inspect |
| `modeldesk_add_traffic_object` | Add a named catalog entry with a 3D asset reference when mutation is supported. | Edit |
| `modeldesk_remove_traffic_object` | Remove a selected catalog object. | Edit |
| `modeldesk_add_traffic_object_folder` | Add a catalog folder when mutation is supported. | Edit |
| `modeldesk_remove_traffic_object_folder` | Remove a selected catalog folder. | Edit |

Inspect capability flags before catalog mutations. An empty catalog or disabled mutation capability is not evidence that the Environment Pool has no assets.

## UC5: Tests and Analysis

**10 tools** for testing, plotting, and numerical capture comparison.

| Tool | Purpose | Effect |
| --- | --- | --- |
| `modeldesk_get_test_summary` | Inspect the active test configuration; an accessible test must exist. | Inspect |
| `modeldesk_activate_test` | Activate a project-specific test configuration by exact name. | Context |
| `modeldesk_list_logical_test_cases` | List logical cases in the active test. | Inspect |
| `modeldesk_list_concrete_test_cases` | List concrete cases beneath one selected logical case; defaults to logical index 0. | Inspect |
| `modeldesk_execute_test` | Execute the active test or a selected supported test-case scope. | Runtime |
| `modeldesk_get_plotting_summary` | Inspect plotting configuration, available captures, and layouts. | Inspect |
| `modeldesk_activate_plotting` | Activate a plotting configuration by selector. | Context |
| `modeldesk_list_plot_captures` | List captures in the active plotting configuration. | Inspect |
| `modeldesk_list_plot_layouts` | List plot layouts in the active plotting configuration. | Inspect |
| `modeldesk_compare_captures` | Compare two project Measurements MAT files using selected signals and numeric tolerances; comparison rows are paginated. | Analyze |

Test activation and execution need installed test content and any required runtime setup. Plot capture listing and capture comparison are separate operations: comparison uses capture filenames in the active project's Measurements folder, not arbitrary external paths. Signal specs and tolerances are JSON-encoded arguments. The comparison `signalSet` returns counts only (`commonCount`, `onlyReferenceCount`, and `onlyCandidateCount`); `comparisons` is paginated by `offset` and `limit`.

## Inputs and Results

Selectors normally use `index` or `name`, with index values supplied as decimal strings. `active` is accepted only in scopes that support it; for Fellow selectors it identifies the ego. Do not assume selector support is identical across tools.

Arguments ending in `Json` contain serialized JSON, not a nested MCP argument object. For example, an ego profile request uses `"longitudinalProfileJson": "{\"StartPosition\":70.0,\"InitialLongitudinalVelocity\":20.0}"`.

All tools return `ok`, `operation`, `sessionId`, `data`, `warnings`, `artifacts`, and `error`. Domain summaries and mutation details have operation-specific shapes. A registered name does not guarantee a live domain is available; check capabilities, actual results, and [error-handling.md](error-handling.md).

## Source of Truth

The name inventory is maintained in [../src/modeldesk_mcp/tools/registry.py](../src/modeldesk_mcp/tools/registry.py). Use-case overlaps are maintained in [../src/modeldesk_mcp/contracts/use_cases.py](../src/modeldesk_mcp/contracts/use_cases.py).

For a names-only inventory, run `.\ModelDeskMCP.cmd --list-tools`. For UC lookup, call `modeldesk_list_tools_by_use_case` with `UC1`, `UC2`, `UC3`, `UC4`, `UC5`, or `Supporting`. This reference groups shared tools once; use-case lookup may legitimately return them in more than one group.
