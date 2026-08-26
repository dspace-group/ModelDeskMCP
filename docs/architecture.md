# Architecture

This repository contains a small Python server that exposes ModelDesk automation as a local MCP endpoint over stdio. The public-safe architecture is intentionally limited to the server’s own runtime boundaries and does not describe proprietary product internals beyond the local COM integration points required to operate the automation layer.

## 1. Local stdio host

The server is started from the checkout launcher or Python module entry point and runs as a local stdio application. The host process connects to the MCP server over standard input and output; no network listener is required for the default public execution model.

The entrypoint in the repository is intentionally narrow:

- launch script or `python -m modeldesk_mcp`
- `main()` in the server module
- metadata flags such as `--version`, `--list-tools`, `--list-resources`, and `--list-prompts` that return immediate output without starting the full COM-backed runtime
- normal execution path that boots the full FastMCP application

## 2. FastMCP server runtime

The server creates a `FastMCP` instance using the MCP Python SDK v1 API that is compatible with the project’s supported dependency line. This app owns the public MCP surface: tool registration, request dispatch, stdio transport, and the CLI metadata mode.

The public contract is intentionally explicit. Tool names are registered in a dedicated registry module and exposed to the host as typed MCP tool calls. The server does not promise dynamic discovery beyond the checked registry and the metadata commands listed above.

## 3. Registry and tool wrappers

The adapter layer registers tool definitions into the FastMCP app through a registry wrapper. In public terms, the registry sits between the host-facing MCP surface and the business logic service layer.

This pattern keeps the tool contract stable:

- registry defines the public tool names and schema metadata
- tool wrappers translate function arguments into the service call model
- the service layer does not directly depend on the stdio transport or the host protocol details
- the server returns structured `ToolResult` dictionaries for user-recoverable outcomes instead of throwing application-level exceptions into the host

For this repo, the public tool domain is intentionally centered on the five supported areas already defined in the registry:

1. General COM Automation — the general ownership bucket for lifecycle, parameter, processing, testing, and workflow tools that do not belong to one of the specialized domains.
2. Scenario/TrafficScenario — scenario orchestration and traffic-scenario operations.
3. Road/RoadGenerator — road network creation, activation, editing, and road-generation utilities.
4. Plotting/PlotManager — plotting, capture, comparison, and plot-management operations.
5. TrafficObjectManager/TrafficObject/TOM — traffic object catalog, folder management, and traffic-object manager operations.

These are the five public domain labels and ownership boundaries enforced by the registry, and they are intentionally not redefined as a separate project taxonomy. The exact names and behavior are the source of truth for the runtime, and they are not rewritten here to avoid a public contract drift.

## 4. ModelDeskService and workflow catalog

The runtime creates a service object that owns the domain model for automation operations. This service coordinates workflow selection, execution orchestration, and state management for the ModelDesk automation layer.

The service is not the COM transport itself. It consumes a gateway abstraction and applies the repository’s explicit workflow catalog, so the public logic remains stable while the underlying automation layer can be swapped or reselected by selector without exposing product internals.

## 5. ModelDeskAutomationGateway and COM boundary

The service talks to a gateway object that isolates the automation layer from MCP transport concerns. The gateway is the boundary where the server can interact with local Windows COM automation without exposing those calls directly to the tool registry.

The public-safe boundary is:

- service layer stays domain-oriented
- gateway handles automation coordination and command translation
- COM-specific access stays behind the dedicated bridge package
- all external automation calls are routed through a dispatcher that enforces threading and lifecycle safety

## 6. ComStaDispatcher STA thread

The dispatch layer runs automation operations on an STA thread. This is the boundary used to keep COM access safe and deterministic on Windows. The dispatcher does not cache deep child objects across tool calls; instead, it reacquires the target object or selector state per operation.

This is a security and reliability requirement. The public architecture must avoid keeping long-lived references to deep COM object graphs, because those references can go stale and create invalid automation state between requests.

## 7. COM accessor and local ModelDesk runtime

The underlying Windows-side COM accessor opens the local ModelDesk automation object when required and uses the active selector to reacquire a fresh object reference for each tool call. The server keeps the COM access narrow and explicit, rather than caching nested child objects across requests.

This reduces the risk of stale handles, thread-affinity problems, and cross-request state leakage. In other words, the request path is:

1. stdio host sends an MCP request
2. FastMCP server resolves the registered tool
3. registry wrapper calls the domain service
4. service requests the automation gateway
5. gateway dispatches the call through the STA thread
6. COM accessor reacquires the selector target and performs the local automation work
7. result is converted into a structured `ToolResult` response

## 8. Request flow and `ToolResult` response model

The request lifecycle is intentionally simple and predictable:

- the host sends a tool call over stdio
- the MCP runtime resolves the tool name
- the wrapper validates input and forwards the request to the service
- the service executes the workflow or automation action
- the gateway performs the COM-bound step through the STA dispatcher
- the final result is normalized into a structured `ToolResult` dictionary

Structured error output is used for user-recoverable problems. The public contract avoids leaking low-level COM details or internal stack traces into the host. Bounded timeouts help prevent long-running desktop automation calls from hanging the server or the client session.

## 9. Redacted errors, bounded timeouts, and selector safety

The server follows a narrow error boundary:

- domain and automation failures are converted into structured, redacted results
- host-facing messages omit internal private implementation details
- long-running operations are bounded by configured timeouts
- selector-based reacquisition is used instead of deep COM object retention

This keeps the server robust under repeated tool calls without creating stale references or letting the client see internal implementation details.

## 10. Extension and testing boundaries

This public architecture intentionally separates the supported extension boundary from internal implementation details:

- the public extension boundary is the MCP tool registry, tool metadata, and the domain service contract
- seller-specific or private product architecture is not documented here
- backend implementation and runtime behavior are not changed in this task
- deterministic tests remain separate from live COM automation and are designed to exercise the public logic without requiring a live ModelDesk runtime

The same boundary also applies to the repository’s testing model: unit and smoke tests validate the public contract, local metadata commands, compile integrity, and COM-free behavior without depending on a live desktop automation session.

## 11. Summary

The public architecture is therefore a narrow local stdio host -> FastMCP -> registry wrappers -> ModelDeskService -> gateway -> ComStaDispatcher -> COM accessor -> local ModelDesk automation pipeline. The server remains explicit, bounded, and safe: tool calls are structured, errors are redacted, COM references are reacquired by selector rather than cached deeply, and the public docs stay within the repository’s supported, public-safe contract.
