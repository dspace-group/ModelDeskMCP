"""Tests for road authoring request validation."""

import pytest

from modeldesk_mcp.contracts import BasicRoadCreationRequest, RoadObjectProperties, RoadSegmentEditRequest, RoadSegmentType


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