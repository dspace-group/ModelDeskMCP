"""Tests for Traffic Object Manager mutation tools."""

from types import SimpleNamespace

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector, SelectorKind


class _InlineDispatcher:
    def invoke(self, operation, timeout_seconds):
        return operation()


class _CatalogCollection:
    def __init__(self, items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, selector):
        if isinstance(selector, int):
            return self.items[selector]
        for item in self.items:
            for property_name in ("Name", "Path", "CompleteName", "ObjectID"):
                value = getattr(item, property_name, None)
                if value is not None and value == selector:
                    return item
        raise IndexError(selector)


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
    def remove_traffic_object(self, selector, dry_run=False):
        self.calls.append(("remove", selector, dry_run))
        return type("R", (), {"ok": True})()
    def add_traffic_object_folder(self, name):
        self.calls.append(("add_folder", name))
        return type("R", (), {"ok": True})()
    def remove_traffic_object_folder(self, selector, dry_run=False):
        self.calls.append(("remove_folder", selector, dry_run))
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


def test_catalog_readback_and_mutation_capability_match_registered_api() -> None:
    reusable_object = SimpleNamespace(
        Name="PassengerCar",
        Path="Vehicles/PassengerCar",
        CompleteName="Vehicles/PassengerCar",
        TypeName="DynamicVehicle",
        ObjectID="vehicle-1",
    )
    folder = SimpleNamespace(Name="Vehicles", Path="Vehicles", CompleteName="Vehicles", TypeName="Folder")

    class FakeCatalogManager:
        Name = "Traffic Object Manager"

        def __init__(self) -> None:
            self.TrafficObjects = _CatalogCollection([reusable_object])
            self.Objects = self.TrafficObjects
            self.Folders = _CatalogCollection([folder])
            self.add_calls = []
            self.remove_calls = []

        def AddTrafficObject(self, name: str, object3d: str):
            self.add_calls.append((name, object3d))
            traffic_object = SimpleNamespace(Name=name, Path=f"Vehicles/{name}", CompleteName=f"Vehicles/{name}", TypeName="TrafficObject", ObjectID="new-1")
            self.TrafficObjects.items.append(traffic_object)
            return traffic_object

        def RemoveTrafficObject(self, object_id: str) -> bool:
            self.remove_calls.append(("object", object_id))
            self.TrafficObjects.items = [item for item in self.TrafficObjects.items if item.ObjectID != object_id]
            return True

        def AddFolder(self, name: str):
            new_folder = SimpleNamespace(Name=name, CompleteName=name, Path=name, TypeName="Folder")
            self.Folders.items.append(new_folder)
            return new_folder

        def RemoveFolder(self, name: str) -> bool:
            self.remove_calls.append(("folder", name))
            self.Folders.items = [item for item in self.Folders.items if item.Name != name]
            return True

    manager = FakeCatalogManager()
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = _InlineDispatcher()  # type: ignore[attr-defined]
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    gateway._application = SimpleNamespace(  # type: ignore[attr-defined]
        ActiveProject=SimpleNamespace(TrafficObjectManager=manager)
    )

    capabilities = gateway.get_capabilities()
    objects = gateway.list_traffic_objects()
    folders = gateway.list_traffic_object_folders()
    reference = gateway.validate_traffic_object_reference(Selector.create("path", "Vehicles/PassengerCar"))
    mutation = gateway.add_traffic_object("Truck", "Truck.dae")
    folder_added = gateway.add_traffic_object_folder("StaticAssets")
    folder_preview = gateway.remove_traffic_object_folder(Selector.create("name", "StaticAssets"), dry_run=True)
    object_preview = gateway.remove_traffic_object(Selector.create("id", "vehicle-1"), dry_run=True)
    assert folder_preview.ok
    assert object_preview.ok
    assert folder_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert object_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert manager.remove_calls == []
    folder_removed = gateway.remove_traffic_object_folder(Selector.create("name", "StaticAssets"))
    object_removed = gateway.remove_traffic_object(Selector.create("id", "vehicle-1"))

    assert capabilities.ok
    assert capabilities.to_dict()["data"]["domains"]["trafficObjectCatalogMutation"] is False
    assert [item["name"] for item in objects.to_dict()["data"]["items"]] == ["PassengerCar"]
    assert [item["name"] for item in folders.to_dict()["data"]["items"]] == ["Vehicles"]
    assert reference.ok
    assert reference.to_dict()["data"]["details"]["Path"] == "Vehicles/PassengerCar"
    assert mutation.ok
    assert folder_added.ok
    assert folder_preview.ok
    assert folder_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert object_preview.ok
    assert object_preview.to_dict()["data"]["details"]["dryRun"] == "true"
    assert folder_removed.ok
    assert object_removed.ok
    assert manager.add_calls == [("Truck", "Truck.dae")]
    assert manager.remove_calls == [("folder", "StaticAssets"), ("object", "vehicle-1")]
