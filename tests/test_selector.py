"""Tests for selector validation."""

import pytest

from modeldesk_mcp.contracts import Selector, SelectorKind


def test_active_selector_is_default() -> None:
    selector = Selector.create(None, None)

    assert selector.by == SelectorKind.ACTIVE
    assert selector.value == ""


def test_index_selector_converts_to_integer() -> None:
    selector = Selector.create("index", "3")

    assert selector.to_com_value() == 3


def test_non_index_selector_preserves_text_value() -> None:
    selector = Selector.create("completeName", "Pool/Road/Main")

    assert selector.by == SelectorKind.COMPLETE_NAME
    assert selector.to_com_value() == "Pool/Road/Main"


def test_index_selector_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        Selector.create("index", "-1")


def test_named_selector_requires_value() -> None:
    with pytest.raises(ValueError):
        Selector.create("name", "")