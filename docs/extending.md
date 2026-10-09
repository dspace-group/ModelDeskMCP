# Extending the Server

[../README.md](../README.md) | [architecture.md](architecture.md) | [tools.md](tools.md)

Keep the public contract explicit and route all automation through the existing service, gateway, and STA dispatcher. An extension must be grounded in the actual automation interface, not in properties that merely sound plausible in the UI.

## Implementation Checklist

1. Verify the owning COM object, supported members, units, selectors, and side effects using an interface definition or a controlled live fixture.
2. Add typed request parsing/validation in [../src/modeldesk_mcp/contracts/requests.py](../src/modeldesk_mcp/contracts/requests.py) where the input has domain-specific structure.
3. Implement the operation in [../src/modeldesk_mcp/com_bridge/gateway.py](../src/modeldesk_mcp/com_bridge/gateway.py). Resolve child objects per call and dispatch COM work through the STA worker.
4. Add the forwarding method in [../src/modeldesk_mcp/domain/service.py](../src/modeldesk_mcp/domain/service.py), preserving the common response contract.
5. Register the wrapper, owner domain, input descriptions/examples, and output envelope in [../src/modeldesk_mcp/tools/registry.py](../src/modeldesk_mcp/tools/registry.py).
6. Assign use-case tags in [../src/modeldesk_mcp/contracts/use_cases.py](../src/modeldesk_mcp/contracts/use_cases.py). Add a dry-run recipe only when a repeatable workflow needs one.
7. Add focused deterministic coverage using the existing domain test module and helpers.
8. Update the customer documentation and fixed-inventory gates, then run the relevant verification commands.

Adding a new tool is a deliberate public API change. The existing 83-name contract is not a dynamic discovery mechanism; do not silently append or rename tools without updating its consumers.

## Contract Rules

| Area | Rule |
| --- | --- |
| Tool names | Use a unique, lowercase `modeldesk_` name and one registry owner domain. |
| Inputs | Use the established camel-case argument style and SDK-native metadata; include verified examples rather than guessed project names. |
| JSON payloads | Validate shape, supported keys, finite values, and mutually exclusive modes before mutation where possible. |
| Selectors | State exactly which kinds are supported and whether an index is zero-based. |
| Results | Return the common `ToolResult` envelope and operation-specific data; do not serialize raw COM objects. |
| Persistence | Keep edit-tool Save/Download opt-in and execute them only after successful required checks/readbacks. |
| Failures | Preserve structured recovery guidance, redact exception paths, and disclose partial changes instead of promising rollback. |
| Planning | Return recipes as dry-run guidance, never silently execute their steps. |

Do not infer an object's ownership from a successful nested assignment. Ego initial values and Fellow behavior-profile constants are separate contracts. Do not invent setters for immutable members or a universal lateral/profile schema.

## Test Strategy

Use source-shaped fakes that expose the real object hierarchy, read-only members, selector behavior, and available methods. A fake that accepts arbitrary attributes or string removals can conceal a live incompatibility.

Cover the intended success path, invalid input before mutation, unavailable/ambiguous context, and the relevant Save/Download ordering. For multi-step edits, test a late failure and make the remaining state explicit. Keep tests COM-free; do not start ModelDesk or execute runtime actions from deterministic tests.

Reuse [../tests/test_cli_and_skill.py](../tests/test_cli_and_skill.py) and [../tests/test_expected_tools.py](../tests/test_expected_tools.py) for metadata, registry, and SDK-schema coverage. Dispatcher lifecycle tests live in [../tests/test_com_dispatcher.py](../tests/test_com_dispatcher.py).

## Inventory and Documentation

When changing the tool surface, update these related contracts together:

- Registry names, ownership, registration order, and input metadata.
- Use-case tags and any recipes that reference the operation.
- [tools.md](tools.md), the relevant section of [use-cases.md](use-cases.md), and README counts when applicable.
- The tool index in [../.github/skills/modeldesk-mcp-tools/SKILL.md](../.github/skills/modeldesk-mcp-tools/SKILL.md).
- Fixed name/count assertions in tests, smoke checks, and [../.github/workflows/python-tests.yml](../.github/workflows/python-tests.yml).

Keep customer-facing documentation factual. Distinguish MCP support from broader ModelDesk features and do not copy private product source or vendor-only documentation into the repository.

## Verification

From the checkout root:

```powershell
uv sync --extra dev
uv run pytest tests/test_expected_tools.py tests/test_cli_and_skill.py
uv run pytest
uv run python -m compileall src server.py
uv run python -m modeldesk_mcp.smoke --skip-com-status
```

Run the focused domain test after the first implementation change, then the applicable shared-contract gates. A controlled live check is additional evidence, not a substitute for deterministic tests. Obtain explicit intent for live edits, persistence, downloads, and execution, and remove only temporary objects created by the check.
