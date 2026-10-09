# Error Handling

[../README.md](../README.md) | [tools.md](tools.md) | [clients.md](clients.md)

Tool handlers return structured results so clients can distinguish successful operations from validation, context, and automation failures. Do not infer success solely from an MCP response being received.

## Result Envelope

All handler results use these seven lower-camel fields:

| Field | Meaning |
| --- | --- |
| `ok` | Whether the requested operation completed successfully. |
| `operation` | Registered operation name. |
| `sessionId` | Identifier of the component/session that produced the result. |
| `data` | Operation-specific payload on success; null on failure. |
| `warnings` | Additional warnings; an empty array is valid. |
| `artifacts` | Artifact references with `kind`, `path`, and optional `description`. |
| `error` | Structured failure details, or null on success. |

`data` is intentionally flexible. A domain summary, status result, mutation result, and capture comparison do not have the same nested shape. Optional properties can be null even when `ok=true`.

Workflow plans use a separate local catalog session from the COM gateway. A different `sessionId` on a planning response does not imply a different ModelDesk application was opened.

## Error Fields

| Field | Meaning |
| --- | --- |
| `errorType` | Failure classification used for recovery. |
| `message` | Human-readable explanation. |
| `operation` | The failed operation. |
| `recovery` | Suggested next action, when available. |
| `isRetryable` | Whether retry might be useful; not permission for a blind retry. |

Example validation result:

```json
{
	"ok": false,
	"operation": "modeldesk_get_workflow_plan",
	"sessionId": "example-session",
	"data": null,
	"warnings": [],
	"artifacts": [],
	"error": {
		"errorType": "validation",
		"message": "Workflow name must not be empty.",
		"operation": "modeldesk_get_workflow_plan",
		"recovery": "Use one of the documented workflow names.",
		"isRetryable": false
	}
}
```

Invalid protocol messages or arguments rejected by the MCP SDK can fail before a tool handler runs; those transport/schema failures are distinct from this application-level envelope.

## Common Failure Types

| Type | Typical cause | Recovery |
| --- | --- | --- |
| `validation` | Invalid selector, JSON, number, shape, or unsupported property assignment. | Correct the input; do not repeat it unchanged. |
| `not_found` | Missing file or unknown workflow name. | Verify the path/content or use a registered recipe. |
| `invalid_state` | No active project/experiment, unavailable runtime context, or an unsupported state change. | Refresh status and inspect the requested domain. |
| `timeout` | Caller stopped waiting for a dispatched COM operation. | Treat mutation outcome as uncertain; inspect before retrying. |
| `com_error` | Failure reported by Windows COM or the active ModelDesk object. | Inspect installation, registration, and active context. |
| `unexpected` | An exception outside the known classifications. | Capture the operation and sanitized result for an issue report. |

For example, a changed maneuver order is rejected with an unsupported-reordering message; clients must not require a separate `unsupported` error type to recognize that limitation.

## Validation and JSON Inputs

The MCP `tools/list` schema describes parameters, defaults, and verified examples. Values ending in `Json` are JSON-encoded strings; malformed JSON is not a property patch. Project-specific test names have no universal example.

Typed request validation catches many errors before COM traversal, including non-finite numeric values, unsupported road fields, and ego-only initial fields submitted for a Fellow. Other checks require the selected live object, so validation is not a universal guarantee of zero COM access.

Use explicit selectors from fresh listings. Support for `active`, names, and indices varies by scope. In particular, use listed indices for Fellow sequence deletion and do not assume a name selector works everywhere.

## Partial Changes and Persistence

There is no transaction or automatic rollback around a multi-step ModelDesk operation. A later assignment, readback, Save, or Download failure can leave earlier in-memory changes in place.

`save=false` and `download=false` suppress those follow-up operations; they do not make editing tools read-only. Profile updates read back their assigned values before persistence, but a successful assignment followed by a readback error can still have changed the object.

After a failed mutation:

1. Stop dependent write calls.
2. Refresh status, the relevant summary, and the affected collection.
3. Determine which items/values exist now, rather than assuming the old snapshot remains valid.
4. Resolve selectors again; additions and removals can shift indices.
5. Retry only the required remaining operation, with persistence/runtime intent still explicit.

Do not remove or restore objects that were not part of the intended operation. Recovery can itself change user data.

## Timeouts and Concurrent Calls

The default COM wait timeout is 60 seconds. It bounds the caller's wait, not the COM operation itself: queued or running work is not cancelled when the waiter times out. A timed-out edit may complete afterward.

The STA dispatcher serializes submitted operations, but concurrent MCP requests do not establish a dependency order. Do not send an edit and a dependent read in the same parallel batch. Wait for the edit result, then issue the read separately. After timeout, establish that the outstanding operation has settled before using the next inspection as a final-state guarantee.

A client-level timeout can expire independently of the server timeout. See [clients.md](clients.md) for server environment variables.

## Paths and Trust Boundary

Exception-derived messages redact local absolute paths. Useful domain data and artifact references can still contain paths, names, and project details; the server does not anonymize the complete response.

This is a trusted local stdio integration, not an authenticated hosted or multi-user API. Restrict who can invoke it and review requested file access, edits, execution, and persistence accordingly.

## Reporting a Failure

Include the tool name, sanitized inputs, `errorType`, message, warnings, and the active domain/context needed to reproduce it. State whether Save/Download or runtime actions were requested and whether a timeout occurred. Avoid credentials and unrelated private project content.

Deterministic pytest and `modeldesk_mcp.smoke --skip-com-status` validate the server without live COM. They do not replace a controlled live reproduction when installation-specific behavior is involved.
