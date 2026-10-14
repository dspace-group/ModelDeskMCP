"""Tests for testing-domain tool input validation and selector routing."""

from __future__ import annotations

from typing import Any

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.config import ComGatewayOptions
from modeldesk_mcp.contracts import Selector, SelectorKind
from modeldesk_mcp.contracts.models import ToolResult


def _make_gateway() -> ModelDeskAutomationGateway:
    return ModelDeskAutomationGateway(ComStaDispatcher(), ComGatewayOptions())


def test_list_concrete_test_cases_rejects_active_selector() -> None:
    gateway = _make_gateway()

    result = gateway.list_concrete_test_cases(Selector.active())

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


class _FakeGateway:
    """Minimal gateway stub that records calls and returns a canned success result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.session_id = "test-session"

    def _record(self, name: str, *args: Any) -> ToolResult:
        self.calls.append((name, args))
        return ToolResult.success(name, "test-session", {})

    def list_concrete_test_cases(self, logical_test_case_selector: Selector, offset: int = 0) -> ToolResult:
        return self._record("list_concrete_test_cases", logical_test_case_selector, offset)


def _make_service(fake_gateway: _FakeGateway) -> Any:
    from modeldesk_mcp.domain.service import ModelDeskService

    service = object.__new__(ModelDeskService)
    service._gateway = fake_gateway  # type: ignore[attr-defined]
    return service


def test_service_list_concrete_test_cases_defaults_to_first_logical_test_case() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_concrete_test_cases("index", "0")

    assert result.ok
    name, args = fake.calls[0]
    assert name == "list_concrete_test_cases"
    selector: Selector = args[0]
    assert selector.by == SelectorKind.INDEX
    assert selector.to_com_value() == 0
    assert args[1] == 0


def test_service_list_concrete_test_cases_routes_name_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_concrete_test_cases("name", "NCAP_AEB_CCR_Case2")

    assert result.ok
    name, args = fake.calls[0]
    selector: Selector = args[0]
    assert selector.by == SelectorKind.NAME
    assert selector.value == "NCAP_AEB_CCR_Case2"
    assert args[1] == 0


def test_service_list_concrete_test_cases_rejects_invalid_selector() -> None:
    fake = _FakeGateway()
    service = _make_service(fake)

    result = service.list_concrete_test_cases("index", "")

    assert not result.ok
    assert len(fake.calls) == 0
