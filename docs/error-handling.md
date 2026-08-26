# Error handling

The public server contract prefers structured, recoverable results over unhandled exceptions.

## Rules

- Tool entry points return structured `ToolResult` dictionaries.
- Application-level failures are translated into explicit status values rather than raw stack traces.
- COM and gateway failures are bounded by operating timeouts and should report the failure in the result payload.
- The server should not expose machine-specific local paths in generic error payloads.

## Safe failure behavior

When a ModelDesk operation cannot proceed, the result should indicate the failure in a structured form and remain within the valid tool contract. This makes the server easier to validate in automated tests and safer for MCP clients that do not parse arbitrary exception strings.

## COM-free validation

The deterministic tests and the smoke path do not require a live ModelDesk session. They validate the request/response layer and the registry contract without invoking the COM backend.

## Local-only constraints

The server is not a hosted service and does not provide authentication, remote session management, or a multi-user API. It is designed for a trusted local environment that already contains ModelDesk and the necessary project assets.
