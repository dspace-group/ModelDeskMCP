"""Tests for Traffic Object Manager mutation tools."""

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector, SelectorKind


def _make_gateway() -> ModelDeskAutomationGateway:
    return ModelDeskAutomationGateway(ComStaDispatcher(), ComGatewayOptions())


def test_add_traffic_object_rejects_empty_name() -> None:
    gateway = _make_gateway()
    result = gateway.add_traffic_object("", "Cube.obj")
    assert not result.ok
    assert result.error.error_type == "validation"


def test_normalize_object3d_accepts_empty_and_none() -> None:
    gateway = _make_gateway()
    assert gateway._normalize_object3d("") == ""
    assert gateway._normalize_object3d(None) == ""


def test_remove_traffic_object_rejects_active_selector() -> None:
    gateway = _make_gateway()
    result = gateway.remove_traffic_object(Selector.active())
    assert not result.ok
    assert result.error.error_type == "validation"


def test_add_traffic_object_folder_rejects_empty_name() -> None:
    gateway = _make_gateway()
    result = gateway.add_traffic_object_folder("")
    assert not result.ok
    assert result.error.error_type == "validation"


def test_remove_traffic_object_folder_rejects_active_selector() -> None:
    gateway = _make_gateway()
    result = gateway.remove_traffic_object_folder(Selector.active())
    assert not result.ok
    assert result.error.error_type == "validation"


class _FakeGateway:
    def __init__(self):
        self.calls = []
        self.session_id = "test-session"
    def add_traffic_object(self, name, object3d):
        self.calls.append(("add", name, object3d))
        return type("R", (), {"ok": True})()
    def remove_traffic_object(self, selector):
        self.calls.append(("remove", selector))
        return type("R", (), {"ok": True})()
    def add_traffic_object_folder(self, name):
        self.calls.append(("add_folder", name))
        return type("R", (), {"ok": True})()
    def remove_traffic_object_folder(self, selector):
        self.calls.append(("remove_folder", selector))
        return type("R", (), {"ok": True})()


def _make_service(fake_gateway):
    from modeldesk_mcp.domain.service import ModelDeskService
    service = object.__new__(ModelDeskService)
    service._gateway = fake_gateway  # type: ignore[attr-defined]
    return service


def test_service_add_traffic_object_routes_args() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    service.add_traffic_object("Cone", "Cone.obj")
    assert fake.calls == [("add", "Cone", "Cone.obj")]

def test_service_remove_traffic_object_selector_validation() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    result = service.remove_traffic_object("name", "")
    assert not result.ok
    assert fake.calls == []

def test_service_add_traffic_object_folder_routes_args() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    service.add_traffic_object_folder("TestFolder")
    assert fake.calls == [("add_folder", "TestFolder")]

def test_service_remove_traffic_object_folder_selector_validation() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)
    result = service.remove_traffic_object_folder("name", "")
    assert not result.ok
    assert fake.calls == []
