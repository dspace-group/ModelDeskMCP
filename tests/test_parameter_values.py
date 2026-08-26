"""Tests for generic parameter value validation."""

import pytest

from modeldesk_mcp.contracts import ParameterValueEditRequest, ParameterValueKind


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