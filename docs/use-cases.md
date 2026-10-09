# Use Cases

[../README.md](../README.md) | [tools.md](tools.md) | [error-handling.md](error-handling.md)

These workflows describe the current MCP tool surface, not every feature available in the ModelDesk UI. Use [tools.md](tools.md) for the complete inventory and inspect capabilities before assuming a domain is usable.

Example names, paths, and indices are illustrative. Replace them with values from your active project and fresh listings. The JSON blocks are tool arguments, not commands that run automatically; fields ending in `Json` intentionally contain serialized JSON strings.

## Before Any Workflow

1. Read `modeldesk_get_status` and `modeldesk_get_capabilities`.
2. Verify the active project and experiment; switch context only when intended.
3. List the relevant collection and resolve the target explicitly.
4. Plan edits separately from Save, Download, processing, test execution, and runtime controls.
5. After each dependent operation, inspect its result before continuing.

For discovery, arguments for `modeldesk_list_tools_by_use_case`:

```json
{
	"useCase": "UC3"
}
```

This is local lookup, not an execution request. Use-case lists can overlap for shared tools.

## UC1: Parameterize Vehicle Models

**Goal:** Edit vehicle-model parameters in a known experiment and parameter-set context.

1. List and activate the intended experiment and parameter set.
2. Inspect the active model with `modeldesk_get_active_model_info`; change the binding only if necessary.
3. Read the parameterization summary and each intended parameter by its exact path.
4. Use the scalar or typed JSON setter, then read the value back.
5. Save the project or experiment only when required. Run processing as a separate, explicit action after inspecting its configuration.

Arguments for `modeldesk_set_parameter_value`:

```json
{
	"parameterPath": "Vehicle.Speed",
	"valueKind": "Scalar",
	"valueJson": "1200.0"
}
```

Supported typed shapes are Scalar, Text, Vector, Matrix, and Table. Valid structure and dimensions depend on the selected shape and parameter. Paths must be known exactly: there is no general parameter enumeration or automatic unit conversion workflow. Check reported type/unit metadata before writing.

Processing summary/configuration can be incomplete in some installations. Null fields or collection errors are not proof that processing is configured correctly.

**Recipes:** `parameterize_vehicle_variant`, `run_processing_and_save_parameter_set`.

## UC2: Build Roads

**Goal:** Author roads in an active Road Network for simulation and visualization.

A Road Network is a pool file containing roads; each road contains ordered segments, lane sections, and road-local traffic objects. Creating a pool file and editing the active network are separate steps.

1. Inspect Road Environment Pool files with `modeldesk_list_environment_pool_items`.
2. If a new file is needed, create it with `modeldesk_create_road_network`, with overwrite disabled unless intended.
3. Activate and inspect the target network before adding or editing roads.
4. Add/update segments, configure lanes, place road-local objects, and connect endpoints as needed.
5. Reinspect the result before Save, Download, or AURELION synchronization.

Arguments for `modeldesk_create_basic_road` in the already-active network:

```json
{
	"name": "ExampleRoad",
	"length": 80.0,
	"leftLaneCount": 1,
	"rightLaneCount": 1,
	"laneWidth": 3.5,
	"trafficObjectsJson": "[]",
	"save": false,
	"download": false
}
```

The basic helper creates a straight road. Use individual segment tools for Straight, Circular, Clothoid, or Spline geometry and the validated property schema for that type. Road-local objects use longitudinal `s` and lateral `d` in meters. Connections select Start/End endpoints and Move/Modify adaptation.

Segment input indices are zero-based, while a returned COM segment `Index` can be one-based. Resolve the actual collection index before an update or removal. Compound road creation is not atomic; a failed later step can leave a newly created road or segment in memory.

The MCP registry does not expose general OpenDRIVE export, junction authoring, or arbitrary surface/scenery editing tools. Do not treat broader Road Generator features as available MCP operations.

**Recipes:** `create_basic_road`, `sync_scene_to_aurelion`.

## UC3: Define Scenarios and Traffic

**Goal:** Author ego maneuvers and Fellow behavior in an explicitly selected scenario.

1. Inspect Scenario and TrafficDriver Environment Pool files when their references are unknown.
2. Create a scenario pool file if needed, then activate the intended scenario.
3. Inspect its road, ego maneuvers, and Fellows; assign only verified road/catalog/driver references.
4. Add or update Fellows and discover their activities/sequences before editing profiles.
5. Read back the relevant values before Save/Download. Start, stop, or reset execution only as an explicit runtime step.

### Fellow Creation and Sequences

Arguments for `modeldesk_add_scenario_fellow`:

```json
{
	"name": "Traffic1",
	"save": false,
	"download": false
}
```

Creation requires neither yaw nor initial/profile values. A new Fellow may already have a sequence. Call `modeldesk_list_fellow_activities` before adding another; do not assume creation left an empty collection. Fellow-scoped maneuver tools operate on its sequences, not the ego maneuver collection.

Use a freshly listed index for Fellow sequence deletion. Plain-name deletion is not supported by the verified live removal path and can fail without changing the collection.

### Ego Initial Values

Only the ego maneuver sequence has **Start position on route** (`StartPosition`, meters) and **Initial longitudinal velocity** (`InitialLongitudinalVelocity`, km/h). These are not Fellow properties.

Arguments for `modeldesk_set_maneuver_behavior_profiles` targeting an ego maneuver:

```json
{
	"fellowSelectorKind": "active",
	"fellowSelectorValue": "active",
	"maneuverSelectorKind": "index",
	"maneuverSelectorValue": "0",
	"longitudinalProfileJson": "{\"StartPosition\":70.0,\"InitialLongitudinalVelocity\":20.0}",
	"lateralProfileJson": "{}",
	"save": false,
	"download": false
}
```

Values pass through unchanged. The selected ego maneuver must have exactly one sequence; zero or multiple sequences are rejected because the tool has no separate ego sequence selector.

### Fellow Behavior Profiles

Fellows require explicit nested behavior-profile JSON. Arguments for `modeldesk_set_maneuver_behavior_profiles` targeting a sequence discovered on `Traffic1`:

```json
{
	"fellowSelectorKind": "name",
	"fellowSelectorValue": "Traffic1",
	"maneuverSelectorKind": "index",
	"maneuverSelectorValue": "0",
	"longitudinalProfileJson": "{\"Velocity\":{\"Constant\":{\"Constant\":20.0}}}",
	"lateralProfileJson": "{}",
	"save": false,
	"download": false
}
```

The alternative Position payload is `{"Position":{"YawAngleConstant":{"Constant":70.0}}}`. Both target the first segment's longitudinal behavior. Position and Velocity are mutually exclusive alternatives; activating one changes the longitudinal mode. They are not aliases for ego initial values, and submitting either ego-only field for a Fellow is rejected before COM traversal.

Verify `data.details.longitudinalPosition` or `data.details.longitudinalVelocity` on a successful response. Lateral behavior has no universal schema; leave `lateralProfileJson` as `{}` unless the exact selected interface is verified.

### Ordering and References

`modeldesk_set_scenario_maneuver_sequence` can confirm an already-matching order. It rejects a changed order before Save/Download because the interface exposes immutable maneuver indices and no verified reorder member. Do not rewrite indices or recreate existing content as an implicit workaround.

Scenario-road identity fields can be null, and selectable vehicle-type lists can contain placeholder labels. Check the setter result and relevant live context instead of inventing paths or declaring those fields verified.

**Recipe:** `create_basic_traffic_scenario`. Recipe wording is guidance, not permission to bypass these current limits or automatically start execution.

## UC4: Manage Traffic Objects

**Goal:** Inspect and validate reusable Traffic Object Manager assets before assigning them to roads or participants.

1. Read capabilities and the traffic-object summary.
2. List catalog objects and folders.
3. Validate a selected reference before assigning it elsewhere.
4. Add/remove catalog objects or folders only when the installation exposes mutation support.

Keep three concepts separate: reusable catalog entries, road-local placements, and scenario Fellow instances. Environment Pool files are another collection; an empty TOM catalog does not mean there are no filesystem-backed assets.

Reference names and paths are installation-specific. Reuse returned values rather than constructing a catalog path or driver reference from a display label.

**Recipe:** `manage_traffic_objects`.

## UC5: Test and Analyze Results

**Goal:** Inspect test content and compare simulation captures with explicit numerical criteria.

### Testing

Activate an existing test configuration, inspect its summary, list logical cases, then list concrete cases under one selected logical case. An absent or inaccessible active test is a context failure, not an empty successful test run.

`modeldesk_execute_test` is an execution request, not a read-only inspection. Select only a supported scope from its current schema and ensure required project/runtime content is available.

### Plotting and Capture Comparison

Inspect/activate plotting and list captures/layouts as needed. The comparison tool reads capture files from the active project's `WorkingRoot/Pool/Simulation/Measurements`; listing an open plot capture is not required to supply a valid file there.

Arguments for `modeldesk_compare_captures`:

```json
{
	"referenceCapture": "reference.mat",
	"candidateCapture": "candidate.mat",
	"signalSpecsJson": "[\"Vehicle.Speed\"]",
	"tolerancesJson": "{\"rootMeanSquaredError\":0.1}"
}
```

Only filenames ending in `.mat` are accepted, without directory components. Each file is limited to 512 MiB and must be a readable MATLAB 5 capture with the expected root X/Y measurement structure: time data in `X.Data`, and signal `Name`, `Data`, and `Unit` in `Y`. Arbitrary MAT structures and MATLAB 7.3/HDF5 files are not supported by this loader.

An empty signal list `[]` selects common names. Objects with `reference` and `candidate` can map differently named signals. Supported tolerance metrics are `meanAbsoluteError`, `rootMeanSquaredError`, and `maximumAbsoluteError`, globally or under `signals` keyed by reference name. Thresholds must be finite and non-negative.

The comparison reports alignment, overlap, finite sample counts, units, metrics, and verdict. It can interpolate candidate data onto reference timestamps within their common interval; it does not automatically convert units. Inspect each signal's status as well as the overall verdict, which considers evaluated signals only.

`ok=true` means comparison completed, not that tolerances passed. The verdict is `passed`, `failed`, or `notEvaluated`; missing thresholds or fewer than two finite overlapping samples can leave a signal unevaluated. No capture is modified and no report file is automatically generated.

**Recipes:** `execute_regression_test`, `plot_and_compare_two_runs`.

## Dry-run Recipe Index

Arguments for `modeldesk_get_workflow_plan`:

```json
{
	"workflowName": "create_basic_traffic_scenario"
}
```

| Recipe | Purpose |
| --- | --- |
| `automation_session_smoke` | Plan status, capability, and context inspection. |
| `parameterize_vehicle_variant` | Plan model/parameter-set selection and parameter edits. |
| `run_processing_and_save_parameter_set` | Plan configured processing and intentional persistence. |
| `create_basic_road` | Plan road-pool setup and active-network authoring. |
| `create_basic_traffic_scenario` | Plan scenario/Fellow/maneuver authoring within the limits above. |
| `manage_traffic_objects` | Plan catalog inspection and reference validation. |
| `execute_regression_test` | Plan activation, inspection, and explicit test execution. |
| `plot_and_compare_two_runs` | Plan plotting inspection and MAT capture comparison. |
| `sync_scene_to_aurelion` | Plan explicit runtime download and visualization synchronization. |

Plans are local, dry-run-only guidance. They neither validate the complete live environment nor execute, save, or download anything. Apply the current tool schemas and domain restrictions even when recipe wording is broader.
