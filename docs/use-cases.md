# ModelDeskMCP Use Cases

This page summarizes the main engineering use cases supported by ModelDesk, based on the official dSPACE documentation retrieved through the MCP server.

## 1. Parameterize ASM-Based Vehicle Models

ModelDesk is used to navigate through vehicle model hierarchies and edit scalar, vector, matrix, and table parameters. This is the baseline use case for configuring simulation variants for controller development, calibration, and validation.

As a Customer/User of ModelDesk, I want to configure vehicle-model parameters in a controlled experiment context so that I can create, compare, and reuse simulation-ready variants without editing model internals manually.

For the MCP server scope, this use case must include selecting the active project, experiment, model, and parameter set; reading parameter metadata and current values; changing scalar and structured parameter values; and saving the resulting parameter set or project state. Parameterization tools should preserve explicit parameter paths, units, value types, and validation feedback so scripted changes remain traceable.

Typical outcomes:

- vehicle variant setup
- subsystem tuning
- repeatable parameter changes across experiments or parameter sets
- scripted calibration preparation for HIL, SIL, or offline simulation
- parameter-set comparison across experiments

## 2. Build Roads for Simulation and Visualization

The Road Generator supports the creation of road elements, junctions, profiles, surfaces, and scenery. The official documentation states that the generated road data is used both for simulation and for AURELION visualization.

As a Customer/User of ModelDesk, I want to generate and modify roads from structured engineering input so that I can build reproducible proving-ground, curved-road, lane-guidance, and sensor-simulation road networks without drawing each element manually.

For the MCP server scope, this use case must include creating and modifying a complete road network from structured input, not only activating or inspecting existing roads. A RoadNetwork corresponds to an `.rd` file and can contain multiple Roads. A Road is built from ordered Segments, can have Lanes and LaneSections, can contain traffic objects, and can be connected to other Roads through start/end connection points for predecessor/successor style road chains.

Road geometry must support segment types, because this is how the road course is defined. At minimum, structured road creation and modification must support `Straight`, `Circular`, `Clothoid`, and `Spline` segments. Segment-specific properties should be represented explicitly, for example length for straight sections, radius and angle for circular sections, radius and infinite-radius handling for clothoids, and end-vector or parameter-based definitions for splines. This is required to generate curves, transitions, and more realistic road courses.

A basic road creation workflow should accept road length, lane counts, lane widths, segment definitions, and traffic-object placements with explicit road-relative `s` and `d` positions. If a new RoadNetwork file is requested, automation must create it through `Application.ActiveProject.Pool.CreateFile(0, name, overwriteExisting)`, for example `CreateFile(0, "OvertakeRoad", false)` to create `OvertakeRoad.rd`, before the RoadNetwork is activated or populated. More advanced workflows should cover RoadNetwork save/save-as, road-to-road connections, lane-section updates, road-object updates, OpenDRIVE export, junctions, surfaces, scenery, and AURELION synchronization.

Typical outcomes:

- proving-ground style road networks
- complete straight, curved, clothoid-transition, or spline-based roads generated from user-provided dimensions
- new RoadNetwork files created through the project pool with CreateFile type `0`
- RoadNetwork `.rd` files containing one or more connected Roads
- Road predecessor/successor chains through start/end connection points
- configurable lane count and lane width per road side
- traffic objects or scene assets placed at defined `s` and `d` road coordinates
- road-surface and lane variations
- road contexts prepared for 3D animation and sensor simulation

## 3. Define Scenarios and Traffic Behavior

The Scenario Editor is used to define the movement of the ego vehicle and other traffic participants. This supports scenario-driven verification and replay of traffic situations.

As a Customer/User of ModelDesk, I want to define scenario participants, maneuvers, and behavior timing in a reusable way so that I can verify how a vehicle model behaves in specific traffic situations.

For the MCP server scope, this use case must go beyond activating an existing scenario. It should include selecting or creating the active traffic scenario, managing fellows or other traffic participants, assigning traffic-object and driver references, defining maneuvers, building maneuver sequences, and setting longitudinal and lateral behavior profiles. If a new Traffic Scenario file is requested, automation must create it through `Application.ActiveProject.Pool.CreateFile(1, name, overwriteExisting)` before activation and authoring. Scenario tools should keep object references explicit, because scenarios depend on roads, traffic objects, drivers, and experiment context.

The initial properties **Initial longitudinal velocity** and **Start position on route** belong only to the ego vehicle/maneuver sequence, not to fellows. Select the ego with `fellowSelectorKind="active"` and pass `{"StartPosition":70.0,"InitialLongitudinalVelocity":20.0}` to `modeldesk_set_maneuver_behavior_profiles`; route start position is meters and initial longitudinal velocity is km/h, passed unchanged.

Fellows can be created without yaw or behavior-profile values. To edit their longitudinal behavior, discover their sequences with `modeldesk_list_fellow_activities` and provide an explicit profile such as `{"Position":{"YawAngleConstant":{"Constant":70.0}}}` or `{"Velocity":{"Constant":{"Constant":20.0}}}`. These target the first segment's behavior profile, not ego initial fields. The tool reads back the value as `data.details.longitudinalPosition` or `data.details.longitudinalVelocity` before Save or Download. A fellow segment has only one active longitudinal profile; selecting Position or Velocity replaces the active longitudinal mode. Neither ego-only initial property is accepted for a fellow.

The verified Traffic Editor automation interface exposes maneuver collection access and an immutable `Maneuver.Index`, but no reorder member. `modeldesk_set_scenario_maneuver_sequence` therefore accepts only a requested order that already matches the current order; a changed order returns a structured unsupported error before Save or Download. Sequence reordering remains unavailable until a source-backed API is verified.

Typical outcomes:

- maneuver-based tests
- surrounding traffic behavior
- ego and fellow vehicle movement definitions
- reusable maneuver sequences for regression testing
- regression scenarios for ADAS and vehicle dynamics features

## 4. Manage Traffic Objects and Scene Assets

The Traffic Object Manager provides reusable traffic participants and static roadside objects. These assets are then referenced by roads and scenarios.

As a Customer/User of ModelDesk, I want to manage traffic participants and static scene assets as a catalog so that roads and scenarios can reuse consistent objects with known geometry, behavior, and metadata.

For the MCP server scope, this use case must include reading and validating catalog entries, resolving object paths used by roads and scenarios, and preparing safe mutation tools for folders, static objects, dynamic traffic objects, and driver-related references. Tools should distinguish reusable catalog assets from road-local object placements and scenario participant instances.

Typical outcomes:

- standardized object catalogs
- consistent static scenery across scenarios
- reusable dynamic actors for traffic scenarios
- validated catalog paths for road-object and scenario-object references
- separation of asset definition, road placement, and scenario behavior

## 5. Analyze and Compare Simulation Results

The Plot Manager provides layouts and plotters for monitoring signals and comparing runs. This supports investigation after parameter, road, or scenario changes.

As a Customer/User of ModelDesk, I want to inspect and compare simulation signals after a run so that I can understand whether parameter, road, or scenario changes improved or degraded behavior.

For the MCP server scope, this use case includes selecting plotting configurations, listing captures and layouts, identifying signals, and comparing MATLAB capture results with explicit tolerances. Capture file names are resolved from the active project's `WorkingRoot` under `Pool/Simulation/Measurements`; clients do not provide machine-specific absolute paths. Plotting and comparison tools return structured summaries, alignment details, numeric error metrics, and tolerance verdicts instead of only opening UI views.

Typical outcomes:

- signal trend comparison
- run-to-run regression analysis
- quick inspection during calibration and validation loops
- tolerance-based comparison of relevant signals from project-pool MATLAB captures
- result artifacts that can be attached to automated validation reports
