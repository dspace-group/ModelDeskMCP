"""Tests for road authoring request validation."""

from types import SimpleNamespace

import pytest

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import BasicRoadCreationRequest, RoadObjectProperties, RoadSegmentEditRequest, RoadSegmentType, Selector


class _InlineDispatcher:
    def invoke(self, operation, timeout_seconds):
        return operation()


class _FakeCollection:
    def __init__(self, items):
        self.items = items

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index]


class _FakeActiveSegment:
    _type_ids = {"Straight": 0, "Circular": 1, "Clothoid": 2, "Spline": 3}

    def __init__(self, segment_type: str) -> None:
        vector = SimpleNamespace(X=0.0, Y=0.0, Tangent=0.0)
        parameter_x = SimpleNamespace(B=0.0, C=0.0, D=0.0)
        parameter_y = SimpleNamespace(B=0.0, C=0.0, D=0.0)
        self.typed_segment = SimpleNamespace(
            Name="Segment",
            Type=self._type_ids[segment_type],
            Index=0,
            S=0.0,
            Length=0.0,
            Radius=0.0,
            Angle=0.0,
            IsInfinite=False,
            DefintionType=0,
            RelativeEndVector=vector,
            AbsoluteEndVector=SimpleNamespace(X=0.0, Y=0.0, Tangent=0.0),
            Parameters=SimpleNamespace(X=parameter_x, Y=parameter_y),
        )

    def Activate(self, segment_type: str):
        self.typed_segment.Type = self._type_ids[segment_type]
        return self.typed_segment


class _FakeSegmentCollection(_FakeCollection):
    def Add(self, segment_type: str) -> _FakeActiveSegment:
        segment = _FakeActiveSegment(segment_type)
        self.items.append(segment)
        return segment


class _FakeLaneCollection(_FakeCollection):
    def Add(self, side: int):
        if side == 0:
            lane_index = max((lane.LaneIndex for lane in self.items if lane.LaneIndex > 0), default=0) + 1
        else:
            lane_index = min((lane.LaneIndex for lane in self.items if lane.LaneIndex < 0), default=0) - 1
        lane = SimpleNamespace(LaneIndex=lane_index, Width=0.0)
        self.items.append(lane)
        return lane

    def Remove(self, side: int) -> bool:
        lane_candidates = [lane for lane in self.items if (lane.LaneIndex > 0) == (side == 0)]
        lane = max(lane_candidates, key=lambda item: abs(item.LaneIndex))
        self.items.remove(lane)
        return True


class _FakeRoadObjects(_FakeCollection):
    def Add(self, s: float, d: float):
        road_object = SimpleNamespace(
            Name=None,
            Position=SimpleNamespace(S=s, D=d),
            LaneMapping=[],
            LaneMappingEnabled=False,
        )
        self.items.append(road_object)
        return road_object


class _FakeRoadCollection(_FakeCollection):
    def __init__(self, items, road_factory) -> None:
        super().__init__(items)
        self.road_factory = road_factory

    def Add(self):
        road = self.road_factory()
        self.items.append(road)
        return road

    def Remove(self, road) -> bool:
        self.items.remove(road)
        return True


class _FakeConnectionPoint:
    def __init__(self, point_type: int) -> None:
        self.Type = point_type
        self.move_targets = []
        self.modify_targets = []

    def MoveAndConnect(self, target) -> bool:
        self.move_targets.append(target)
        return True

    def ModifyAndConnect(self, target) -> bool:
        self.modify_targets.append(target)
        return True


def _gateway_with_active_road(road) -> ModelDeskAutomationGateway:
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(
            ActiveExperiment=SimpleNamespace(Road=SimpleNamespace(Roads=_FakeCollection([road])))
        )
    )
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]
    return gateway


def test_add_straight_segment_request_accepts_length() -> None:
    request = RoadSegmentEditRequest.create("Straight", '{"length": 100}', -1, False, False, True)

    assert request.segment_type == RoadSegmentType.STRAIGHT
    assert request.properties.length == 100.0


def test_straight_segment_rejects_radius() -> None:
    with pytest.raises(ValueError):
        RoadSegmentEditRequest.create("Straight", '{"radius": 50}', -1, False, False, True)


def test_lane_mapping_validation() -> None:
    properties = RoadObjectProperties.create('{"laneMapping": [1, -1]}')

    assert properties.lane_mapping == (1, -1)


def test_basic_road_requires_at_least_one_lane() -> None:
    with pytest.raises(ValueError):
        BasicRoadCreationRequest.create("Road", 100.0, 0, 0, 3.5, "[]", False, False)


def test_basic_road_accepts_traffic_objects() -> None:
    request = BasicRoadCreationRequest.create(
        "Road",
        100.0,
        1,
        1,
        3.5,
        '[{"name":"Cone","s":25,"d":1.75,"laneMapping":[1]}]',
        False,
        False,
    )

    assert len(request.traffic_objects) == 1
    assert request.traffic_objects[0].lane_mapping == (1,)


@pytest.mark.parametrize(
    "traffic_objects_json",
    (
        '[{"s":true}]',
        '[{"d":false}]',
        '[{"s":"25.0"}]',
        '[{"d":"1.75"}]',
    ),
)
def test_basic_road_rejects_non_numeric_traffic_object_coordinates(traffic_objects_json: str) -> None:
    with pytest.raises(ValueError, match="JSON number"):
        BasicRoadCreationRequest.create("Road", 100.0, 1, 1, 3.5, traffic_objects_json, False, False)


def test_update_road_object_does_not_hide_partial_mutation_on_invalid_position() -> None:
    road_object = SimpleNamespace(Name="Original", Position=SimpleNamespace(S=10.0, D=0.0))
    road = SimpleNamespace(Name="Road", Length=100.0, Objects=_FakeCollection([road_object]))
    road_network = SimpleNamespace(Roads=_FakeCollection([road]))
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(ActiveExperiment=SimpleNamespace(Road=road_network))
    )
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]

    result = gateway.update_road_object(
        Selector.create("index", "0"),
        0,
        '{"name":"Renamed","s":150}',
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    unchanged = road_object.Name == "Original"
    partial_change_is_reported = road_object.Name == "Renamed" and any(
        marker in result.error.message.lower() for marker in ("partial", "not rolled back")
    )
    assert unchanged or partial_change_is_reported


@pytest.mark.parametrize(
    ("segment_type", "properties_json", "expected_values"),
    (
        ("Straight", '{"length":50}', {"length": 50.0}),
        ("Circular", '{"length":40,"radius":25,"angle":90}', {"length": 40.0, "radius": 25.0, "angle": 90.0}),
        ("Clothoid", '{"length":60,"radius":75,"isInfinite":true}', {"length": 60.0, "radius": 75.0, "isInfinite": True}),
        (
            "Spline",
            '{"splineDefinitionType":"EndVector","relativeEndVector":{"x":80,"y":4,"tangent":0.5}}',
            {"definitionType": 0, "relativeEndVector": (80.0, 4.0, 0.5)},
        ),
        (
            "Spline",
            '{"splineDefinitionType":"ParameterBased","splineParameterX":{"b":1,"c":2,"d":3},"splineParameterY":{"b":4,"c":5,"d":6}}',
            {"definitionType": 1, "parameterX": (1.0, 2.0, 3.0), "parameterY": (4.0, 5.0, 6.0)},
        ),
    ),
)
def test_add_road_segment_applies_source_defined_geometry_members(
    segment_type: str,
    properties_json: str,
    expected_values: dict[str, object],
) -> None:
    segments = _FakeSegmentCollection([])
    road = SimpleNamespace(Name="Road", Length=100.0, Segments=segments)
    gateway = _gateway_with_active_road(road)

    result = gateway.add_road_segment(
        Selector.create("index", "0"),
        segment_type,
        properties_json,
        insert_after_segment_index=-1,
        save=False,
        download=False,
    )

    assert result.ok
    typed_segment = segments.items[0].typed_segment
    assert typed_segment.Type == _FakeActiveSegment._type_ids[segment_type]
    if "length" in expected_values:
        assert typed_segment.Length == expected_values["length"]
    if "radius" in expected_values:
        assert typed_segment.Radius == expected_values["radius"]
    if "angle" in expected_values:
        assert typed_segment.Angle == expected_values["angle"]
    if "isInfinite" in expected_values:
        assert typed_segment.IsInfinite is expected_values["isInfinite"]
    if "definitionType" in expected_values:
        assert typed_segment.DefintionType == expected_values["definitionType"]
    if "relativeEndVector" in expected_values:
        vector = typed_segment.RelativeEndVector
        assert (vector.X, vector.Y, vector.Tangent) == expected_values["relativeEndVector"]
    if "parameterX" in expected_values:
        parameter = typed_segment.Parameters.X
        assert (parameter.B, parameter.C, parameter.D) == expected_values["parameterX"]
    if "parameterY" in expected_values:
        parameter = typed_segment.Parameters.Y
        assert (parameter.B, parameter.C, parameter.D) == expected_values["parameterY"]


def test_configure_road_lanes_updates_section_counts_widths_and_length() -> None:
    lanes = _FakeLaneCollection([SimpleNamespace(LaneIndex=1, Width=3.5), SimpleNamespace(LaneIndex=-1, Width=3.5)])
    lane_section = SimpleNamespace(Name="Section 0", Length=20.0, Lanes=lanes)
    road = SimpleNamespace(Name="Road", Length=100.0, LaneSections=_FakeCollection([lane_section]))
    gateway = _gateway_with_active_road(road)

    result = gateway.configure_road_lanes(
        Selector.create("index", "0"),
        lane_section_index=0,
        left_lane_count=2,
        right_lane_count=1,
        lane_width=3.7,
        lane_section_length=0.0,
        save=False,
        download=False,
    )

    assert result.ok
    assert sorted(lane.LaneIndex for lane in lanes.items) == [-1, 1, 2]
    assert all(lane.Width == 3.7 for lane in lanes.items)
    details = result.to_dict()["data"]["details"]
    assert details["leftLaneCount"] == "2"
    assert details["rightLaneCount"] == "1"
    assert details["laneSectionLength"] == "100.0"


def test_add_road_object_uses_road_relative_s_d_and_reads_them_back() -> None:
    road_objects = _FakeRoadObjects([])
    road = SimpleNamespace(Name="Road", Length=100.0, Objects=road_objects)
    gateway = _gateway_with_active_road(road)

    result = gateway.add_road_object(
        Selector.create("index", "0"),
        s=25.0,
        d=-1.75,
        name="Marker",
        catalog_path=None,
        lane_mapping_json="[1]",
        save=False,
        download=False,
    )

    assert result.ok
    assert road_objects.Count == 1
    road_object = road_objects.items[0]
    assert (road_object.Position.S, road_object.Position.D) == (25.0, -1.75)
    assert road_object.Name == "Marker"
    assert road_object.LaneMapping == [1]
    details = result.to_dict()["data"]["details"]
    assert details["s"] == "25.0"
    assert details["d"] == "-1.75"


def test_add_road_object_rejects_position_after_road_length_without_mutation() -> None:
    road_objects = _FakeRoadObjects([])
    road = SimpleNamespace(Name="Road", Length=100.0, Objects=road_objects)
    gateway = _gateway_with_active_road(road)

    result = gateway.add_road_object(
        Selector.create("index", "0"),
        s=101.0,
        d=0.0,
        name="OutOfBounds",
        catalog_path=None,
        lane_mapping_json="[]",
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert road_objects.Count == 0


def test_road_subobject_removal_dry_runs_do_not_mutate_or_persist() -> None:
    events: list[str] = []
    segment = SimpleNamespace(ActiveElement=SimpleNamespace(Name="Segment A"))
    segments = _FakeSegmentCollection([segment])
    road_object = SimpleNamespace(Name="Sign")
    road_objects = _FakeRoadObjects([road_object])

    class ConnectionPoint:
        Type = 1

        def Disconnect(self) -> bool:
            events.append("disconnect")
            return True

    connection_point = ConnectionPoint()
    road = SimpleNamespace(
        Name="Road",
        Length=100.0,
        Segments=segments,
        Objects=road_objects,
        ConnectionPoints=_FakeCollection([connection_point]),
    )
    gateway = _gateway_with_active_road(road)
    selector = Selector.create("index", "0")

    segment_preview = gateway.remove_road_segment(selector, 0, save=True, download=True, dry_run=True)
    object_preview = gateway.remove_road_object(selector, 0, save=True, download=True, dry_run=True)
    disconnect_preview = gateway.disconnect_road(selector, "End", save=True, download=True, dry_run=True)

    assert segment_preview.ok
    assert segment_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert object_preview.ok
    assert object_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert disconnect_preview.ok
    assert disconnect_preview.to_dict()["data"]["details"]["wouldSave"] == "true"
    assert segments.items == [segment]
    assert road_objects.items == [road_object]
    assert events == []


def test_connect_roads_maps_end_to_start_and_invokes_move_connection() -> None:
    source_start = _FakeConnectionPoint(0)
    source_end = _FakeConnectionPoint(1)
    target_start = _FakeConnectionPoint(0)
    target_end = _FakeConnectionPoint(1)
    source_road = SimpleNamespace(Name="Source", ConnectionPoints=_FakeCollection([source_start, source_end]))
    target_road = SimpleNamespace(Name="Target", ConnectionPoints=_FakeCollection([target_start, target_end]))
    road_network = SimpleNamespace(Roads=_FakeCollection([source_road, target_road]))
    application = SimpleNamespace(ActiveProject=SimpleNamespace(ActiveExperiment=SimpleNamespace(Road=road_network)))
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]

    result = gateway.connect_roads(
        Selector.create("index", "0"),
        "End",
        Selector.create("index", "1"),
        "Start",
        "Move",
        save=False,
        download=False,
    )
    modified = gateway.connect_roads(
        Selector.create("index", "0"),
        "End",
        Selector.create("index", "1"),
        "Start",
        "Modify",
        save=False,
        download=False,
    )

    assert result.ok
    assert modified.ok
    assert source_end.move_targets == [target_start]
    assert source_end.modify_targets == [target_start]
    assert source_start.move_targets == []
    assert result.to_dict()["data"]["details"]["sourcePoint"] == "End"
    assert result.to_dict()["data"]["details"]["targetPoint"] == "Start"


def test_road_crud_save_download_and_save_as_use_active_network(tmp_path) -> None:
    persistence_calls: list[str] = []

    def create_road():
        lane_section = SimpleNamespace(Name="Section 0", Length=0.0, Lanes=_FakeLaneCollection([]))
        return SimpleNamespace(
            Name="Road",
            Length=100.0,
            LaneSections=_FakeCollection([lane_section]),
            Segments=_FakeSegmentCollection([]),
            Objects=_FakeRoadObjects([]),
        )

    class FakeRoadNetwork:
        def __init__(self) -> None:
            self.Roads = _FakeRoadCollection([], create_road)
            self.save_as_call = None

        def Save(self) -> bool:
            persistence_calls.append("save")
            return True

        def Download(self) -> bool:
            persistence_calls.append("download")
            return True

        def SaveAs(self, path: str, overwrite_existing: bool) -> None:
            self.save_as_call = (path, overwrite_existing)

    road_network = FakeRoadNetwork()
    gateway = _gateway_with_active_road(SimpleNamespace())
    gateway._application.ActiveProject.ActiveExperiment.Road = road_network

    added = gateway.add_road("Created", 1, 1, 3.5, save=True, download=True)
    listed = gateway.list_roads()
    renamed = gateway.update_road(Selector.create("index", "0"), "Renamed", save=False, download=False)
    preview_path = tmp_path / "existing-road-network.rd"
    preview_path.write_text("existing", encoding="utf-8")
    preview = gateway.save_road_network_as(str(preview_path), overwrite_existing=True, dry_run=True)
    assert preview.ok
    preview_details = preview.to_dict()["data"]["details"]
    assert preview_details["dryRun"] == "true"
    assert preview_details["targetExists"] == "true"
    assert preview_details["wouldOverwrite"] == "true"
    assert road_network.save_as_call is None

    save_as_path = tmp_path / "road-network.rd"
    saved_as = gateway.save_road_network_as(str(save_as_path), overwrite_existing=False)

    assert added.ok
    assert listed.to_dict()["data"]["items"][0]["name"] == "Created"
    assert renamed.ok
    assert road_network.Roads.items[0].Name == "Renamed"
    assert saved_as.ok
    assert road_network.save_as_call == (str(save_as_path.resolve()), False)

<<<<<<< Updated upstream
    preview = gateway.remove_road(Selector.create("index", "0"), save=False, download=False, dry_run=True)

    assert preview.ok
    assert preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert road_network.Roads.Count == 1
=======
    calls_before_preview = list(persistence_calls)
    roads_before_preview = road_network.Roads.Count
    removal_preview = gateway.remove_road(Selector.create("index", "0"), save=True, download=True, dry_run=True)

    assert removal_preview.ok
    preview_details = removal_preview.to_dict()["data"]["details"]
    assert preview_details["dryRun"] == "true"
    assert preview_details["wouldSave"] == "true"
    assert preview_details["wouldDownload"] == "true"
    assert road_network.Roads.Count == roads_before_preview
    assert persistence_calls == calls_before_preview
>>>>>>> Stashed changes

    removed = gateway.remove_road(Selector.create("index", "0"), save=False, download=False)

    assert removed.ok
    assert road_network.Roads.Count == 0
    assert persistence_calls == ["save", "download"]
