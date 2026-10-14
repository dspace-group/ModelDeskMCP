"""Structured response models returned by ModelDesk MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """References an artifact produced or used by an MCP tool operation."""

    kind: str
    path: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ToolError:
    """Describes a structured MCP tool failure at the public error boundary."""

    error_type: str
    message: str
    operation: str
    recovery: str | None = None
    is_retryable: bool = False


_QUOTED_ABSOLUTE_PATH_PATTERN = re.compile(
    r"""(?i)(?P<quote>['"])(?:[a-z]:[\\/]|\\\\|/(?!/))(?:(?!(?P=quote))[^\r\n])*(?P=quote)"""
)
_SPACED_FILE_PATH_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9_])(?:[a-z]:[\\/]|\\\\|/(?!/))[^<>:\"'|?*\r\n,;)}\]]*?\.[a-z0-9][a-z0-9._-]*(?=$|[\s,;)}\]])"
)
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9_])(?:[a-z]:[\\/]|\\\\|/(?!/))[^<>:\"'|?*\r\n\s,;)}\]]+"
)


def public_error_message(message: object) -> str:
    """Return exception text suitable for a public structured tool error.

    Domain results may still contain useful artifact paths returned by ModelDesk.
    Only exception-derived messages are normalized here so local machine paths
    are not copied into generic MCP error text.
    """

    text = str(message).strip()
    if text == "":
        return "The operation failed without additional details."
    text = _QUOTED_ABSOLUTE_PATH_PATTERN.sub("[local path]", text)
    text = _SPACED_FILE_PATH_PATTERN.sub("[local path]", text)
    return _ABSOLUTE_PATH_PATTERN.sub("[local path]", text)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Represents the standard structured result returned by MCP tools."""

    ok: bool
    operation: str
    session_id: str
    data: Any | None
    warnings: tuple[str, ...]
    artifacts: tuple[ArtifactRef, ...]
    error: ToolError | None

    @staticmethod
    def success(
        operation: str,
        session_id: str,
        data: Any,
        warnings: tuple[str, ...] | None = None,
        artifacts: tuple[ArtifactRef, ...] | None = None,
    ) -> "ToolResult":
        """Create a successful tool result."""

        return ToolResult(
            ok=True,
            operation=operation,
            session_id=session_id,
            data=data,
            warnings=warnings or (),
            artifacts=artifacts or (),
            error=None,
        )

    @staticmethod
    def failure(
        operation: str,
        session_id: str,
        error: ToolError,
        warnings: tuple[str, ...] | None = None,
        artifacts: tuple[ArtifactRef, ...] | None = None,
    ) -> "ToolResult":
        """Create a failed tool result."""

        return ToolResult(
            ok=False,
            operation=operation,
            session_id=session_id,
            data=None,
            warnings=warnings or (),
            artifacts=artifacts or (),
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the result into MCP-friendly lower-camel structured data."""

        return to_plain_data(self)


@dataclass(frozen=True, slots=True)
class ItemSummary:
    """Summarizes one item from a ModelDesk collection."""

    index: int
    name: str
    kind: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class DomainSummary:
    """Summarizes a ModelDesk domain or collection exposed through MCP."""

    domain: str
    available: bool
    count: int
    items: tuple[ItemSummary, ...]
    properties: dict[str, str | None]
    message: str | None = None
    next_offset: int | None = None


@dataclass(frozen=True, slots=True)
class OperationInfo:
    """Reports the outcome of a command-style MCP operation."""

    operation: str
    completed: bool
    message: str | None = None
    details: dict[str, str | None] | None = None


@dataclass(frozen=True, slots=True)
class ModelDeskStatus:
    """Reports ModelDesk Automation reachability and active context state."""

    session_id: str
    model_desk_reachable: bool
    model_desk_version: str | None
    has_active_project: bool
    active_project_name: str | None
    active_experiment_name: str | None
    prog_id: str
    process_architecture: str


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """Reports runtime, platform, and ModelDesk Automation capability state."""

    server_version: str
    dot_net_version: str | None
    operating_system: str
    is_windows: bool
    prog_id: str
    model_desk_reachable: bool
    domains: dict[str, bool]
    disabled_capabilities: tuple[str, ...]
    python_version: str


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Describes the active ModelDesk project state."""

    has_active_project: bool
    name: str | None
    working_root: str | None
    active_experiment_name: str | None


@dataclass(frozen=True, slots=True)
class ProjectPoolFileCreationInfo:
    """Reports the outcome of a project-pool file creation request."""

    file_type: str
    type_id: int
    name: str
    expected_extension: str
    overwrite_existing: bool
    created_name: str | None
    created_path: str | None
    created_type_name: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ParameterValueInfo:
    """Describes a parameter value read from or written to a parameter set."""

    parameter_path: str
    name: str | None
    type_name: str | None
    unit: str | None
    value: str | None
    numeric_value: float | None


@dataclass(frozen=True, slots=True)
class BasicRoadCreatedTrafficObject:
    """Describes a traffic object placed during basic road creation."""

    name: str | None
    catalog_path: str | None
    s: float
    d: float
    lane_mapping: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BasicRoadTrafficObjectSpec:
    """Describes a traffic object requested for basic road placement."""

    name: str | None
    catalog_path: str | None
    s: float
    d: float
    lane_mapping: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BasicRoadCreationInfo:
    """Reports the result of a basic straight-road creation operation."""

    road_name: str
    length: float
    left_lane_count: int
    right_lane_count: int
    lane_width: float
    segment_count: int
    lane_section_count: int
    traffic_object_count: int
    saved: bool
    downloaded: bool
    traffic_objects: tuple[BasicRoadCreatedTrafficObject, ...]
    message: str


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    """Describes a dry-run workflow recipe made from lower-level MCP tools."""

    name: str
    use_case: str
    dry_run_only: bool
    steps: tuple[str, ...]
    required_tools: tuple[str, ...]
    message: str | None = None


def to_plain_data(value: Any) -> Any:
    """Convert dataclasses, enums, tuples, and dicts into JSON-serializable data."""

    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {_to_camel_case(field.name): to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [to_plain_data(item) for item in value]
    return value


def _to_camel_case(name: str) -> str:
    """Convert snake_case names to lower camelCase for structured MCP output."""

    parts = name.split("_")
    if len(parts) == 1:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
