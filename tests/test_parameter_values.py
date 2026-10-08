"""Tests for generic parameter value validation."""

import pytest
from types import SimpleNamespace

from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway
from modeldesk_mcp.contracts import ParameterValueEditRequest, ParameterValueKind
from modeldesk_mcp.contracts.models import ToolResult


def test_scalar_value_accepts_numeric_json() -> None:
    request = ParameterValueEditRequest.create("Scalar", "1.25")

    assert request.value_kind == ParameterValueKind.SCALAR
    assert request.com_value == 1.25


def test_text_value_requires_json_string() -> None:
    request = ParameterValueEditRequest.create("Text", '"Comfort"')

    assert request.com_value == "Comfort"


def test_vector_value_accepts_bounded_numeric_array() -> None:
    request = ParameterValueEditRequest.create("Vector", "[1,2,3]")

    assert request.com_value == (1.0, 2.0, 3.0)


def test_matrix_value_requires_rectangular_rows() -> None:
    with pytest.raises(ValueError):
        ParameterValueEditRequest.create("Matrix", "[[1,2],[3]]")


def test_table_value_accepts_rows_object() -> None:
    request = ParameterValueEditRequest.create("Table", '{"columns":["x","y"],"rows":[[1,2],[3,4]]}')
    assert request.value_kind == ParameterValueKind.TABLE
    assert request.com_value == ((1.0, 2.0), (3.0, 4.0))


def test_table_value_rejects_column_count_mismatch() -> None:
    with pytest.raises(ValueError, match="column"):
        ParameterValueEditRequest.create("Table", '{"columns":["x","y"],"rows":[[1]]}')


def test_scalar_value_rejects_integer_outside_finite_float_range() -> None:
    oversized_integer = "9" * 400

    with pytest.raises(ValueError, match="finite|range"):
        ParameterValueEditRequest.create("Scalar", oversized_integer)


def test_typed_scalar_overflow_returns_structured_validation_error() -> None:
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._session_id = "test-session"  # type: ignore[attr-defined]

    result = gateway.set_parameter_value("Vehicle.Speed", "Scalar", "9" * 400)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"


@pytest.mark.parametrize("value", ("NaN", "Infinity", "-Infinity", "1e999"))
def test_scalar_parameter_rejects_nonfinite_values_before_com_dispatch(value: str) -> None:
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._session_id = "test-session"  # type: ignore[attr-defined]
    dispatches: list[str] = []

    def record_dispatch(operation_name: str, _operation: object) -> ToolResult:
        dispatches.append(operation_name)
        return ToolResult.success(operation_name, "test-session", {})

    gateway._execute_com = record_dispatch  # type: ignore[attr-defined]

    result = gateway.set_scalar_parameter("Vehicle.Speed", value)

    assert not result.ok
    assert result.error is not None
    assert result.error.error_type == "validation"
    assert dispatches == []


def test_gateway_sets_typed_parameter_reads_back_metadata_and_saves() -> None:
    events: list[str] = []

    class FakeParameter:
        Name = "TargetSpeed"
        TypeName = "Numeric"
        Unit = "km/h"

        def __init__(self) -> None:
            self.value = 0.0

        @property
        def V(self):
            events.append("read")
            return self.value

        @V.setter
        def V(self, value):
            events.append("write")
            self.value = value

    parameter = FakeParameter()

    class FakeParameterSet:
        def Find(self, parameter_path: str):
            events.append(f"find:{parameter_path}")
            return parameter

    class FakeExperiment:
        ActiveParameterSet = FakeParameterSet()

        def Save(self) -> None:
            events.append("save")

    application = SimpleNamespace(
        ActiveProject=SimpleNamespace(ActiveExperiment=FakeExperiment())
    )
    gateway = object.__new__(ModelDeskAutomationGateway)
    gateway._dispatcher = type("InlineDispatcher", (), {"invoke": lambda _self, operation, timeout_seconds: operation()})()
    gateway._options = type("Options", (), {"operation_timeout_seconds": 60})()
    gateway._session_id = "test-session"
    gateway._application = application

    result = gateway.set_parameter_value("Vehicle.TargetSpeed", "Vector", "[1,2,3]")
    save_result = gateway.save_active_experiment()

    assert result.ok
    assert parameter.value == (1.0, 2.0, 3.0)
    assert result.to_dict()["data"]["parameterPath"] == "Vehicle.TargetSpeed"
    assert result.to_dict()["data"]["unit"] == "km/h"
    assert result.to_dict()["data"]["value"] == "(1.0, 2.0, 3.0)"
    assert save_result.ok
    assert events == ["find:Vehicle.TargetSpeed", "write", "read", "save"]
