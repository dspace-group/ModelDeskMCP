"""Tests for scenario and vehicle object type tool input validation."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector, SelectorKind
from modeldesk_mcp.contracts.models import ToolResult


def _make_gateway() -> ModelDeskAutomationGateway:
    return ModelDeskAutomationGateway(ComStaDispatcher(), ComGatewayOptions())


def test_set_scenario_road_rejects_empty_road_name() -> None:
    gateway = _make_gateway()

    result = gateway.set_scenario_road("", save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


def test_set_scenario_road_rejects_whitespace_only_road_name() -> None:
    gateway = _make_gateway()

    result = gateway.set_scenario_road("   ", save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


def test_set_vehicle_object_type_rejects_negative_element_index() -> None:
    gateway = _make_gateway()
    ego_selector = Selector.create(None, None)

    result = gateway.set_vehicle_object_type(ego_selector, maneuver_index=0, element_index=-1, save=False, download=False)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


def test_scenario_activation_and_maneuver_controls_use_source_defined_methods() -> None:
    calls: list[tuple[str, object]] = []

    class FakeManeuverControl:
        def Start(self, download_if_not_running: bool) -> bool:
            calls.append(("Start", download_if_not_running))
            return True

        def Stop(self) -> bool:
            calls.append(("Stop", True))
            return True

        def Reset(self) -> bool:
            calls.append(("Reset", True))
            return True

    class FakeExperiment:
        ManeuverControl = FakeManeuverControl()

        def ActivateTrafficScenario(self, name: str) -> None:
            calls.append(("ActivateTrafficScenario", name))

    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = SimpleNamespace(  # type: ignore[attr-defined]
        ActiveProject=SimpleNamespace(ActiveExperiment=FakeExperiment())
    )

    activation = gateway.activate_scenario("Scenario A")
    start = gateway.start_maneuver(download_if_not_running=True)
    stop = gateway.stop_maneuver()
    reset = gateway.reset_maneuver()

    assert all(result.ok for result in (activation, start, stop, reset))
    assert calls == [
        ("ActivateTrafficScenario", "Scenario A"),
        ("Start", True),
        ("Stop", True),
        ("Reset", True),
    ]


class _FakeGateway:
    """Minimal gateway stub that records calls and returns a canned success result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.session_id = "test-session"

    def _record(self, name: str, *args: Any) -> ToolResult:
        self.calls.append((name, args))
        return ToolResult.success(name, "test-session", {})

    def get_scenario_road(self) -> ToolResult:
        return self._record("get_scenario_road")

    def set_scenario_road(self, road_name: str, save: bool, download: bool) -> ToolResult:
        return self._record("set_scenario_road", road_name, save, download)

    def list_fellow_activities(self, fellow_selector: Selector) -> ToolResult:
        return self._record("list_fellow_activities", fellow_selector)

    def get_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int) -> ToolResult:
        return self._record("get_vehicle_object_type", fellow_selector, maneuver_index)

    def list_vehicle_object_types(self, fellow_selector: Selector, maneuver_index: int) -> ToolResult:
        return self._record("list_vehicle_object_types", fellow_selector, maneuver_index)

    def set_vehicle_object_type(self, fellow_selector: Selector, maneuver_index: int, element_index: int, save: bool, download: bool) -> ToolResult:
        return self._record("set_vehicle_object_type", fellow_selector, maneuver_index, element_index, save, download)


def _make_service(fake_gateway: _FakeGateway) -> Any:
    from modeldesk_mcp.domain.service import ModelDeskService

    service = object.__new__(ModelDeskService)
    service._gateway = fake_gateway  # type: ignore[attr-defined]
    return service


def test_service_list_fellow_activities_passes_active_selector_for_ego() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("active", "active")

    assert result.ok
    assert len(fake.calls) == 1
    name, args = fake.calls[0]
    assert name == "list_fellow_activities"
    selector: Selector = args[0]
    assert selector.by == SelectorKind.ACTIVE


def test_service_list_fellow_activities_passes_index_selector_for_fellow() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("index", "2")

    assert result.ok
    name, args = fake.calls[0]
    selector: Selector = args[0]
    assert selector.by == SelectorKind.INDEX
    assert selector.to_com_value() == 2


def test_service_list_fellow_activities_rejects_invalid_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_fellow_activities("name", "")

    assert not result.ok
    assert len(fake.calls) == 0


def test_service_get_vehicle_object_type_routes_maneuver_index() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    service.get_vehicle_object_type("active", "active", 3)

    name, args = fake.calls[0]
    assert name == "get_vehicle_object_type"
    assert args[1] == 3


def test_set_vehicle_object_type_rejects_invalid_fellow_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.set_vehicle_object_type("name", "", 0, 0, False, False)

    assert not result.ok
    assert len(fake.calls) == 0


# --- SAFEARRAY regression tests ---
# AvailableElements may return a Python tuple (COM SAFEARRAY) instead of a COM
# collection object. The helpers _available_type_elements and
# _summarize_type_elements must handle both cases without AttributeError.

def test_available_type_elements_handles_python_tuple() -> None:
    from modeldesk_mcp.com_bridge.gateway import _available_type_elements, _summarize_type_elements

    class _FakeTypeManager:
        AvailableElements = ("elem0", "elem1", "elem2")

    elements = _available_type_elements(_FakeTypeManager())

    assert elements == ["elem0", "elem1", "elem2"]


def test_summarize_type_elements_builds_domain_summary_from_list() -> None:
    from modeldesk_mcp.com_bridge.gateway import _summarize_type_elements
    from modeldesk_mcp.contracts.models import DomainSummary

    elements = ["elem0", "elem1"]
    result = _summarize_type_elements("scenarios.objectTypes.ego", elements, "object type", 500)

    assert isinstance(result, DomainSummary)
    assert result.count == 2
    assert len(result.items) == 2
    assert result.items[0].index == 0
    assert result.items[1].index == 1


def test_summarize_type_elements_truncates_at_max_items() -> None:
    from modeldesk_mcp.com_bridge.gateway import _summarize_type_elements

    elements = list(range(10))
    result = _summarize_type_elements("domain", elements, "type", 3)

    assert result.count == 10
    assert len(result.items) == 3
    assert result.message is not None


# --- Fellow name-selector regression tests ---
# ModelDesk's Fellows.Item(string)/Remove(string) only match CompleteName
# ("F{Index}: {Name}") or "F{Index}", never the plain Name that
# modeldesk_list_scenario_fellows exposes as a name selector value. These
# helpers must translate a plain-name selector to the fellow's 0-based
# collection position before any COM call is made.

class _FakeFellow:
    def __init__(self, name: str) -> None:
        self.Name = name


class _FakeFellowsCollection:
    def __init__(self, names: list[str]) -> None:
        self._fellows = [_FakeFellow(name) for name in names]

    @property
    def Count(self) -> int:
        return len(self._fellows)

    def Item(self, index: int) -> _FakeFellow:
        return self._fellows[index]


def test_resolve_fellow_index_by_name_finds_matching_plain_name() -> None:
    from modeldesk_mcp.com_bridge.gateway import _resolve_fellow_index_by_name

    fellows = _FakeFellowsCollection(["Truck1", "MCP_UC3_TestFellow"])

    assert _resolve_fellow_index_by_name(fellows, "MCP_UC3_TestFellow") == 1


def test_resolve_fellow_index_by_name_raises_for_unknown_name() -> None:
    from modeldesk_mcp.com_bridge.gateway import _resolve_fellow_index_by_name

    fellows = _FakeFellowsCollection(["Truck1"])

    try:
        _resolve_fellow_index_by_name(fellows, "DoesNotExist")
        raise AssertionError("Expected RuntimeError for an unknown fellow name.")
    except RuntimeError:
        pass


def test_resolve_fellow_translates_name_selector_to_matching_fellow() -> None:
    from modeldesk_mcp.com_bridge.gateway import _resolve_fellow

    fellows = _FakeFellowsCollection(["Truck1", "MCP_UC3_TestFellow"])
    selector = Selector(SelectorKind.NAME, "MCP_UC3_TestFellow")

    fellow = _resolve_fellow(fellows, selector)

    assert fellow.Name == "MCP_UC3_TestFellow"


def test_fellow_selector_to_index_selector_translates_name_to_index() -> None:
    from modeldesk_mcp.com_bridge.gateway import _fellow_selector_to_index_selector

    fellows = _FakeFellowsCollection(["Truck1", "MCP_UC3_TestFellow"])
    selector = Selector(SelectorKind.NAME, "MCP_UC3_TestFellow")

    index_selector = _fellow_selector_to_index_selector(fellows, selector)

    assert index_selector.by == SelectorKind.INDEX
    assert index_selector.to_com_value() == 1


def test_fellow_selector_to_index_selector_passes_through_index_selector() -> None:
    from modeldesk_mcp.com_bridge.gateway import _fellow_selector_to_index_selector

    fellows = _FakeFellowsCollection(["Truck1"])
    selector = Selector(SelectorKind.INDEX, "0")

    index_selector = _fellow_selector_to_index_selector(fellows, selector)

    assert index_selector is selector


class _InlineDispatcher:
    def invoke(self, operation: Any, timeout_seconds: float) -> Any:
        return operation()


class _FakeComCollection:
    def __init__(self, items: list[Any] | None = None, add_factory: Any = None) -> None:
        self.items = list(items or [])
        self._add_factory = add_factory
        self.item_calls = 0

    @property
    def Count(self) -> int:
        return len(self.items)

    def Item(self, selector: int) -> Any:
        self.item_calls += 1
        return self.items[selector]

    def Add(self) -> Any:
        item = self._add_factory()
        self.items.append(item)
        return item


def _gateway_for_application(application: Any) -> ModelDeskAutomationGateway:
    gateway = _make_gateway()
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[assignment]
    gateway._application = application
    return gateway


class _FakeProfileValue:
    def __init__(self, name: str, constant: float, events: list[tuple[str, str]]) -> None:
        self.name = name
        self._constant = constant
        self.readback_override: float | None = None
        self.readback_error: Exception | None = None
        self.setter_error: Exception | None = None
        self.events = events

    @property
    def Constant(self) -> float:
        self.events.append((self.name, "read:Constant"))
        if self.readback_error is not None:
            raise self.readback_error
        return self._constant if self.readback_override is None else self.readback_override

    @Constant.setter
    def Constant(self, value: float) -> None:
        self.events.append((self.name, "set:Constant"))
        if self.setter_error is not None:
            raise self.setter_error
        self._constant = value


class _FakeProfileSelection:
    def __init__(self, name: str, elements: dict[str, Any], active_name: str, events: list[tuple[str, str]]) -> None:
        self.name = name
        self.elements = elements
        self.active_name = active_name
        self.events = events

    @property
    def AvailableElements(self) -> tuple[str, ...]:
        self.events.append((self.name, "available"))
        return tuple(self.elements)

    @property
    def ActiveElement(self) -> Any:
        return self.elements[self.active_name]

    def Activate(self, element_name: str) -> Any:
        assert element_name in self.AvailableElements
        self.events.append((self.name, f"activate:{element_name}"))
        self.active_name = element_name
        return self.ActiveElement


def _make_fellow_profile_context() -> SimpleNamespace:
    events: list[tuple[str, str]] = []
    velocity_value = _FakeProfileValue("velocity", 25.0, events)
    position_value = _FakeProfileValue("position", 0.0, events)
    velocity_source = _FakeProfileSelection("velocity-source", {"Constant": velocity_value}, "Constant", events)
    velocity_profile = type("FakeVelocityProfile", (), {"SourceType": velocity_source})()
    position_source = _FakeProfileSelection("source", {"YawAngleConstant": position_value}, "YawAngleConstant", events)
    position_profile = type("FakePositionProfile", (), {"SourceType": position_source})()
    longitudinal_profile = _FakeProfileSelection(
        "longitudinal",
        {"Velocity": velocity_profile, "Position": position_profile},
        "Velocity",
        events,
    )
    activity = type("FakeFellowActivity", (), {"LongitudinalType": longitudinal_profile})()
    segment = type("FakeFellowSegment", (), {"Activity": activity})()
    sequence = type("FakeFellowSequence", (), {"Segments": _FakeComCollection([segment])})()
    fellow = type("FakeFellow", (), {"Name": "", "Sequences": _FakeComCollection(add_factory=lambda: sequence)})()
    fellows = _FakeComCollection(add_factory=lambda: fellow)
    scenario = type("FakeTrafficScenario", (), {"Fellows": fellows})()
    save_calls: list[str] = []

    def save() -> None:
        save_calls.append("save")
        events.append(("experiment", "Save"))

    def download() -> None:
        save_calls.append("download")
        events.append(("experiment", "Download"))

    class FakeExperiment:
        TrafficScenario = scenario

        def Save(self) -> None:
            save()

        def Download(self) -> None:
            download()

    experiment = FakeExperiment()
    project = type("FakeProject", (), {"ActiveExperiment": experiment})()
    gateway = _gateway_for_application(type("FakeApplication", (), {"ActiveProject": project})())
    return SimpleNamespace(
        gateway=gateway,
        fellow_selector=Selector.create("index", "0"),
        fellows=fellows,
        sequence=sequence,
        longitudinal_profile=longitudinal_profile,
        source_type=position_source,
        velocity_source_type=velocity_source,
        velocity_value=velocity_value,
        position_value=position_value,
        events=events,
        save_calls=save_calls,
    )


def _make_counted_ego_context() -> SimpleNamespace:
    sequence = type("FakeManeuverSequence", (), {"StartPosition": 0.0, "InitialLongitudinalVelocity": 0.0})()
    maneuver = type("FakeManeuver", (), {"Sequences": _FakeComCollection([sequence])})()
    scenario = type("FakeTrafficScenario", (), {"Maneuver": _FakeComCollection([maneuver])})()
    experiment = type("FakeExperiment", (), {"TrafficScenario": scenario})()
    project = type("FakeProject", (), {"ActiveExperiment": experiment})()

    class FakeApplication:
        def __init__(self) -> None:
            self.active_project_reads = 0

        @property
        def ActiveProject(self) -> Any:
            self.active_project_reads += 1
            return project

    application = FakeApplication()
    return SimpleNamespace(
        gateway=_gateway_for_application(application),
        application=application,
        sequence=sequence,
    )


def test_get_capabilities_does_not_resolve_lazy_testing_domain() -> None:
    class FakeExperiment:
        def __init__(self) -> None:
            self.test_reads = 0

        @property
        def Test(self) -> Any:
            self.test_reads += 1
            raise AttributeError("No test is active; NCAP content must not be opened.")

    experiment = FakeExperiment()
    project = type("FakeProject", (), {"ActiveExperiment": experiment})()
    application = type("FakeApplication", (), {"ActiveProject": project})()

    result = _gateway_for_application(application).get_capabilities()

    assert result.ok
    assert experiment.test_reads == 0
    domains = result.to_dict()["data"]["domains"]
    assert domains["testing"] is True
    assert domains["testCaseInspection"] is True


def test_get_capabilities_reports_testing_support_without_project() -> None:
    application = type("FakeApplication", (), {})()

    result = _gateway_for_application(application).get_capabilities()

    assert result.ok
    domains = result.to_dict()["data"]["domains"]
    assert domains["experiments"] is False
    assert domains["testing"] is True
    assert domains["testCaseInspection"] is True


def test_set_maneuver_behavior_profiles_updates_ego_sequence_start_values() -> None:
    context = _make_counted_ego_context()
    sequence = context.sequence

    result = context.gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        json.dumps({"StartPosition": 70.0, "InitialLongitudinalVelocity": 20.0}),
        "{}",
        save=False,
        download=False,
    )

    assert result.ok
    assert sequence.StartPosition == 70.0
    assert sequence.InitialLongitudinalVelocity == 20.0
    details = result.to_dict()["data"]["details"]
    assert details["startPosition"] == "70.0"
    assert details["initialLongitudinalVelocity"] == "20.0"


def test_ego_profile_routes_through_selected_maneuver_sequence() -> None:
    first_sequence = SimpleNamespace(StartPosition=0.0, InitialLongitudinalVelocity=0.0)
    selected_sequence = SimpleNamespace(StartPosition=0.0, InitialLongitudinalVelocity=0.0)

    class FakeManeuver:
        __slots__ = ("Sequences",)

        def __init__(self, sequence: Any) -> None:
            self.Sequences = _FakeComCollection([sequence])

    scenario = SimpleNamespace(
        Maneuver=_FakeComCollection([FakeManeuver(first_sequence), FakeManeuver(selected_sequence)])
    )
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(ActiveExperiment=SimpleNamespace(TrafficScenario=scenario))
    )
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = application  # type: ignore[attr-defined]

    result = gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "1"),
        json.dumps({"StartPosition": 70.0, "InitialLongitudinalVelocity": 20.0}),
        "{}",
        save=False,
        download=False,
    )

    assert result.ok
    assert (first_sequence.StartPosition, first_sequence.InitialLongitudinalVelocity) == (0.0, 0.0)
    assert (selected_sequence.StartPosition, selected_sequence.InitialLongitudinalVelocity) == (70.0, 20.0)


@pytest.mark.parametrize(
    ("sequence_count", "expected_message"),
    ((0, "no sequences"), (2, "multiple sequences")),
)
def test_ego_profile_rejects_empty_or_ambiguous_maneuver_sequences(
    sequence_count: int,
    expected_message: str,
) -> None:
    sequences = [
        SimpleNamespace(StartPosition=0.0, InitialLongitudinalVelocity=0.0)
        for _ in range(sequence_count)
    ]

    class FakeManeuver:
        __slots__ = ("Sequences",)

        def __init__(self) -> None:
            self.Sequences = _FakeComCollection(sequences)

    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(
            ActiveExperiment=SimpleNamespace(TrafficScenario=SimpleNamespace(Maneuver=_FakeComCollection([FakeManeuver()])))
        )
    )
    gateway = _gateway_for_application(application)

    result = gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        json.dumps({"StartPosition": 70.0, "InitialLongitudinalVelocity": 20.0}),
        "{}",
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert expected_message in result.error.message.lower()
    assert all(
        (sequence.StartPosition, sequence.InitialLongitudinalVelocity) == (0.0, 0.0)
        for sequence in sequences
    )


def test_scenario_maneuver_sequence_applies_requested_order() -> None:
    class FakeManeuver:
        __slots__ = ("_index",)

        def __init__(self, index: int) -> None:
            self._index = index

        @property
        def Index(self) -> int:
            return self._index

    maneuvers = _FakeComCollection([FakeManeuver(0), FakeManeuver(1)])
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(
            ActiveExperiment=SimpleNamespace(TrafficScenario=SimpleNamespace(Maneuver=maneuvers))
        )
    )
    gateway = _gateway_for_application(application)

    result = gateway.set_scenario_maneuver_sequence(
        Selector.active(),
        json.dumps(
            [
                {"selectorKind": "index", "selectorValue": "1"},
                {"selectorKind": "index", "selectorValue": "0"},
            ]
        ),
        save=False,
        download=False,
    )

    assert result.ok
    assert [maneuvers.Item(index).Index for index in range(maneuvers.Count)] == [1, 0]


@pytest.mark.parametrize(
    ("requested_order", "should_succeed"),
    (((0, 1), True), ((1, 0), False)),
)
def test_scenario_maneuver_order_never_writes_immutable_index(
    requested_order: tuple[int, int],
    should_succeed: bool,
) -> None:
    index_set_attempts: dict[int, list[int]] = {0: [], 1: []}

    class FakeManeuver:
        __slots__ = ("_index",)

        def __init__(self, index: int) -> None:
            self._index = index

        @property
        def Index(self) -> int:
            return self._index

        @Index.setter
        def Index(self, value: int) -> None:
            index_set_attempts[self._index].append(value)
            if value != self._index:
                raise ValueError("Index is immutable.")

    maneuvers = _FakeComCollection([FakeManeuver(0), FakeManeuver(1)])
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(
            ActiveExperiment=SimpleNamespace(TrafficScenario=SimpleNamespace(Maneuver=maneuvers))
        )
    )
    gateway = _gateway_for_application(application)
    selector_json = json.dumps(
        [
            {"selectorKind": "index", "selectorValue": str(index)}
            for index in requested_order
        ]
    )

    result = gateway.set_scenario_maneuver_sequence(
        Selector.active(),
        selector_json,
        save=False,
        download=False,
    )

    assert result.ok is should_succeed
    if not should_succeed:
        assert result.error is not None
        assert "reordering is unsupported" in result.error.message.lower()
    assert index_set_attempts == {0: [], 1: []}
    assert [maneuvers.Item(index).Index for index in range(maneuvers.Count)] == [0, 1]


def test_lateral_profile_probe_uses_source_defined_activity_manager() -> None:
    class FakeSequence:
        __slots__ = ("Segments",)

        def __init__(self, segments: _FakeComCollection) -> None:
            self.Segments = segments

    class FakeLateralManager:
        AvailableElements = ("NotUsed", "StimulusAngle", "StimulusTorque", "BasicRoad", "FollowRoad")

        def __init__(self) -> None:
            self.activations: list[str] = []

        def Activate(self, profile_name: str) -> str:
            self.activations.append(profile_name)
            return profile_name

    lateral_manager = FakeLateralManager()

    class FakeActivity:
        def __init__(self) -> None:
            self.lateral_reads = 0

        @property
        def LateralType(self) -> FakeLateralManager:
            self.lateral_reads += 1
            return lateral_manager

    activity = FakeActivity()
    segment = SimpleNamespace(Activity=activity)
    sequence = FakeSequence(_FakeComCollection([segment]))
    fellow = SimpleNamespace(Name="Fellow", Sequences=_FakeComCollection([sequence]))
    scenario = SimpleNamespace(Fellows=_FakeComCollection([fellow]))
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(ActiveExperiment=SimpleNamespace(TrafficScenario=scenario))
    )
    gateway = _gateway_for_application(application)

    result = gateway.set_maneuver_behavior_profiles(
        Selector.create("index", "0"),
        Selector.create("index", "0"),
        "{}",
        '{"profile":"StimulusAngle"}',
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert activity.lateral_reads == 0
    assert lateral_manager.activations == []


def test_add_fellow_routes_catalog_object_and_driver_references() -> None:
    class FakeReferenceTypes:
        def __init__(self) -> None:
            self.activations: list[str] = []

        def Activate(self, reference: str) -> bool:
            self.activations.append(reference)
            return True

    class FakeFellow:
        def __init__(self) -> None:
            self.Name = ""
            self.Path = ""
            self.TypeName = "Fellow"
            self.ObjectID = "fellow-1"
            self.TrafficObjectType = FakeReferenceTypes()
            self.TrafficDriverType = FakeReferenceTypes()

    class FakeTrafficObjects(_FakeComCollection):
        def Item(self, selector: Any) -> Any:
            if isinstance(selector, int):
                return self.items[selector]
            for item in self.items:
                if selector in (item.Name, item.Path, item.CompleteName, item.ObjectID):
                    return item
            raise IndexError(selector)

    traffic_object = SimpleNamespace(
        Name="PassengerCar",
        Path="Vehicles/PassengerCar",
        CompleteName="Vehicles/PassengerCar",
        ObjectID="vehicle-1",
    )
    traffic_objects = FakeTrafficObjects([traffic_object])
    manager = SimpleNamespace(TrafficObjects=traffic_objects)
    fellows = _FakeComCollection(add_factory=FakeFellow)
    scenario = SimpleNamespace(Fellows=fellows)
    experiment = SimpleNamespace(TrafficScenario=scenario)
    project = SimpleNamespace(ActiveExperiment=experiment, TrafficObjectManager=manager)
    gateway = _gateway_for_application(SimpleNamespace(ActiveProject=project))

    result = gateway.add_scenario_fellow(
        "MCP_UC4_Actor",
        "{}",
        Selector.create("path", "Vehicles/PassengerCar"),
        None,
        "Drivers/Urban",
        save=False,
        download=False,
    )

    assert result.ok
    fellow = fellows.items[0]
    assert fellow.Name == "MCP_UC4_Actor"
    assert fellow.TrafficObjectType.activations == ["Vehicles/PassengerCar"]
    assert fellow.TrafficDriverType.activations == ["Drivers/Urban"]


def test_fellow_position_profile_is_editable_after_creation_without_initial_values() -> None:
    context = _make_fellow_profile_context()
    context.position_value.YawAngle = 15.0

    creation = context.gateway.add_scenario_fellow("Vehicle70", None, None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, None, save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    assert context.events == []

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        '{"Position": {"YawAngleConstant": {"Constant": 70.0}}}',
        None,
        save=False,
        download=False,
    )

    assert result.ok
    assert context.position_value._constant == 70.0
    assert context.position_value.YawAngle == 15.0
    assert context.velocity_value._constant == 25.0
    assert result.to_dict()["data"]["details"]["longitudinalPosition"] == "70.0"
    assert context.save_calls == []


def test_fellow_velocity_profile_is_editable_after_creation_without_initial_values() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle20", None, None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, None, save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    assert context.events == []

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        '{"Velocity": {"Constant": {"Constant": 20.0}}}',
        None,
        save=True,
        download=True,
    )

    assert result.ok
    assert context.longitudinal_profile.active_name == "Velocity"
    assert context.velocity_source_type.active_name == "Constant"
    assert context.velocity_value._constant == 20.0
    assert context.position_value._constant == 0.0
    assert context.sequence.Segments.item_calls == 1
    assert result.to_dict()["data"]["details"]["longitudinalVelocity"] == "20.0"
    assert context.events.index(("velocity-source", "activate:Constant")) < context.events.index(("velocity", "set:Constant"))
    assert context.events.index(("velocity", "set:Constant")) < context.events.index(("velocity", "read:Constant"))
    assert context.events.index(("velocity", "read:Constant")) < context.events.index(("experiment", "Save"))
    assert context.save_calls == ["save", "download"]


@pytest.mark.parametrize(
    "longitudinal_json",
    (
        '{"StartPosition": 70.0}',
        '{"InitialLongitudinalVelocity": 20.0}',
        '{"StartPosition": 70.0, "InitialLongitudinalVelocity": 20.0}',
    ),
    ids=("ego-start-position", "ego-initial-velocity", "both-ego-initial-properties"),
)
def test_fellow_rejects_ego_initial_properties_before_com_mutation(longitudinal_json: str) -> None:
    context = _make_fellow_profile_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        longitudinal_json,
        None,
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert "ego-only" in result.error.message
    assert context.fellows.item_calls == 0
    assert context.events == []
    assert context.save_calls == []


def test_fellow_position_profile_workflow_reads_back_the_requested_value() -> None:
    context = _make_fellow_profile_context()

    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    assert creation.ok
    fellow = context.fellows.items[0]
    existing_sequence = type("FakeExistingSequence", (), {"Name": "EarlierSequence", "Segments": _FakeComCollection()})()
    fellow.Sequences.items.append(existing_sequence)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    activities = context.gateway.list_fellow_activities(context.fellow_selector)
    assert maneuver.ok
    assert activities.ok
    activity_data = activities.to_dict()["data"]
    assert activity_data["count"] == 2
    assert [item["index"] for item in activity_data["items"]] == [0, 1]

    first_segment = context.sequence.Segments.items[0]
    second_position_value = _FakeProfileValue("second-position", 10.0, context.events)
    second_source_type = _FakeProfileSelection("second-source", {"YawAngleConstant": second_position_value}, "YawAngleConstant", context.events)
    second_position_profile = type("FakePositionProfile", (), {"SourceType": second_source_type})()
    second_velocity_value = _FakeProfileValue("second-velocity", 50.0, context.events)
    second_longitudinal_profile = _FakeProfileSelection(
        "second-longitudinal",
        {"Velocity": second_velocity_value, "Position": second_position_profile},
        "Velocity",
        context.events,
    )
    second_activity = type("FakeFellowActivity", (), {"LongitudinalType": second_longitudinal_profile})()
    second_segment = type("FakeFellowSegment", (), {"Activity": second_activity})()
    context.sequence.Segments = _FakeComCollection([first_segment, second_segment])

    profile = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "1"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert profile.ok
    assert context.longitudinal_profile.active_name == "Position"
    assert context.velocity_value.Constant == 25.0
    assert context.position_value.Constant == 70.0
    assert context.sequence.Segments.item_calls == 1
    assert second_position_value._constant == 10.0
    assert ("second-position", "set:Constant") not in context.events
    assert profile.to_dict()["data"]["details"]["longitudinalPosition"] == "70.0"
    assert context.events.index(("longitudinal", "available")) < context.events.index(("longitudinal", "activate:Position"))
    assert context.events.index(("longitudinal", "activate:Position")) < context.events.index(("source", "available"))
    assert context.events.index(("source", "available")) < context.events.index(("source", "activate:YawAngleConstant"))
    assert context.events.index(("source", "activate:YawAngleConstant")) < context.events.index(("position", "set:Constant"))
    assert context.events.index(("position", "set:Constant")) < context.events.index(("position", "read:Constant"))
    assert context.events.index(("position", "read:Constant")) < context.events.index(("experiment", "Save"))
    assert context.events.index(("experiment", "Save")) < context.events.index(("experiment", "Download"))
    assert context.save_calls == ["save", "download"]
    assert profile.to_dict()["data"]["details"]["saved"] == "True"
    assert profile.to_dict()["data"]["details"]["downloaded"] == "True"


def test_fellow_flat_constant_is_rejected_before_com_traversal_or_mutation() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok

    item_calls = context.fellows.item_calls, context.sequence.Segments.item_calls
    event_count = len(context.events)
    profile = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Constant": 70.0}),
        "{}",
        save=True,
        download=True,
    )

    assert not profile.ok
    assert profile.error is not None
    assert profile.error.error_type == "validation"
    assert "Position" in profile.error.message
    assert (context.fellows.item_calls, context.sequence.Segments.item_calls) == item_calls
    assert len(context.events) == event_count
    assert context.velocity_value.Constant == 25.0
    assert context.position_value.Constant == 0.0
    assert context.save_calls == []


@pytest.mark.parametrize(
    "longitudinal_json",
    (
        "not json",
        '{"StartPosition": true}',
        '{"StartPosition": "70.0"}',
        '{"StartPosition": []}',
        '{"StartPosition": NaN}',
        '{"StartPosition": 1e999}',
        '{"StartPosition": 70.0, "StartPosition": 71.0}',
    ),
)
def test_invalid_ego_profile_json_is_rejected_before_com_traversal(longitudinal_json: str) -> None:
    context = _make_counted_ego_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        longitudinal_json,
        "{}",
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert context.application.active_project_reads == 0
    assert context.sequence.StartPosition == 0.0
    assert context.sequence.InitialLongitudinalVelocity == 0.0


def test_both_profile_sides_are_validated_before_ego_mutation() -> None:
    context = _make_counted_ego_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        json.dumps({"StartPosition": 70.0}),
        "[]",
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert context.application.active_project_reads == 0
    assert context.sequence.StartPosition == 0.0


def test_json_null_unused_lateral_payload_is_accepted_without_lateral_traversal() -> None:
    context = _make_counted_ego_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        json.dumps({"StartPosition": 70.0}),
        "null",
        save=False,
        download=False,
    )

    assert result.ok
    assert context.sequence.StartPosition == 70.0
    assert result.to_dict()["data"]["details"]["startPosition"] == "70.0"


@pytest.mark.parametrize("parameter_name", ("longitudinalProfileJson", "lateralProfileJson"))
def test_maneuver_profile_json_null_normalizes_to_empty_for_each_side(parameter_name: str) -> None:
    from modeldesk_mcp.contracts.requests import _parse_maneuver_behavior_profile_json

    assert _parse_maneuver_behavior_profile_json("null", parameter_name) == {}


@pytest.mark.parametrize("json_text", ("[]", "false", '"unused"', "70.0"))
@pytest.mark.parametrize("parameter_name", ("longitudinalProfileJson", "lateralProfileJson"))
def test_maneuver_profile_json_rejects_non_object_non_null_roots(json_text: str, parameter_name: str) -> None:
    from modeldesk_mcp.contracts.requests import _parse_maneuver_behavior_profile_json

    with pytest.raises(ValueError, match="must be a JSON object"):
        _parse_maneuver_behavior_profile_json(json_text, parameter_name)


@pytest.mark.parametrize(
    ("longitudinal_json", "lateral_json"),
    (("{}", "{}"), ("null", "null")),
    ids=("empty-objects", "json-nulls"),
)
def test_two_empty_profile_payloads_are_rejected_before_com_traversal(
    longitudinal_json: str, lateral_json: str
) -> None:
    context = _make_counted_ego_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        Selector.active(),
        Selector.create("index", "0"),
        longitudinal_json,
        lateral_json,
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert context.application.active_project_reads == 0


@pytest.mark.parametrize(
    "longitudinal_json",
    (
        '{"Velocity": {"Constant": 70.0}}',
        '{"StartPosition": true}',
        '{"InitialLongitudinalVelocity": true}',
        '{"InitialLongitudinalVelocity": "20.0"}',
        '{"InitialLongitudinalVelocity": [20.0]}',
        '{"InitialLongitudinalVelocity": NaN}',
        '{"InitialLongitudinalVelocity": 1e999}',
        '{"InitialLongitudinalVelocity": 20.0, "InitialLongitudinalVelocity": 21.0}',
        '{"Velocity": {"YawAngleConstant": {"Constant": 20.0}}}',
        '{"Velocity": {"Constant": {"Constant": true}}}',
        '{"Velocity": {"Constant": {"Constant": 20.0, "YawAngle": 0.0}}}',
        '{"Position": {"YawAngleConstant": {"Constant": 70.0}}, "Velocity": {"Constant": {"Constant": 20.0}}}',
        '{"Position": {}}',
        '{"Position": {"YawAngleConstant": {"Constant": 70.0, "YawAngle": 0.0}}}',
        '{"Position": {"YawAngleConstant": {"Constant": true}}}',
        '{"Position": {"YawAngleConstant": {"Constant": []}}}',
        '{"Position": {"YawAngleConstant": {"Constant": NaN}}}',
        '{"Position": {"YawAngleConstant": {"Constant": 70.0, "Constant": 71.0}}}',
        '{"Position": {"Velocity": {"Constant": 70.0}}}',
        '{"Position": {"YawAngleConstant": {"YawAngle": 0.0}}}',
    ),
)
def test_invalid_fellow_selection_json_is_rejected_before_com_traversal(longitudinal_json: str) -> None:
    context = _make_fellow_profile_context()

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        longitudinal_json,
        "{}",
        save=False,
        download=False,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert context.fellows.item_calls == 0
    assert context.events == []


def test_missing_fellow_sequence_fails_before_profile_access() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "1"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert context.events == []
    assert context.save_calls == []


def test_empty_fellow_sequence_fails_before_profile_access() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    context.sequence.Segments = _FakeComCollection()

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "no segments" in result.error.message
    assert context.events == []
    assert context.save_calls == []


def test_unavailable_fellow_profile_is_not_activated_or_saved() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    context.longitudinal_profile.elements = {"Velocity": context.velocity_value}

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "unavailable" in result.error.message
    assert ("longitudinal", "activate:Position") not in context.events
    assert context.velocity_value.Constant == 25.0
    assert context.position_value.Constant == 0.0
    assert context.save_calls == []


def test_unavailable_fellow_source_reports_partial_activation_without_saving() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    context.source_type.elements = {}

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "partial" in result.error.message
    assert "not rolled back" in result.error.message
    assert ("longitudinal", "activate:Position") in context.events
    assert ("source", "activate:YawAngleConstant") not in context.events
    assert context.position_value.Constant == 0.0
    assert context.save_calls == []


def test_failed_position_readback_reports_partial_mutation_and_skips_save_download() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    context.position_value.readback_override = 69.0

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "partial" in result.error.message
    assert "not rolled back" in result.error.message
    assert context.position_value._constant == 70.0
    assert context.save_calls == []


@pytest.mark.parametrize("failure_stage", ("setter", "readback"))
def test_fellow_position_setter_or_readback_exception_skips_persistence(failure_stage: str) -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok
    if failure_stage == "setter":
        context.position_value.setter_error = RuntimeError("injected setter failure")
    else:
        context.position_value.readback_error = RuntimeError("injected readback failure")

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "setting and reading back fellow Position.Constant failed" in result.error.message
    assert "not rolled back" in result.error.message
    assert result.to_dict()["data"] is None
    assert context.position_value._constant == (0.0 if failure_stage == "setter" else 70.0)
    assert context.save_calls == []
    assert ("experiment", "Save") not in context.events
    assert ("experiment", "Download") not in context.events


def test_save_failure_does_not_download_after_verified_fellow_write() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok

    def fail_save() -> None:
        context.save_calls.append("save")
        raise RuntimeError("injected save failure")

    context.gateway._application.ActiveProject.ActiveExperiment.Save = fail_save

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "Save failed" in result.error.message
    assert "not rolled back" in result.error.message
    assert context.save_calls == ["save"]


def test_download_failure_reports_successful_save_without_claiming_rollback() -> None:
    context = _make_fellow_profile_context()
    creation = context.gateway.add_scenario_fellow("Vehicle70", "{}", None, None, None, save=False, download=False)
    maneuver = context.gateway.add_scenario_maneuver(context.fellow_selector, "{}", save=False, download=False)
    assert creation.ok
    assert maneuver.ok

    def fail_download() -> None:
        context.save_calls.append("download")
        raise RuntimeError("injected download failure")

    context.gateway._application.ActiveProject.ActiveExperiment.Download = fail_download

    result = context.gateway.set_maneuver_behavior_profiles(
        context.fellow_selector,
        Selector.create("index", "0"),
        json.dumps({"Position": {"YawAngleConstant": {"Constant": 70.0}}}),
        "{}",
        save=True,
        download=True,
    )

    assert not result.ok
    assert result.error is not None
    assert "Download failed" in result.error.message
    assert "Save succeeded and remains complete" in result.error.message
    assert context.save_calls == ["save", "download"]


@pytest.mark.parametrize("properties_json", ('{"Value":NaN}', '{"Value":Infinity}', '{"Value":1e999}'))
def test_scalar_property_json_rejects_nonfinite_numbers(properties_json: str) -> None:
    from modeldesk_mcp.contracts.requests import parse_scalar_properties_json

    with pytest.raises(ValueError):
        parse_scalar_properties_json(properties_json, "propertiesJson")


def test_scenario_maneuver_rejects_nonfinite_property_before_com_mutation() -> None:
    mutations: list[float] = []

    class FakeManeuver:
        Name = "Ego Maneuver"
        TypeName = "Maneuver"
        Path = ""
        ObjectID = "maneuver-1"

        def __init__(self) -> None:
            self._value = 0.0

        @property
        def Value(self) -> float:
            return self._value

        @Value.setter
        def Value(self, value: float) -> None:
            mutations.append(value)
            self._value = value

    maneuvers = _FakeComCollection(add_factory=FakeManeuver)
    scenario = SimpleNamespace(Maneuvers=maneuvers)
    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(ActiveExperiment=SimpleNamespace(TrafficScenario=scenario))
    )
    gateway = _gateway_for_application(application)

    result = gateway.add_scenario_maneuver(
        Selector.active(),
        '{"Value":NaN}',
        save=False,
        download=False,
    )

    assert not result.ok
    assert mutations == []

