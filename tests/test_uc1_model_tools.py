"""Tests for UC1 model info/model selection tools."""

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions


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

    def get_active_model_info(self):
        self.calls.append(("get_active_model_info",))
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
    assert fake.calls == [("get_active_model_info",)]


def test_service_set_active_model_routes_to_gateway() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    service.set_active_model("model.slx", None, "", "")
    assert fake.calls == [("set_active_model", "model.slx", None, "", "")]
