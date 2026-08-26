# Extending the server

The public contract is centered on a stable registry, a narrow service layer, and a single COM gateway.

## When extending the server

1. Add or update the public tool definition in the registry.
2. Keep the tool name and schema explicit and deterministic.
3. Add or update the corresponding service logic.
4. Route all ModelDesk COM calls through the gateway and `ComStaDispatcher`.
5. Add a deterministic test that validates the contract without requiring a live ModelDesk instance.

## Contract boundaries

- Registry: tool names, metadata, and public schema
- Service: domain-specific translation and validation
- Gateway: COM invocation boundary and timeout handling
- Tests: deterministic contract validation and smoke coverage

## Avoid

- Caching deep COM child objects across tool calls
- Broadening the public registry without an explicit contract reason
- Reusing internal source/module details in public docs
- Publishing ModelDesk product documentation or vendor-only references in this repo

## Skill and generator drift

If backend tooling generates skills or registry metadata, ensure the generated outputs remain aligned with the checked-in public contract. The public build contract here is limited to the source-only server and its documentation, not to backend-only generation workflows.
