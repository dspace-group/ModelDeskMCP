"""Configuration loading for the ModelDesk MCP server."""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_PROG_ID = "ModelDesk.Application"
DEFAULT_OPERATION_TIMEOUT_SECONDS = 60
DEFAULT_MAX_COLLECTION_ITEMS = 500


@dataclass(frozen=True, slots=True)
class ComGatewayOptions:
    """Configuration values used by the COM automation gateway."""

    prog_id: str = DEFAULT_PROG_ID
    operation_timeout_seconds: int = DEFAULT_OPERATION_TIMEOUT_SECONDS
    max_collection_items: int = DEFAULT_MAX_COLLECTION_ITEMS

    @staticmethod
    def load_from_environment() -> "ComGatewayOptions":
        """Load gateway options from environment variables with safe defaults."""

        prog_id = os.environ.get("MODELDESK_MCP_PROG_ID", DEFAULT_PROG_ID).strip()
        if prog_id == "":
            prog_id = DEFAULT_PROG_ID

        timeout = _read_positive_int(
            "MODELDESK_MCP_OPERATION_TIMEOUT_SECONDS",
            DEFAULT_OPERATION_TIMEOUT_SECONDS,
        )
        max_items = _read_positive_int(
            "MODELDESK_MCP_MAX_COLLECTION_ITEMS",
            DEFAULT_MAX_COLLECTION_ITEMS,
        )
        return ComGatewayOptions(
            prog_id=prog_id,
            operation_timeout_seconds=timeout,
            max_collection_items=max_items,
        )


def _read_positive_int(name: str, default_value: int) -> int:
    """Read a positive integer environment value."""

    raw_value = os.environ.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default_value

    try:
        parsed_value = int(raw_value, 10)
    except ValueError:
        return default_value

    if parsed_value <= 0:
        return default_value

    return parsed_value