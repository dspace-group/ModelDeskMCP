# ModelDesk MCP Server

Connect an MCP client to local ModelDesk Automation/COM through **83 tools** for vehicle parameterization, roads, traffic scenarios, scene assets, testing, and capture comparison.

This early-release server runs on Windows over local **stdio**. It is distributed as a Python source checkout, not a bundled ModelDesk installation or executable. ModelDesk, projects, models, and simulation assets remain on the machine running the server.

Start with [docs/clients.md](docs/clients.md) for client setup, [docs/use-cases.md](docs/use-cases.md) for workflows, or [docs/tools.md](docs/tools.md) for the complete grouped tool reference.

## Prerequisites

- Windows 10 or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage Python 3.14 and project dependencies
- A local ModelDesk installation with working COM registration for automation tools
- An MCP client that supports local stdio servers, such as VS Code
- The required ModelDesk project, model files, and runtime or visualization configuration for your workflow

The Python server itself does not require Docker, Node.js, or .NET. Processing, MATLAB model bindings, runtime execution, and AURELION synchronization can require additional locally installed components.

## Quick Start

From the checkout root:

```powershell
uv sync
.\ModelDeskMCP.cmd --version
uv run python -m modeldesk_mcp.smoke --skip-com-status
```

uv creates and manages a project-local `.venv`; no manual activation is needed. Dependency installation requires access to your approved package index. See [docs/clients.md](docs/clients.md) for package-source and startup troubleshooting.

## MCP client configuration

Add the following server entry to your VS Code MCP configuration. Keep unrelated entries in [.vscode/mcp.json](.vscode/mcp.json).

```json
{
  "servers": {
    "modeldesk-mcp": {
      "type": "stdio",
      "command": "${workspaceFolder}\\ModelDeskMCP.cmd",
      "args": [],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

The client starts and owns the server process. With no arguments, [ModelDeskMCP.cmd](ModelDeskMCP.cmd) starts the MCP stdio session; it does not open a web server or print an interactive prompt. The launcher uses `uv` from PATH, or falls back to `py -3.14 -m uv` when that module is installed.

Other entry points are `uv run python -m modeldesk_mcp.server`, `uv run python server.py`, and the installed `modeldesk-mcp` command. For other clients, use an absolute launcher path and the checkout as the working directory; see [docs/clients.md](docs/clients.md).

## Typical safe workflow

1. Connect the client and call `modeldesk_get_status` and `modeldesk_get_capabilities`.
2. Inspect the active project, experiment, and domain collections before selecting a target.
3. Use `modeldesk_list_tools_by_use_case` or `modeldesk_get_workflow_plan` to plan the next calls.
4. Back up project content before edits. Keep `save` and `download` false unless explicitly required.
5. Execute dependent calls sequentially, then inspect the updated state.
6. Save, download, process, execute, or synchronize only when those actions are intended.

Disabling Save/Download does not prevent in-memory edits. Multi-step mutations are not transactions and can leave partial changes on failure. Context-switch tools can save by default, and starting a maneuver can download by default; inspect the relevant input schema before calling them.

## Tool overview

The complete [docs/tools.md](docs/tools.md) reference lists each tool exactly once, grouped by purpose:

| Group | Tools | Scope |
| --- | ---: | --- |
| Shared infrastructure | 14 | Status, project and experiment lifecycle, pools, workflow discovery, AURELION |
| UC1: Vehicle parameterization | 11 | Model bindings, parameter sets and values, processing |
| UC2: Roads | 18 | Networks, segments, lanes, objects, connections |
| UC3: Scenarios and traffic | 22 | Fellows, maneuvers, behavior profiles, road and vehicle references, runtime controls |
| UC4: Traffic objects | 8 | Catalog objects, folders, reference validation |
| UC5: Tests and analysis | 10 | Test cases, plotting, MATLAB capture comparison |
| **Total** | **83** | Fixed `modeldesk_` tool names |

Some tools support multiple use cases. MCP use-case lookup includes those overlaps, while the reference avoids duplicate entries. Internally, the registry has five ownership domains; these are distinct from the six documentation groups.

## Responses and limits

Every tool returns the same seven top-level fields: `ok`, `operation`, `sessionId`, `data`, `warnings`, `artifacts`, and `error`. Check `ok` before using `data`; failure details and recovery guidance are in `error`. See [docs/error-handling.md](docs/error-handling.md).

- Ego-only `StartPosition` and `InitialLongitudinalVelocity` must not be assigned to Fellows. Fellow Position and Velocity behavior profiles are explicit, mutually exclusive alternatives.
- Maneuver reordering is not supported: an already-matching order can be confirmed, but a changed order is rejected.
- Catalog editing, processing, testing, and visualization depend on the active installation and project context.
- Tool availability and deterministic tests do not establish that every operation works in every live ModelDesk environment.

The server registers tools only: no MCP resources or prompts are registered.

## Verification and development

Run from the checkout root:

```powershell
uv sync --extra dev
uv run python -m compileall src server.py
uv run pytest
uv run python -m modeldesk_mcp.smoke --skip-com-status
.\ModelDeskMCP.cmd --list-tools
.\ModelDeskMCP.cmd --list-resources
.\ModelDeskMCP.cmd --list-prompts
```

These checks are COM-free. Metadata flags exit after printing their result; use them to verify startup without opening a ModelDesk session. `uv build` can produce an sdist and wheel, but the checkout remains the documented deployment path.

The lockfile pins dependencies. GitHub CI uses Windows, Python 3.14, and a job-scoped public PyPI index so that organization-local mirror URLs do not prevent hosted runners from installing packages. Local package policy is not changed by that CI setting.

The request path is MCPServer -> registry -> service -> COM gateway -> bounded STA dispatcher -> ModelDesk. See [docs/architecture.md](docs/architecture.md) and [docs/extending.md](docs/extending.md) for implementation details.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Client cannot start the server | Verify the launcher path, working directory, and `uv` availability; restart the client after PATH changes. |
| Package download or DNS failure | Check whether the configured index and locked download hosts are reachable from that machine. |
| COM operation fails | Check local ModelDesk installation, COM registration, active project/experiment, and requested domain. |
| Tool schema appears outdated | Restart the MCP server after source changes and refresh the client's tool list. |
| Mutation fails partway through | Reinspect the collection and affected values before retrying; do not assume rollback. |

## Documentation index

| Document | Contents |
| --- | --- |
| [docs/tools.md](docs/tools.md) | All 83 tools, grouped by purpose and effects |
| [docs/use-cases.md](docs/use-cases.md) | Practical workflows and domain-specific constraints |
| [docs/clients.md](docs/clients.md) | VS Code and other stdio clients, startup, package sources |
| [docs/error-handling.md](docs/error-handling.md) | Response envelope, validation, recovery, partial changes |
| [docs/architecture.md](docs/architecture.md) | Modules, request flow, COM threading, verification boundaries |
| [docs/extending.md](docs/extending.md) | Adding tools and keeping contracts, tests, and documentation aligned |

## Support

For technical questions and issues related to the dSPACE MCP Servers and related GitHub repositories, please open a GitHub issue.
As a valued dSPACE customer, you are always welcome to contact dSPACE Support directly via <http://www.dspace.com/go/supportrequest>.
