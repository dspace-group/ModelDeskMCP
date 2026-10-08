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

## Local tool schemas

`tools/list` describes every registered input property and includes examples where a repository-verified example exists. `modeldesk_activate_test.testName` has no example because valid test names depend on the installed ModelDesk project. Every tool declares the stable lower-camel `ToolResult` envelope (`ok`, `operation`, `sessionId`, `data`, `warnings`, `artifacts`, and `error`). The `data` field remains intentionally flexible because its payload is operation-specific; clients should use each tool's description and returned operation data rather than assume one nested schema applies to all tools.

## Local-only constraints

The server is not a hosted service and does not provide authentication, remote session management, or a multi-user API. It is designed for a trusted local environment that already contains ModelDesk and the necessary project assets.
