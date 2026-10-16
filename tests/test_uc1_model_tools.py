"""Tests for UC1 model info/model selection tools."""

from types import SimpleNamespace

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector


def _make_gateway() -> ModelDeskAutomationGateway:
    return ModelDeskAutomationGateway(ComStaDispatcher(), ComGatewayOptions())


def test_set_active_model_rejects_empty_model_path() -> None:
    gateway = _make_gateway()
    result = gateway.set_active_model("", None, None, None)
    assert not result.ok
    assert result.error.error_type == "validation"


class _FakeGateway:
    def __init__(self) -> None:
        self.calls = []
        self.session_id = "test-session"

    def get_active_model_info(self, offset=0):
        self.calls.append(("get_active_model_info", offset))
        return type("R", (), {"ok": True})()

    def set_active_model(self, model_file_path, ml_working_directory, initialization_command, platform_name):
        self.calls.append(("set_active_model", model_file_path, ml_working_directory, initialization_command, platform_name))
        return type("R", (), {"ok": True})()


def _make_service(fake_gateway):
    from modeldesk_mcp.domain.service import ModelDeskService

    service = object.__new__(ModelDeskService)
    service._gateway = fake_gateway  # type: ignore[attr-defined]
    return service


def test_service_get_active_model_info_routes_to_gateway() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    service.get_active_model_info()
    assert fake.calls == [("get_active_model_info", 0)]


def test_service_set_active_model_routes_to_gateway() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    service.set_active_model("model.slx", None, "", "")
    assert fake.calls == [("set_active_model", "model.slx", None, "", "")]


def test_gateway_activates_selected_experiment_and_parameter_set() -> None:
    calls: list[tuple[str, object]] = []

    class FakeActivatable:
        def __init__(self, kind: str, name: str) -> None:
            self.kind = kind
            self.Name = name

        def Activate(self, save_active: bool):
            calls.append((self.kind, save_active))

    class FakeCollection:
        def __init__(self, items) -> None:
            self.items = items

        @property
        def Count(self) -> int:
            return len(self.items)

        def Item(self, selector):
            if isinstance(selector, int):
                return self.items[selector]
            for item in self.items:
                if item.Name == selector:
                    return item
            raise IndexError(selector)

    parameter_set = FakeActivatable("parameter-set", "Nominal")
    experiment = FakeActivatable("experiment", "Baseline")
    experiment.ParameterSets = FakeCollection([parameter_set])
    project = SimpleNamespace(
        Experiments=FakeCollection([experiment]),
        ActiveExperiment=experiment,
    )
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = type("InlineDispatcher", (), {"invoke": lambda _self, operation, timeout_seconds: operation()})()
    gateway._options = type("Options", (), {"operation_timeout_seconds": 60})()
    gateway._session_id = "test-session"
    gateway._application = SimpleNamespace(ActiveProject=project)

    experiment_result = gateway.activate_experiment(Selector.create("name", "Baseline"), save_active=False)
    parameter_result = gateway.activate_parameter_set(Selector.create("index", "0"), save_active=True)

    assert experiment_result.ok
    assert parameter_result.ok
    assert calls == [("experiment", False), ("parameter-set", True)]


def test_gateway_model_readbacks_map_verified_interface_property_names() -> None:
    model_info = SimpleNamespace(
        Name="VehicleModel",
        Path="C:/models/vehicle.slx",
        TypeName="SimulinkModel",
        PlatformName="ASM",
        PlatformKind="Simulink",
        Validity="Valid",
        MATLABWorkingDirectory="C:/models/work",
        ModelInitializationCommand="initialize_vehicle",
    )

    class FakeModels:
        ActiveModelInfo = model_info

        def SetActiveModel(self, *arguments):
            return model_info

    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = type("InlineDispatcher", (), {"invoke": lambda _self, operation, timeout_seconds: operation()})()
    gateway._options = type("Options", (), {"operation_timeout_seconds": 60})()
    gateway._session_id = "test-session"
    gateway._application = SimpleNamespace(
        ActiveProject=SimpleNamespace(
            ActiveExperiment=SimpleNamespace(Models=FakeModels())
        )
    )

    active_info = gateway.get_active_model_info().to_dict()["data"]
    set_result = gateway.set_active_model("C:/models/vehicle.slx", "C:/models/work", "initialize_vehicle", "ASM")

    assert active_info["properties"]["ModelFilePath"] == model_info.Path
    assert active_info["properties"]["MLWorkingDirectory"] == model_info.MATLABWorkingDirectory
    assert set_result.ok
    assert set_result.to_dict()["data"]["details"]["ModelFilePath"] == model_info.Path
