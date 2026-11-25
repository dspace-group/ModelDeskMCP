"""COM-free effect previews for high-impact tool invocations."""

from typing import Any, Literal, NotRequired, TypedDict

from modeldesk_mcp.contracts.models import PreviewInspection


class EffectPreview(TypedDict):
    dryRun: Literal[True]
    target: str
    requestedTarget: dict[str, str | int]
    effects: list[str]
    preconditions: str
    targetVerified: bool
    inspection: NotRequired[PreviewInspection]


PREVIEW_EFFECTS: dict[str, tuple[str, str]] = {
    "modeldesk_open_project": ("Requested project", "Open the requested project and optionally activate its experiment."),
    "modeldesk_save_project": ("Active project", "Write current project changes to disk."),
    "modeldesk_activate_experiment": ("Selected experiment", "Switch the active experiment."),
    "modeldesk_save_active_experiment": ("Active experiment", "Write current experiment changes to disk."),
    "modeldesk_download_active_experiment": ("Active experiment and runtime", "Transfer the experiment and replace the deployed state."),
    "modeldesk_activate_parameter_set": ("Selected parameter set", "Switch the active parameter set."),
    "modeldesk_set_active_model": ("Active experiment and requested model file", "Replace the model binding; a requested initialization command can run on binding."),
    "modeldesk_add_road": ("Active road network", "Insert a new road."),
    "modeldesk_update_road": ("Selected road", "Apply the requested road changes."),
    "modeldesk_add_road_segment": ("Selected road", "Insert a new segment."),
    "modeldesk_update_road_segment": ("Selected road segment", "Apply the requested segment changes."),
    "modeldesk_configure_road_lanes": ("Selected road lane section", "Apply the requested lane configuration."),
    "modeldesk_add_road_object": ("Selected road", "Insert a new road object."),
    "modeldesk_update_road_object": ("Selected road object", "Apply the requested object changes."),
    "modeldesk_connect_roads": ("Selected source and target road endpoints", "Connect the endpoints and apply the requested geometry adaptation."),
    "modeldesk_create_basic_road": ("Active road network", "Create a road with the requested geometry, lanes, and objects."),
    "modeldesk_add_scenario_fellow": ("Active traffic scenario", "Insert a new fellow."),
    "modeldesk_update_scenario_fellow": ("Selected fellow", "Apply the requested fellow changes."),
    "modeldesk_add_scenario_maneuver": ("Ego or selected fellow", "Insert a new maneuver or sequence."),
    "modeldesk_update_scenario_maneuver": ("Selected maneuver", "Apply the requested maneuver changes."),
    "modeldesk_set_maneuver_behavior_profiles": ("Selected maneuver and segment", "Apply the requested behavior profiles."),
    "modeldesk_set_scenario_road": ("Active traffic scenario", "Change its assigned road."),
    "modeldesk_set_vehicle_object_type": ("Selected vehicle", "Change its vehicle object type."),
    "modeldesk_run_processing": ("Active parameter set", "Run processing; it can produce new results or change runtime state."),
    "modeldesk_execute_test": ("Active test configuration or selected logical case", "Execute tests and produce run results."),
    "modeldesk_start_maneuver": ("Active experiment runtime", "Start maneuver execution."),
    "modeldesk_stop_maneuver": ("Active experiment runtime", "Stop maneuver execution."),
    "modeldesk_reset_maneuver": ("Active experiment runtime", "Reset maneuver execution."),
    "modeldesk_synchronize_aurelion": ("Active scene and AURELION target", "Synchronize the scene to the selected AURELION target."),
}

_TARGET_FIELDS = frozenset({
    "projectFile", "initialExperiment", "modelFilePath", "name", "roadName", "scope", "mode", "sourcePoint",
    "targetPoint", "laneSectionIndex", "segmentIndex", "insertAfterSegmentIndex", "objectIndex", "maneuverIndex",
    "elementIndex", "system", "scenario",
})
_CONDITIONAL_EFFECTS = {
    "saveActive": "Save the current active target before switching.",
    "save": "Save the active experiment after applying the changes.",
    "download": "Download the active experiment and replace deployed state after applying the changes.",
    "downloadIfNotRunning": "Download the experiment first if it is not already running.",
}


def build_preview(name: str, arguments: dict[str, Any], properties: dict[str, Any], description: str) -> EffectPreview:
    target, effect = PREVIEW_EFFECTS[name]
    effects = [effect]
    for field, optional_effect in _CONDITIONAL_EFFECTS.items():
        if field in properties and arguments.get(field, properties[field].get("default")) is True:
            effects.append(optional_effect)
    return {
        "dryRun": True,
        "target": target,
        "requestedTarget": {
            key: value for key, value in arguments.items()
            if (key in _TARGET_FIELDS or key.endswith(("SelectorKind", "SelectorValue")) or key in {"selectorKind", "selectorValue"})
            and type(value) in (str, int)
        },
        "effects": effects,
        "preconditions": next((line for line in description.splitlines() if line.startswith("Preconditions: ")), ""),
        "targetVerified": False,
    }