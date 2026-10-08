"""Validated request parsers for ModelDesk MCP tool arguments."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import PureWindowsPath
from typing import Any

from modeldesk_mcp.contracts.enums import (
    EnvironmentPoolGroup,
    ParameterValueKind,
    ProjectPoolFileType,
    RoadSegmentType,
    SelectorKind,
)
from modeldesk_mcp.contracts.models import BasicRoadTrafficObjectSpec


MAX_VECTOR_LENGTH = 8192
MAX_MATRIX_ROWS = 1024
MAX_MATRIX_COLUMNS = 1024
MAX_TABLE_ROWS = 1024
MAX_TABLE_COLUMNS = 1024
MAX_LANE_COUNT_PER_SIDE = 16
MAX_TRAFFIC_OBJECT_COUNT = 128
MAX_LANE_MAPPING_COUNT = 64
MAX_ROAD_LENGTH = 1_000_000.0
MAX_LANE_WIDTH = 20.0
MAX_RADIUS = 1_000_000.0
MAX_ANGLE_DEGREES = 3600.0
MAX_COORDINATE = 1_000_000.0


@dataclass(frozen=True, slots=True)
class Selector:
    """Describes a validated selector for resolving COM collection items."""

    by: SelectorKind
    value: str

    @staticmethod
    def active() -> "Selector":
        """Return the active selector."""

        return Selector(SelectorKind.ACTIVE, "")

    @staticmethod
    def create(selector_kind: str | None, selector_value: str | None) -> "Selector":
        """Create and validate a selector from user-facing values."""

        if selector_kind is None or selector_kind.strip() == "":
            return Selector.active()

        parsed_kind = _parse_enum(selector_kind, SelectorKind, "Unsupported selector kind")
        normalized_value = selector_value or ""
        selector = Selector(parsed_kind, normalized_value)
        selector.validate()
        return selector

    def validate(self) -> None:
        """Validate that the selector has the required value shape."""

        if self.by == SelectorKind.ACTIVE:
            return
        if self.value.strip() == "":
            raise ValueError(f"Selector '{self.by.value}' requires a value.")
        if self.by == SelectorKind.INDEX:
            try:
                index = int(self.value, 10)
            except ValueError as exc:
                raise ValueError("Index selectors must be non-negative integers.") from exc
            if index < 0:
                raise ValueError("Index selectors must be non-negative integers.")

    def to_com_value(self) -> int | str:
        """Convert this selector into the value expected by COM indexers."""

        if self.by == SelectorKind.INDEX:
            return int(self.value, 10)
        return self.value


@dataclass(frozen=True, slots=True)
class ProjectPoolFileCreationRequest:
    """Validated request for ActiveProject.Pool.CreateFile."""

    file_type: ProjectPoolFileType
    name: str
    overwrite_existing: bool

    @staticmethod
    def create(file_type: str | ProjectPoolFileType | None, name: str | None, overwrite_existing: bool) -> "ProjectPoolFileCreationRequest":
        """Create a validated request from a user-facing file type alias."""

        parsed_file_type = _parse_project_pool_file_type(file_type)
        normalized_name = _normalize_project_pool_name(name, parsed_file_type)
        return ProjectPoolFileCreationRequest(parsed_file_type, normalized_name, overwrite_existing)

    def to_com_type(self) -> int:
        """Return the integer COM file type id."""

        return int(self.file_type)

    def expected_extension(self) -> str:
        """Return the expected extension including the leading dot."""

        return _expected_project_pool_extension(self.file_type)


@dataclass(frozen=True, slots=True)
class EnvironmentPoolGroupRequest:
    """Validated request for listing one Environment Pool group."""

    group: EnvironmentPoolGroup
    recursive: bool

    @staticmethod
    def create(group: str | None, recursive: bool) -> "EnvironmentPoolGroupRequest":
        """Create a validated Environment Pool group request."""

        return EnvironmentPoolGroupRequest(_parse_environment_group(group), recursive)

    def folder_name(self) -> str:
        """Return the folder name below Pool/Environment."""

        return {
            EnvironmentPoolGroup.OBJECTS: "Objects",
            EnvironmentPoolGroup.ROAD: "Road",
            EnvironmentPoolGroup.SCENARIO: "Scenario",
            EnvironmentPoolGroup.TRAFFIC_DRIVER: "Traffic Driver",
        }[self.group]

    def file_extension(self) -> str:
        """Return the file extension used to filter this group."""

        return {
            EnvironmentPoolGroup.OBJECTS: ".tro",
            EnvironmentPoolGroup.ROAD: ".rd",
            EnvironmentPoolGroup.SCENARIO: ".xml",
            EnvironmentPoolGroup.TRAFFIC_DRIVER: ".trd",
        }[self.group]

    def item_kind(self) -> str:
        """Return the item kind used in summaries."""

        return {
            EnvironmentPoolGroup.OBJECTS: "traffic object",
            EnvironmentPoolGroup.ROAD: "road network",
            EnvironmentPoolGroup.SCENARIO: "traffic scenario",
            EnvironmentPoolGroup.TRAFFIC_DRIVER: "traffic driver",
        }[self.group]

    def domain_name(self) -> str:
        """Return the domain name used in summaries."""

        return {
            EnvironmentPoolGroup.OBJECTS: "environmentPool.objects",
            EnvironmentPoolGroup.ROAD: "environmentPool.road",
            EnvironmentPoolGroup.SCENARIO: "environmentPool.scenario",
            EnvironmentPoolGroup.TRAFFIC_DRIVER: "environmentPool.trafficDriver",
        }[self.group]


@dataclass(frozen=True, slots=True)
class ParameterValueEditRequest:
    """Validated generic parameter-value edit ready for COM assignment."""

    value_kind: ParameterValueKind
    com_value: Any
    normalized_json: str

    @staticmethod
    def create(value_kind: str | None, value_json: str | None) -> "ParameterValueEditRequest":
        """Create and validate a parameter-value edit request."""

        parsed_kind = _parse_parameter_value_kind(value_kind)
        if value_json is None or value_json.strip() == "":
            raise ValueError("Parameter value JSON must not be empty.")
        try:
            root = json.loads(value_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Parameter value JSON is invalid: {exc.msg}") from exc
        value = _case_insensitive_get(root, "value") if isinstance(root, dict) and _has_key(root, "value") else root
        com_value = _parse_parameter_com_value(parsed_kind, value)
        return ParameterValueEditRequest(parsed_kind, com_value, json.dumps(value, separators=(",", ":")))


@dataclass(frozen=True, slots=True)
class ManeuverBehaviorProfileRequest:
    """Validated ego/fellow profile payloads, ready before the gateway touches COM."""

    longitudinal_properties: dict[str, Any]
    lateral_properties: dict[str, Any]

    @staticmethod
    def create(
        fellow_selector: Selector,
        longitudinal_profile_json: str | None,
        lateral_profile_json: str | None,
    ) -> "ManeuverBehaviorProfileRequest":
        """Parse both profile sides and enforce the existing selector-specific payload contract.

        Active (ego) longitudinal values are direct sequence-owned finite numbers. Fellow
        values must explicitly select Position.YawAngleConstant or Velocity.Constant
        behavior profiles; these are not aliases for the ego-only initial properties.
        A fellow segment supports only one longitudinal profile. Lateral scalar assignments
        retain their shape. This method has no COM side effects and raises ValueError for
        malformed, ambiguous, or empty requests.
        """

        if fellow_selector is None:
            raise ValueError("A fellow selector is required.")
        fellow_selector.validate()
        longitudinal = _parse_maneuver_behavior_profile_json(longitudinal_profile_json, "longitudinalProfileJson")
        lateral = _parse_maneuver_behavior_profile_json(lateral_profile_json, "lateralProfileJson")
        _validate_finite_json_numbers(longitudinal, "longitudinalProfileJson")
        _validate_finite_json_numbers(lateral, "lateralProfileJson")

        if fellow_selector.by == SelectorKind.ACTIVE:
            _validate_ego_maneuver_properties(longitudinal)
        else:
            longitudinal = _validate_fellow_longitudinal_properties(longitudinal)
        _validate_scalar_property_object(lateral, "lateralProfileJson", 0)

        if not longitudinal and not lateral:
            raise ValueError("At least one longitudinal or lateral profile property must be provided.")
        return ManeuverBehaviorProfileRequest(longitudinal, lateral)


@dataclass(frozen=True, slots=True)
class RoadVectorSpec:
    """Optional spline end-vector properties."""

    x: float | None = None
    y: float | None = None
    tangent: float | None = None


@dataclass(frozen=True, slots=True)
class RoadSplineParameterSpec:
    """Optional spline parameter properties."""

    b: float | None = None
    c: float | None = None
    d: float | None = None


@dataclass(frozen=True, slots=True)
class RoadSegmentProperties:
    """Optional road segment properties supported by road-authoring tools."""

    name: str | None = None
    length: float | None = None
    radius: float | None = None
    angle: float | None = None
    is_infinite: bool | None = None
    spline_definition_type: str | None = None
    relative_end_vector: RoadVectorSpec | None = None
    absolute_end_vector: RoadVectorSpec | None = None
    spline_parameter_x: RoadSplineParameterSpec | None = None
    spline_parameter_y: RoadSplineParameterSpec | None = None

    @staticmethod
    def empty() -> "RoadSegmentProperties":
        """Return an empty segment property set."""

        return RoadSegmentProperties()


@dataclass(frozen=True, slots=True)
class RoadSegmentEditRequest:
    """Validated road-segment edit request."""

    segment_type: RoadSegmentType | None
    properties: RoadSegmentProperties
    insert_after_segment_index: int
    save: bool
    download: bool

    @staticmethod
    def create(
        segment_type: str | None,
        properties_json: str | None,
        insert_after_segment_index: int,
        save: bool,
        download: bool,
        segment_type_required: bool,
    ) -> "RoadSegmentEditRequest":
        """Create and validate a road-segment edit request."""

        parsed_type = _parse_road_segment_type(segment_type, segment_type_required)
        if insert_after_segment_index < -1:
            raise ValueError("Insert-after index must be -1 or a non-negative segment index.")
        properties = _parse_road_segment_properties(properties_json)
        _validate_road_segment_properties(properties)
        if parsed_type is not None:
            _validate_road_segment_properties_for_type(parsed_type, properties)
        return RoadSegmentEditRequest(parsed_type, properties, insert_after_segment_index, save, download)


@dataclass(frozen=True, slots=True)
class RoadObjectProperties:
    """Optional road traffic-object properties for updates."""

    name: str | None = None
    catalog_path: str | None = None
    s: float | None = None
    d: float | None = None
    lane_mapping: tuple[int, ...] | None = None

    @staticmethod
    def create(properties_json: str | None) -> "RoadObjectProperties":
        """Parse and validate road-object properties from JSON."""

        if properties_json is None or properties_json.strip() == "":
            return RoadObjectProperties()
        data = _parse_json_object(properties_json, "Road object properties JSON must be an object")
        properties = RoadObjectProperties(
            name=_optional_text(_case_insensitive_get(data, "name")),
            catalog_path=_optional_text(_case_insensitive_get(data, "catalogPath")),
            s=_optional_float(_case_insensitive_get(data, "s")),
            d=_optional_float(_case_insensitive_get(data, "d")),
            lane_mapping=_optional_lane_mapping(_case_insensitive_get(data, "laneMapping")),
        )
        _validate_road_object_properties(properties)
        return properties

    @staticmethod
    def parse_lane_mapping(lane_mapping_json: str | None) -> tuple[int, ...]:
        """Parse and validate a lane-mapping JSON integer array."""

        if lane_mapping_json is None or lane_mapping_json.strip() == "":
            return ()
        try:
            data = json.loads(lane_mapping_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Lane mapping JSON must be an integer array: {exc.msg}") from exc
        lane_mapping = _optional_lane_mapping(data) or ()
        _validate_lane_mapping(lane_mapping)
        return lane_mapping


@dataclass(frozen=True, slots=True)
class BasicRoadCreationRequest:
    """Validated request for creating a simple straight road."""

    name: str
    length: float
    left_lane_count: int
    right_lane_count: int
    lane_width: float
    traffic_objects: tuple[BasicRoadTrafficObjectSpec, ...]
    save: bool
    download: bool

    @staticmethod
    def create(
        name: str | None,
        length: float,
        left_lane_count: int,
        right_lane_count: int,
        lane_width: float,
        traffic_objects_json: str | None,
        save: bool,
        download: bool,
    ) -> "BasicRoadCreationRequest":
        """Create and validate a basic-road creation request."""

        normalized_name = _required_text(name, "Road name must not be empty.")
        _validate_finite_range(length, 0.0, MAX_ROAD_LENGTH, "length", exclusive_minimum=True)
        _validate_finite_range(lane_width, 0.0, MAX_LANE_WIDTH, "laneWidth", exclusive_minimum=True)
        _validate_lane_count(left_lane_count, "leftLaneCount")
        _validate_lane_count(right_lane_count, "rightLaneCount")
        if left_lane_count + right_lane_count == 0:
            raise ValueError("At least one left or right lane is required.")
        traffic_objects = _parse_basic_traffic_objects(traffic_objects_json)
        if len(traffic_objects) > MAX_TRAFFIC_OBJECT_COUNT:
            raise ValueError(f"At most {MAX_TRAFFIC_OBJECT_COUNT} traffic objects are supported per call.")
        for index, traffic_object in enumerate(traffic_objects):
            _validate_basic_traffic_object(traffic_object, index, length)
        return BasicRoadCreationRequest(
            normalized_name,
            length,
            left_lane_count,
            right_lane_count,
            lane_width,
            traffic_objects,
            save,
            download,
        )


def parse_selector_array_json(json_text: str | None, parameter_name: str) -> tuple[Selector, ...]:
    """Parse a bounded maneuver selector array from JSON."""

    if json_text is None or json_text.strip() == "":
        return ()
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Selector JSON must be an array: {exc.msg}") from exc
    if not isinstance(data, list):
        raise ValueError("Selector JSON must be an array.")
    selectors: list[Selector] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each selector item must be an object with selectorKind and selectorValue.")
        selector_kind = _case_insensitive_get(item, "selectorKind")
        selector_value = _case_insensitive_get(item, "selectorValue")
        if not isinstance(selector_kind, str) or not isinstance(selector_value, str):
            raise ValueError("Each selector item must contain string selectorKind and selectorValue.")
        selector = Selector.create(selector_kind, selector_value)
        if selector.by == SelectorKind.ACTIVE:
            raise ValueError(f"Active selectors are not supported in {parameter_name} arrays.")
        selectors.append(selector)
    return tuple(selectors)


def parse_scalar_properties_json(properties_json: str | None, parameter_name: str) -> dict[str, Any]:
    """Parse bounded finite-valued scalar properties before COM mutation.

    Blank input means no assignments. Non-object, unsupported, over-deep, or
    non-finite JSON values raise ``ValueError``; the scenario gateway relies on
    this boundary to reject malformed profiles before traversing COM objects.
    """

    if properties_json is None or properties_json.strip() == "":
        return {}
    data = _parse_json_object(properties_json, "Properties JSON must be an object")
    _validate_finite_json_numbers(data, parameter_name)
    _validate_scalar_property_object(data, parameter_name, 0)
    return data


def _parse_enum(value: str, enum_type: type[Any], message: str) -> Any:
    normalized = value.strip().replace(" ", "").replace("_", "").lower()
    for item in enum_type:
        item_names = {item.name.replace("_", "").lower(), str(item.value).replace(" ", "").lower()}
        if normalized in item_names:
            return item
    raise ValueError(f"{message} '{value}'.")


def _parse_project_pool_file_type(file_type: str | ProjectPoolFileType | None) -> ProjectPoolFileType:
    if isinstance(file_type, ProjectPoolFileType):
        return file_type
    if file_type is None or file_type.strip() == "":
        raise ValueError("Project pool file type must not be empty.")
    aliases = {
        "0": ProjectPoolFileType.ROAD_NETWORK,
        "road": ProjectPoolFileType.ROAD_NETWORK,
        "roadnetwork": ProjectPoolFileType.ROAD_NETWORK,
        "road network": ProjectPoolFileType.ROAD_NETWORK,
        "rd": ProjectPoolFileType.ROAD_NETWORK,
        ".rd": ProjectPoolFileType.ROAD_NETWORK,
        "1": ProjectPoolFileType.TRAFFIC_SCENARIO,
        "scenario": ProjectPoolFileType.TRAFFIC_SCENARIO,
        "trafficscenario": ProjectPoolFileType.TRAFFIC_SCENARIO,
        "traffic scenario": ProjectPoolFileType.TRAFFIC_SCENARIO,
        "2": ProjectPoolFileType.TESTING_TEST,
        "test": ProjectPoolFileType.TESTING_TEST,
        "testingtest": ProjectPoolFileType.TESTING_TEST,
        "testing test": ProjectPoolFileType.TESTING_TEST,
        "tst": ProjectPoolFileType.TESTING_TEST,
        ".tst": ProjectPoolFileType.TESTING_TEST,
        "3": ProjectPoolFileType.SIMULATION_CONFIGURATION,
        "simulationconfiguration": ProjectPoolFileType.SIMULATION_CONFIGURATION,
        "simulation configuration": ProjectPoolFileType.SIMULATION_CONFIGURATION,
        "simconfig": ProjectPoolFileType.SIMULATION_CONFIGURATION,
        "sim config": ProjectPoolFileType.SIMULATION_CONFIGURATION,
        "4": ProjectPoolFileType.TRAFFIC_DRIVER,
        "driver": ProjectPoolFileType.TRAFFIC_DRIVER,
        "trafficdriver": ProjectPoolFileType.TRAFFIC_DRIVER,
        "traffic driver": ProjectPoolFileType.TRAFFIC_DRIVER,
        "trd": ProjectPoolFileType.TRAFFIC_DRIVER,
        ".trd": ProjectPoolFileType.TRAFFIC_DRIVER,
    }
    normalized = file_type.strip().lower()
    if normalized in aliases:
        return aliases[normalized]
    for item in ProjectPoolFileType:
        if normalized == item.display_name.lower():
            return item
    raise ValueError("Project pool file type must be 0/RoadNetwork, 1/TrafficScenario, 2/TestingTest, 3/SimulationConfiguration, or 4/TrafficDriver.")


def _normalize_project_pool_name(name: str | None, file_type: ProjectPoolFileType) -> str:
    normalized = _required_text(name, "Project pool file name must not be empty.")
    if PureWindowsPath(normalized).name != normalized:
        raise ValueError("Project pool file name must be a file name without directories.")
    invalid_chars = set('<>:"/\\|?*')
    if any(char in invalid_chars or ord(char) < 32 for char in normalized):
        raise ValueError("Project pool file name contains invalid file-name characters.")
    extension = _expected_project_pool_extension(file_type)
    if normalized.lower().endswith(extension):
        normalized = normalized[: -len(extension)]
    if normalized.strip() == "":
        raise ValueError("Project pool file name must contain a base name before the extension.")
    return normalized


def _expected_project_pool_extension(file_type: ProjectPoolFileType) -> str:
    return {
        ProjectPoolFileType.ROAD_NETWORK: ".rd",
        ProjectPoolFileType.TRAFFIC_SCENARIO: ".xml",
        ProjectPoolFileType.TESTING_TEST: ".tst",
        ProjectPoolFileType.SIMULATION_CONFIGURATION: ".xml",
        ProjectPoolFileType.TRAFFIC_DRIVER: ".trd",
    }[file_type]


def _parse_environment_group(group: str | None) -> EnvironmentPoolGroup:
    if group is None or group.strip() == "":
        raise ValueError("Environment Pool group must not be empty. Use Objects, Road, Scenario, or Traffic Driver.")
    aliases = {
        "objects": EnvironmentPoolGroup.OBJECTS,
        "object": EnvironmentPoolGroup.OBJECTS,
        "trafficobjects": EnvironmentPoolGroup.OBJECTS,
        "traffic objects": EnvironmentPoolGroup.OBJECTS,
        "trafficobject": EnvironmentPoolGroup.OBJECTS,
        "traffic object": EnvironmentPoolGroup.OBJECTS,
        "tro": EnvironmentPoolGroup.OBJECTS,
        ".tro": EnvironmentPoolGroup.OBJECTS,
        "road": EnvironmentPoolGroup.ROAD,
        "roads": EnvironmentPoolGroup.ROAD,
        "roadnetwork": EnvironmentPoolGroup.ROAD,
        "road network": EnvironmentPoolGroup.ROAD,
        "roadnetworks": EnvironmentPoolGroup.ROAD,
        "road networks": EnvironmentPoolGroup.ROAD,
        "rd": EnvironmentPoolGroup.ROAD,
        ".rd": EnvironmentPoolGroup.ROAD,
        "scenario": EnvironmentPoolGroup.SCENARIO,
        "scenarios": EnvironmentPoolGroup.SCENARIO,
        "trafficscenario": EnvironmentPoolGroup.SCENARIO,
        "traffic scenario": EnvironmentPoolGroup.SCENARIO,
        "traffic scenarios": EnvironmentPoolGroup.SCENARIO,
        "xml": EnvironmentPoolGroup.SCENARIO,
        ".xml": EnvironmentPoolGroup.SCENARIO,
        "driver": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "drivers": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "trafficdriver": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "traffic driver": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "trafficdrivers": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "traffic drivers": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        "trd": EnvironmentPoolGroup.TRAFFIC_DRIVER,
        ".trd": EnvironmentPoolGroup.TRAFFIC_DRIVER,
    }
    normalized = group.strip().lower()
    compact = normalized.replace(" ", "")
    if normalized in aliases:
        return aliases[normalized]
    for item in EnvironmentPoolGroup:
        if compact == item.value.lower().replace(" ", ""):
            return item
    raise ValueError("Environment Pool group must be Objects, Road, Scenario, or Traffic Driver.")


def _parse_parameter_value_kind(value_kind: str | None) -> ParameterValueKind:
    if value_kind is None or value_kind.strip() == "":
        return ParameterValueKind.SCALAR
    return _parse_enum(value_kind, ParameterValueKind, "Value kind must be Scalar, Text, Vector, Matrix, or Table")


def _parse_parameter_com_value(value_kind: ParameterValueKind, value: Any) -> Any:
    if value_kind == ParameterValueKind.SCALAR:
        return _parse_scalar_value(value)
    if value_kind == ParameterValueKind.TEXT:
        if not isinstance(value, str):
            raise ValueError("Text parameter values must be JSON strings.")
        return value
    if value_kind == ParameterValueKind.VECTOR:
        return _parse_vector_value(value)
    if value_kind == ParameterValueKind.MATRIX:
        return _parse_matrix_value(value, MAX_MATRIX_ROWS, MAX_MATRIX_COLUMNS)
    if value_kind == ParameterValueKind.TABLE:
        return _parse_table_value(value)
    raise ValueError("Unsupported parameter value kind.")


def _parse_scalar_value(value: Any) -> float | str | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        try:
            numeric = float(value)
        except OverflowError as exc:
            raise ValueError("Scalar parameter number is outside the supported finite range.") from exc
        _validate_finite(numeric, "value")
        return numeric
    if isinstance(value, str):
        if value.strip() == "":
            raise ValueError("Scalar text values must not be empty.")
        try:
            numeric = float(value)
        except ValueError:
            return value
        _validate_finite(numeric, "value")
        return numeric
    raise ValueError("Scalar parameter values must be a JSON number, string, or boolean.")


def _parse_vector_value(value: Any) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise ValueError("Vector parameter values must be JSON arrays.")
    if len(value) > MAX_VECTOR_LENGTH:
        raise ValueError(f"Vector parameter values support at most {MAX_VECTOR_LENGTH} entries.")
    return tuple(_parse_finite_double(item, f"value[{index}]") for index, item in enumerate(value))


def _parse_matrix_value(value: Any, max_rows: int, max_columns: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list):
        raise ValueError("Matrix parameter values must be JSON arrays of row arrays.")
    if len(value) > max_rows:
        raise ValueError(f"Matrix parameter values support at most {max_rows} rows.")
    if len(value) == 0:
        return ()
    if not isinstance(value[0], list):
        raise ValueError("Matrix rows must be JSON arrays.")
    column_count = len(value[0])
    if column_count > max_columns:
        raise ValueError(f"Matrix parameter values support at most {max_columns} columns.")
    rows: list[tuple[float, ...]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list):
            raise ValueError(f"Matrix row {row_index} must be a JSON array.")
        if len(row) != column_count:
            raise ValueError("All matrix rows must have the same column count.")
        rows.append(tuple(_parse_finite_double(item, f"value[{row_index}][{column_index}]") for column_index, item in enumerate(row)))
    return tuple(rows)


def _parse_table_value(value: Any) -> tuple[tuple[float, ...], ...]:
    if isinstance(value, list):
        return _parse_matrix_value(value, MAX_TABLE_ROWS, MAX_TABLE_COLUMNS)
    if not isinstance(value, dict):
        raise ValueError("Table parameter values must be a row matrix or an object with rows and optional columns.")
    rows = _case_insensitive_get(value, "rows")
    if rows is None:
        raise ValueError("Table parameter objects must contain a rows array.")
    columns = _case_insensitive_get(value, "columns")
    if columns is not None:
        if not isinstance(columns, list):
            raise ValueError("Table columns must be a JSON string array.")
        if len(columns) > MAX_TABLE_COLUMNS:
            raise ValueError(f"Table values support at most {MAX_TABLE_COLUMNS} columns.")
        for index, column in enumerate(columns):
            if not isinstance(column, str) or column.strip() == "":
                raise ValueError(f"Table column {index} must be a non-empty string.")
        if isinstance(rows, list):
            for row_index, row in enumerate(rows):
                if isinstance(row, list) and len(row) != len(columns):
                    raise ValueError(f"Table row {row_index} must match the declared column count.")
    return _parse_matrix_value(rows, MAX_TABLE_ROWS, MAX_TABLE_COLUMNS)


def _parse_road_segment_type(segment_type: str | None, required: bool) -> RoadSegmentType | None:
    if segment_type is None or segment_type.strip() == "":
        if required:
            raise ValueError("Segment type must not be empty.")
        return None
    return _parse_enum(segment_type, RoadSegmentType, "Unsupported segment type")


def _parse_road_segment_properties(properties_json: str | None) -> RoadSegmentProperties:
    if properties_json is None or properties_json.strip() == "":
        return RoadSegmentProperties.empty()
    data = _parse_json_object(properties_json, "Segment properties JSON must be an object")
    return RoadSegmentProperties(
        name=_optional_text(_case_insensitive_get(data, "name")),
        length=_optional_float(_case_insensitive_get(data, "length")),
        radius=_optional_float(_case_insensitive_get(data, "radius")),
        angle=_optional_float(_case_insensitive_get(data, "angle")),
        is_infinite=_optional_bool(_case_insensitive_get(data, "isInfinite")),
        spline_definition_type=_optional_text(_case_insensitive_get(data, "splineDefinitionType")),
        relative_end_vector=_parse_vector_spec(_case_insensitive_get(data, "relativeEndVector")),
        absolute_end_vector=_parse_vector_spec(_case_insensitive_get(data, "absoluteEndVector")),
        spline_parameter_x=_parse_spline_parameter_spec(_case_insensitive_get(data, "splineParameterX")),
        spline_parameter_y=_parse_spline_parameter_spec(_case_insensitive_get(data, "splineParameterY")),
    )


def _parse_vector_spec(value: Any) -> RoadVectorSpec | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Spline vector values must be objects.")
    return RoadVectorSpec(
        x=_optional_float(_case_insensitive_get(value, "x")),
        y=_optional_float(_case_insensitive_get(value, "y")),
        tangent=_optional_float(_case_insensitive_get(value, "tangent")),
    )


def _parse_spline_parameter_spec(value: Any) -> RoadSplineParameterSpec | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Spline parameter values must be objects.")
    return RoadSplineParameterSpec(
        b=_optional_float(_case_insensitive_get(value, "b")),
        c=_optional_float(_case_insensitive_get(value, "c")),
        d=_optional_float(_case_insensitive_get(value, "d")),
    )


def _validate_road_segment_properties(properties: RoadSegmentProperties) -> None:
    _validate_optional_text(properties.name, "name")
    _validate_optional_positive_range(properties.length, MAX_ROAD_LENGTH, "length")
    _validate_optional_absolute_range(properties.radius, MAX_RADIUS, "radius", reject_zero=True)
    _validate_optional_absolute_range(properties.angle, MAX_ANGLE_DEGREES, "angle", reject_zero=False)
    _validate_spline_definition_type(properties.spline_definition_type)
    _validate_vector(properties.relative_end_vector, "relativeEndVector")
    _validate_vector(properties.absolute_end_vector, "absoluteEndVector")
    _validate_spline_parameter(properties.spline_parameter_x, "splineParameterX")
    _validate_spline_parameter(properties.spline_parameter_y, "splineParameterY")


def _validate_road_segment_properties_for_type(segment_type: RoadSegmentType, properties: RoadSegmentProperties) -> None:
    if segment_type != RoadSegmentType.CIRCULAR and properties.angle is not None:
        raise ValueError("Angle can only be set for Circular segments.")
    if segment_type not in (RoadSegmentType.CIRCULAR, RoadSegmentType.CLOTHOID) and properties.radius is not None:
        raise ValueError("Radius can only be set for Circular or Clothoid segments.")
    if segment_type != RoadSegmentType.CLOTHOID and properties.is_infinite is not None:
        raise ValueError("IsInfinite can only be set for Clothoid segments.")
    has_spline_property = any(
        item is not None
        for item in (
            properties.spline_definition_type,
            properties.relative_end_vector,
            properties.absolute_end_vector,
            properties.spline_parameter_x,
            properties.spline_parameter_y,
        )
    )
    if segment_type != RoadSegmentType.SPLINE and has_spline_property:
        raise ValueError("Spline properties can only be set for Spline segments.")
    if segment_type == RoadSegmentType.SPLINE and properties.length is not None:
        raise ValueError("Spline length is calculated by ModelDesk and cannot be set directly through Automation.")


def _validate_road_object_properties(properties: RoadObjectProperties) -> None:
    _validate_optional_text(properties.name, "name")
    _validate_optional_text(properties.catalog_path, "catalogPath")
    _validate_optional_finite_range(properties.s, 0.0, MAX_ROAD_LENGTH, "s")
    _validate_optional_finite(properties.d, "d")
    if properties.lane_mapping is not None:
        _validate_lane_mapping(properties.lane_mapping)


def _parse_basic_traffic_objects(traffic_objects_json: str | None) -> tuple[BasicRoadTrafficObjectSpec, ...]:
    if traffic_objects_json is None or traffic_objects_json.strip() == "":
        return ()
    try:
        data = json.loads(traffic_objects_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Traffic object JSON must be an array of objects: {exc.msg}") from exc
    if not isinstance(data, list):
        raise ValueError("Traffic object JSON must be an array of objects.")
    objects: list[BasicRoadTrafficObjectSpec] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Traffic object JSON must contain objects.")
        object_index = len(objects)
        objects.append(
            BasicRoadTrafficObjectSpec(
                name=_optional_text(_case_insensitive_get(item, "name")),
                catalog_path=_optional_text(_case_insensitive_get(item, "catalogPath")),
                s=_parse_finite_double(_case_insensitive_get(item, "s", 0.0), f"trafficObjects[{object_index}].s"),
                d=_parse_finite_double(_case_insensitive_get(item, "d", 0.0), f"trafficObjects[{object_index}].d"),
                lane_mapping=_optional_lane_mapping(_case_insensitive_get(item, "laneMapping")) or (),
            )
        )
    return tuple(objects)


def _validate_basic_traffic_object(traffic_object: BasicRoadTrafficObjectSpec, object_index: int, road_length: float) -> None:
    _validate_finite_range(traffic_object.s, 0.0, road_length, f"trafficObjects[{object_index}].s", exclusive_minimum=False)
    _validate_finite(traffic_object.d, f"trafficObjects[{object_index}].d")
    _validate_lane_mapping(traffic_object.lane_mapping)


def _parse_json_object(json_text: str, message: str) -> dict[str, Any]:
    try:
        data = json.loads(json_text, parse_constant=_reject_non_finite_json_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{message}: {exc.msg}") from exc
    except ValueError as exc:
        raise ValueError(f"{message}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(message)
    return data


def _parse_maneuver_behavior_profile_json(json_text: str | None, parameter_name: str) -> dict[str, Any]:
    if json_text is None or json_text.strip() == "":
        return {}
    try:
        data = json.loads(
            json_text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_non_finite_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"{parameter_name} must be valid JSON: {exc.msg}") from exc
    except ValueError as exc:
        raise ValueError(f"{parameter_name} is invalid: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{parameter_name} must be a JSON object.")
    return data


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"Duplicate JSON object key '{key}'.")
        data[key] = value
    return data


def _reject_non_finite_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number '{value}' is not supported.")


def _validate_finite_json_numbers(value: Any, parameter_name: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        try:
            is_finite = math.isfinite(value)
        except OverflowError as exc:
            raise ValueError(f"{parameter_name} contains a number outside the supported finite range.") from exc
        if not is_finite:
            raise ValueError(f"{parameter_name} must not contain non-finite numbers.")
        return
    if isinstance(value, dict):
        for nested_value in value.values():
            _validate_finite_json_numbers(nested_value, parameter_name)
    elif isinstance(value, list):
        for nested_value in value:
            _validate_finite_json_numbers(nested_value, parameter_name)


def _validate_ego_maneuver_properties(properties: dict[str, Any]) -> None:
    allowed_properties = {"StartPosition", "InitialLongitudinalVelocity"}
    for property_name, value in properties.items():
        if property_name not in allowed_properties:
            raise ValueError(
                "Ego longitudinalProfileJson supports only StartPosition and InitialLongitudinalVelocity."
            )
        _validate_maneuver_number(value, f"longitudinalProfileJson.{property_name}")


def _validate_fellow_longitudinal_properties(properties: dict[str, Any]) -> dict[str, Any]:
    if not properties:
        return properties
    if {"StartPosition", "InitialLongitudinalVelocity"}.intersection(properties):
        raise ValueError(
            "StartPosition and InitialLongitudinalVelocity are ego-only sequence properties, not fellow properties. "
            "Select the ego (active) or provide an explicit fellow Position or Velocity behavior profile."
        )
    if len(properties) != 1:
        raise ValueError(
            "A fellow segment supports only one longitudinal profile (Position or Velocity); "
            "Position and Velocity cannot be combined."
        )
    if set(properties) == {"Constant"}:
        raise ValueError(
            "Fellow Constant is ambiguous; explicitly select Position and YawAngleConstant, or Velocity and Constant."
        )

    profile_name, value = next(iter(properties.items()))
    source_name = {"Position": "YawAngleConstant", "Velocity": "Constant"}.get(profile_name)
    if source_name is None or not isinstance(value, dict):
        raise ValueError("A fellow longitudinal profile must select exactly one Position or Velocity profile.")

    source_properties = value
    if set(source_properties) != {source_name} or not isinstance(source_properties[source_name], dict):
        raise ValueError(f"A fellow {profile_name} profile must select exactly one {source_name} source.")

    constant_properties = source_properties[source_name]
    if set(constant_properties) != {"Constant"}:
        raise ValueError(f"The {source_name} source supports only its Constant property for this request.")
    _validate_maneuver_number(constant_properties["Constant"], f"longitudinalProfileJson.{profile_name}.{source_name}.Constant")
    return properties


def _validate_maneuver_number(value: Any, parameter_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{parameter_name} must be a finite JSON number.")
    try:
        is_finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f"{parameter_name} is outside the supported finite range.") from exc
    if not is_finite:
        raise ValueError(f"{parameter_name} must be a finite JSON number.")


def _validate_scalar_property_object(data: dict[str, Any], parameter_name: str, depth: int) -> None:
    if depth > 4:
        raise ValueError("Nested profile depth greater than 4 is not supported.")
    if len(data) > 64:
        raise ValueError("At most 64 properties are supported per JSON object.")
    for key, value in data.items():
        if not isinstance(key, str) or key.strip() == "":
            raise ValueError(f"{parameter_name} contains an invalid property name.")
        if isinstance(value, dict):
            _validate_scalar_property_object(value, parameter_name, depth + 1)
        elif isinstance(value, list):
            raise ValueError(f"Array values are not supported for property '{key}'.")
        elif isinstance(value, str | int | float | bool) or value is None:
            continue
        else:
            raise ValueError(f"Unsupported JSON value for property '{key}'.")


def _case_insensitive_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    for item_key, item_value in data.items():
        if item_key.lower() == key.lower():
            return item_value
    return default


def _has_key(data: dict[str, Any], key: str) -> bool:
    return any(item_key.lower() == key.lower() for item_key in data)


def _required_text(value: str | None, message: str) -> str:
    if value is None or value.strip() == "":
        raise ValueError(message)
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Text values must be strings.")
    if value.strip() == "":
        raise ValueError("Text values must be omitted or non-empty.")
    return value.strip()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Numeric values must be JSON numbers.")
    result = float(value)
    _validate_finite(result, "value")
    return result


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError("Boolean values must be JSON booleans.")
    return value


def _optional_lane_mapping(value: Any) -> tuple[int, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("Lane mapping must be an integer array.")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("Lane mapping must be an integer array.")
        result.append(item)
    _validate_lane_mapping(tuple(result))
    return tuple(result)


def _validate_lane_mapping(lane_mapping: tuple[int, ...]) -> None:
    if len(lane_mapping) > MAX_LANE_MAPPING_COUNT:
        raise ValueError(f"Lane mapping supports at most {MAX_LANE_MAPPING_COUNT} entries.")


def _validate_lane_count(lane_count: int, parameter_name: str) -> None:
    if lane_count < 0 or lane_count > MAX_LANE_COUNT_PER_SIDE:
        raise ValueError(f"{parameter_name} must be between 0 and {MAX_LANE_COUNT_PER_SIDE}.")


def _validate_finite(value: float, parameter_name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{parameter_name} must be finite.")


def _validate_finite_range(value: float, minimum: float, maximum: float, parameter_name: str, exclusive_minimum: bool) -> None:
    _validate_finite(value, parameter_name)
    minimum_valid = value > minimum if exclusive_minimum else value >= minimum
    if not minimum_valid or value > maximum:
        minimum_text = f"> {minimum}" if exclusive_minimum else f">= {minimum}"
        raise ValueError(f"{parameter_name} must be {minimum_text} and <= {maximum}.")


def _validate_optional_finite(value: float | None, parameter_name: str) -> None:
    if value is not None:
        _validate_finite(value, parameter_name)


def _validate_optional_finite_range(value: float | None, minimum: float, maximum: float, parameter_name: str) -> None:
    if value is not None:
        _validate_finite_range(value, minimum, maximum, parameter_name, exclusive_minimum=False)


def _validate_optional_positive_range(value: float | None, maximum: float, parameter_name: str) -> None:
    if value is not None:
        _validate_finite_range(value, 0.0, maximum, parameter_name, exclusive_minimum=True)


def _validate_optional_absolute_range(value: float | None, maximum_absolute_value: float, parameter_name: str, reject_zero: bool) -> None:
    if value is None:
        return
    _validate_finite(value, parameter_name)
    if reject_zero and abs(value) <= sys_float_epsilon():
        raise ValueError(f"{parameter_name} must not be zero.")
    if abs(value) > maximum_absolute_value:
        raise ValueError(f"{parameter_name} absolute value must be <= {maximum_absolute_value}.")


def _validate_optional_text(value: str | None, parameter_name: str) -> None:
    if value is not None and value.strip() == "":
        raise ValueError(f"{parameter_name} must be omitted or non-empty.")


def _validate_spline_definition_type(value: str | None) -> None:
    if value is None:
        return
    normalized = value.strip().lower()
    if normalized not in ("endvector", "parameterbased"):
        raise ValueError("SplineDefinitionType must be EndVector or ParameterBased.")


def _validate_vector(vector: RoadVectorSpec | None, parameter_name: str) -> None:
    if vector is None:
        return
    _validate_optional_absolute_range(vector.x, MAX_COORDINATE, f"{parameter_name}.x", reject_zero=False)
    _validate_optional_absolute_range(vector.y, MAX_COORDINATE, f"{parameter_name}.y", reject_zero=False)
    _validate_optional_absolute_range(vector.tangent, MAX_ANGLE_DEGREES, f"{parameter_name}.tangent", reject_zero=False)


def _validate_spline_parameter(parameter: RoadSplineParameterSpec | None, parameter_name: str) -> None:
    if parameter is None:
        return
    _validate_optional_absolute_range(parameter.b, MAX_COORDINATE, f"{parameter_name}.b", reject_zero=False)
    _validate_optional_absolute_range(parameter.c, MAX_COORDINATE, f"{parameter_name}.c", reject_zero=False)
    _validate_optional_absolute_range(parameter.d, MAX_COORDINATE, f"{parameter_name}.d", reject_zero=False)


def _parse_finite_double(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} must be a JSON number.")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{path} is outside the supported finite range.") from exc
    _validate_finite(result, path)
    return result


def sys_float_epsilon() -> float:
    """Return a small positive epsilon used for zero checks."""

    return 2.220446049250313e-16
