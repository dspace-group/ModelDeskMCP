"""Tests for Plot Manager collection discovery."""

from types import SimpleNamespace

from modeldesk_mcp.com_bridge import accessor as com
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions


def _application_with_plotting(plotting: object) -> SimpleNamespace:
    experiment = SimpleNamespace(Plotting=plotting)
    project = SimpleNamespace(ActiveExperiment=experiment)
    return SimpleNamespace(ActiveProject=project)


def _gateway_executing_inline() -> ModelDeskAutomationGateway:
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._options = ComGatewayOptions()  # type: ignore[attr-defined]
    gateway._execute_com = lambda _, callback: callback(gateway._application)  # type: ignore[attr-defined, method-assign]
    return gateway


def test_snapshot_collection_supports_safearray_tuple_values() -> None:
    snapshot = com.snapshot_collection(("Run A", "Run B"), "capture", 10)

    assert snapshot.count == 2
    assert tuple(item.name for item in snapshot.items) == ("Run A", "Run B")
    assert tuple(item.kind for item in snapshot.items) == ("capture", "capture")
    assert not snapshot.is_truncated


def test_snapshot_collection_returns_next_offset_for_each_page() -> None:
    collection = ("Run A", "Run B", "Run C")

    first_page = com.snapshot_collection(collection, "capture", 2)
    second_page = com.snapshot_collection(collection, "capture", 2, first_page.next_offset or 0)

    assert tuple(item.name for item in first_page.items) == ("Run A", "Run B")
    assert first_page.next_offset == 2
    assert tuple(item.name for item in second_page.items) == ("Run C",)
    assert second_page.next_offset is None


def test_list_plot_captures_uses_capture_manager_collection() -> None:
    plotting = SimpleNamespace(Captures=SimpleNamespace(OpenCaptures=("Run A", "Run B")))
    gateway = _gateway_executing_inline()
    gateway._application = _application_with_plotting(plotting)  # type: ignore[attr-defined]

    summary = gateway.list_plot_captures()

    assert summary.domain == "plotting.captures"
    assert tuple(item.name for item in summary.items) == ("Run A", "Run B")
    assert summary.properties["collection.selected"] == "OpenCaptures"


def test_list_plot_captures_returns_next_offset_for_follow_up_page() -> None:
    plotting = SimpleNamespace(Captures=SimpleNamespace(OpenCaptures=("Run A", "Run B", "Run C")))
    gateway = _gateway_executing_inline()
    gateway._options = ComGatewayOptions(max_collection_items=2)  # type: ignore[attr-defined]
    gateway._application = _application_with_plotting(plotting)  # type: ignore[attr-defined]

    first_page = gateway.list_plot_captures()
    second_page = gateway.list_plot_captures(first_page.next_offset)

    assert tuple(item.name for item in first_page.items) == ("Run A", "Run B")
    assert first_page.next_offset == 2
    assert tuple(item.name for item in second_page.items) == ("Run C",)
    assert second_page.next_offset is None


def test_list_plot_layouts_uses_layout_manager_collection() -> None:
    plotting = SimpleNamespace(Layouts=SimpleNamespace(ActiveLayouts=("Overview", "Signals")))
    gateway = _gateway_executing_inline()
    gateway._application = _application_with_plotting(plotting)  # type: ignore[attr-defined]

    summary = gateway.list_plot_layouts()

    assert summary.domain == "plotting.layouts"
    assert tuple(item.name for item in summary.items) == ("Overview", "Signals")
    assert summary.properties["collection.selected"] == "ActiveLayouts"


def test_plotting_summary_reads_nested_manager_collection_counts() -> None:
    plotting = SimpleNamespace(
        Name="Vehicle_Complete.xml",
        Captures=SimpleNamespace(OpenCaptures=("Run A",)),
        Layouts=SimpleNamespace(ActiveLayouts=("Overview", "Signals")),
        SimulationSignals=("Speed", "YawRate", "SteeringAngle"),
    )
    gateway = _gateway_executing_inline()

    summary = gateway._create_plotting_summary(_application_with_plotting(plotting))

    assert summary.items[0].name == "Vehicle_Complete.xml"
    assert summary.properties["collection.captures.open.count"] == "1"
    assert summary.properties["collection.layouts.active.count"] == "2"
    assert summary.properties["collection.signals.simulation.count"] == "3"
