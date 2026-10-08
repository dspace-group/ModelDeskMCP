"""Enum definitions used by ModelDesk MCP contracts."""

from __future__ import annotations

from enum import Enum, IntEnum


class SelectorKind(Enum):
    """Identifies how a COM collection item should be selected."""

    ACTIVE = "Active"
    INDEX = "Index"
    NAME = "Name"
    PATH = "Path"
    COMPLETE_NAME = "CompleteName"
    ID = "Id"


class ParameterValueKind(Enum):
    """Identifies supported parameter value shapes."""

    SCALAR = "Scalar"
    TEXT = "Text"
    VECTOR = "Vector"
    MATRIX = "Matrix"
    TABLE = "Table"


class ProjectPoolFileType(IntEnum):
    """Identifies file kinds supported by ActiveProject.Pool.CreateFile."""

    ROAD_NETWORK = 0
    TRAFFIC_SCENARIO = 1
    TESTING_TEST = 2
    SIMULATION_CONFIGURATION = 3
    TRAFFIC_DRIVER = 4

    @property
    def display_name(self) -> str:
        """Return the .NET-compatible display name."""

        return {
            ProjectPoolFileType.ROAD_NETWORK: "RoadNetwork",
            ProjectPoolFileType.TRAFFIC_SCENARIO: "TrafficScenario",
            ProjectPoolFileType.TESTING_TEST: "TestingTest",
            ProjectPoolFileType.SIMULATION_CONFIGURATION: "LayoutConfiguration",
            ProjectPoolFileType.TRAFFIC_DRIVER: "TrafficDriver",
        }[self]


class EnvironmentPoolGroup(Enum):
    """Identifies supported Environment Pool groups."""

    OBJECTS = "Objects"
    ROAD = "Road"
    SCENARIO = "Scenario"
    TRAFFIC_DRIVER = "TrafficDriver"


class ModelDeskDomain(Enum):
    """Identifies ModelDesk functional domains exposed through MCP."""

    PROJECT = "Project"
    EXPERIMENTS = "Experiments"
    PARAMETERIZATION = "Parameterization"
    ROADS = "Roads"
    SCENARIOS = "Scenarios"
    TRAFFIC_OBJECTS = "TrafficObjects"
    PROCESSING = "Processing"
    TESTING = "Testing"
    PLOTTING = "Plotting"
    COMPARISON = "Comparison"
    WORKFLOW = "Workflow"


class RoadSegmentType(IntEnum):
    """Identifies supported road segment types."""

    STRAIGHT = 0
    CIRCULAR = 1
    CLOTHOID = 2
    SPLINE = 3

    @property
    def display_name(self) -> str:
        """Return the ModelDesk COM display name."""

        return {
            RoadSegmentType.STRAIGHT: "Straight",
            RoadSegmentType.CIRCULAR: "Circular",
            RoadSegmentType.CLOTHOID: "Clothoid",
            RoadSegmentType.SPLINE: "Spline",
        }[self]


class RoadConnectionPointKind(IntEnum):
    """Identifies a road connection point."""

    START = 0
    END = 1

    @property
    def display_name(self) -> str:
        """Return the ModelDesk COM display name."""

        return "Start" if self == RoadConnectionPointKind.START else "End"


class RoadConnectionMode(Enum):
    """Identifies the strategy used when connecting roads."""

    MOVE = "Move"
    MODIFY = "Modify"
