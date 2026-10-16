"""Late-bound COM access helpers used by the ModelDesk automation gateway.

Selectors are resolved inside each dispatched operation. This keeps deep COM
children from surviving across tool calls, where ModelDesk may replace or
invalidate them, while still allowing callers to return stable summaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modeldesk_mcp.contracts import ItemSummary, Selector, SelectorKind


try:
    import pywintypes

    COM_ERROR_TYPES = (pywintypes.com_error, AttributeError, TypeError, RuntimeError)
except ImportError:
    COM_ERROR_TYPES = (AttributeError, TypeError, RuntimeError)


@dataclass(frozen=True, slots=True)
class CollectionSnapshot:
    """Stores a bounded snapshot of a COM collection."""

    count: int
    items: tuple[ItemSummary, ...]
    is_truncated: bool
    next_offset: int | None = None


def try_get_property(instance: Any, property_name: str) -> tuple[bool, Any | None]:
    """Attempt to read a COM property and suppress expected lookup failures."""

    try:
        value = get_property(instance, property_name)
    except COM_ERROR_TYPES:
        return False, None
    return value is not None, value


def get_property(instance: Any, property_name: str) -> Any | None:
    """Read a COM property through Python late binding."""

    _validate_instance(instance)
    _validate_member_name(property_name)
    return getattr(instance, property_name)


def set_property(instance: Any, property_name: str, value: Any | None) -> None:
    """Write a COM property through Python late binding."""

    _validate_instance(instance)
    _validate_member_name(property_name)
    setattr(instance, property_name, value)


def invoke_method(instance: Any, method_name: str, *arguments: Any) -> Any | None:
    """Invoke a COM method through Python late binding."""

    _validate_instance(instance)
    _validate_member_name(method_name)
    method = getattr(instance, method_name)
    if not callable(method):
        raise AttributeError(f"COM member '{method_name}' is not callable.")
    return method(*arguments)


def invoke_item(collection: Any, selector: Any) -> Any | None:
    """Invoke the default Item accessor on a COM collection."""

    _validate_instance(collection)
    item_accessor = getattr(collection, "Item")
    if callable(item_accessor):
        return item_accessor(selector)
    return item_accessor[selector]


def get_string_property(instance: Any, property_name: str) -> str | None:
    """Read a COM property and convert it to string."""

    has_value, value = try_get_property(instance, property_name)
    if not has_value or value is None:
        return None
    return str(value)


def get_count(collection: Any) -> int:
    """Read the Count property from a COM collection."""

    value = get_property(collection, "Count")
    if value is None:
        return 0
    return int(value)


def snapshot_collection(collection: Any, item_kind: str, max_items: int, offset: int = 0) -> CollectionSnapshot:
    """Create a bounded summary snapshot for a COM collection."""

    if max_items <= 0:
        raise ValueError("Maximum item count must be greater than zero.")
    if offset < 0:
        raise ValueError("Collection offset must not be negative.")
    is_sequence = isinstance(collection, (tuple, list))
    count = len(collection) if is_sequence else get_count(collection)
<<<<<<< Updated upstream
    end_index = min(count, offset + max_items)
    items: list[ItemSummary] = []
    for item_index in range(offset, end_index):
=======
    end_offset = min(count, offset + max_items)
    items: list[ItemSummary] = []
    for item_index in range(offset, end_offset):
>>>>>>> Stashed changes
        item = collection[item_index] if is_sequence else invoke_item(collection, item_index)
        if item is None:
            name = f"{item_kind} {item_index}"
            path = None
            kind = item_kind
        elif isinstance(item, (str, int, float, bool)):
            name = str(item)
            path = None
            kind = item_kind
        else:
            name = read_display_name(item, item_kind, item_index)
            path = get_first_string_property(item, "Path", "CompleteName", "FileName")
            kind = get_first_string_property(item, "TypeName", "Kind", "ObjectType")
        items.append(ItemSummary(item_index, name, kind, path))
<<<<<<< Updated upstream
    is_truncated = end_index < count
    return CollectionSnapshot(count, tuple(items), is_truncated, end_index if is_truncated else None)
=======
    is_truncated = end_offset < count
    return CollectionSnapshot(count, tuple(items), is_truncated, end_offset if is_truncated else None)
>>>>>>> Stashed changes


def resolve_item(collection: Any, selector: Selector) -> Any:
    """Resolve a non-active selector against a COM collection."""

    selector.validate()
    if selector.by == SelectorKind.ACTIVE:
        raise ValueError("Active selector is not valid for a collection item.")
    item = invoke_item(collection, selector.to_com_value())
    if item is None:
        raise RuntimeError(f"No item found for selector '{selector.by.value}:{selector.value}'.")
    return item


def read_properties(instance: Any, *property_names: str) -> dict[str, str | None]:
    """Read several COM properties as strings."""

    return {property_name: get_string_property(instance, property_name) for property_name in property_names}


def read_display_name(instance: Any, fallback_kind: str, fallback_index: int) -> str:
    """Read the first available display-name property or create a fallback."""

    name = get_first_string_property(instance, "Name", "CompleteName", "Path", "FileName", "TypeName")
    if name is not None and name.strip() != "":
        return name
    return f"{fallback_kind} {fallback_index}"


def get_first_string_property(instance: Any, *property_names: str) -> str | None:
    """Read the first non-empty string property from a COM object."""

    for property_name in property_names:
        value = get_string_property(instance, property_name)
        if value is not None and value.strip() != "":
            return value
    return None


def _validate_instance(instance: Any) -> None:
    if instance is None:
        raise ValueError("COM object instance must not be None.")


def _validate_member_name(member_name: str) -> None:
    if member_name.strip() == "":
        raise ValueError("COM member name must not be empty.")
