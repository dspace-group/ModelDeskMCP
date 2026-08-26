# ModelDesk MCP Server

ModelDesk MCP is an early-release, source-only Windows server for exposing ModelDesk Automation/COM capabilities to MCP clients over local stdio.

This repository contains the Python 3.14 source checkout for the server. It does not bundle ModelDesk, project files, executables, packaged resources, or a release artifact. ModelDesk and the relevant ModelDesk project assets remain local to the machine running the server, and COM-backed tools require a working local ModelDesk installation and COM registration.

## Product summary

The server is intended for local use in desktop MCP clients and editor integrations. It presents a stable tool registry, accepts structured MCP requests, and routes ModelDesk operations through a single COM gateway with a bounded STA dispatcher. The public surface is intentionally explicit: a fixed registry, known tool domains, and deterministic test coverage that does not depend on a live ModelDesk session.

## Prerequisites

- Windows 10 or later
- Python 3.14 installed through `py -3.14`
- ModelDesk installed and registered for COM automation where COM-backed tools will be used
- An MCP-capable client that supports local stdio servers
- A ModelDesk project or test content you can safely access and, when necessary, back up

No Docker, Node.js, or .NET runtime is required for the Python server itself.

## Source installation

From a PowerShell prompt in this repository:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

If activation is blocked, run the editable install directly with `py -3.14 -m pip install -e ".[test]"` and use `py -3.14` for the commands below.

## Local stdio behavior

The server runs as a local stdio MCP process. When started without arguments, it listens on standard input/output for MCP requests. Any metadata-style CLI flags are part of the backend contract and are forwarded through the source-checkout launcher; the launcher itself is only responsible for invoking the local checkout in a predictable way.

## MCP client configuration

The repository includes a VS Code example in `.vscode/mcp.json`. Use the launcher from the checkout root:

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

The matching source-checkout launcher is:

```bat
@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
py -3.14 -m modeldesk_mcp.server %*
exit /b %ERRORLEVEL%
```

The launcher forwards all arguments with `%*`. When no arguments are provided, the server starts in stdio mode.

## Typical safe workflow

1. Install the checkout in editable mode.
2. Run a COM-free smoke check before touching a real ModelDesk project.
3. Connect the client to the local stdio server.
4. Start with read-only discovery tools and status checks.
5. Make a backup before running tools that create, edit, save, execute, or close ModelDesk content.
6. Keep ModelDesk operations scoped to a controlled project or test case.

## Tool domains and public inventory

The registry exposes 83 tools across five public domains:

- General automation and application orchestration
- Scenario and traffic-scenario operations
- Road and road-generator utilities
- Plotting and capture management
- Traffic object catalog and TOM operations

The public tool names are intentionally namespaced with the `modeldesk_` prefix and are fixed by the registry contract. They are not dynamically discovered from the filesystem at runtime.

## Server verification commands

Run these commands from the repository root:

```powershell
py -3.14 -m pip install -e ".[test]"
py -3.14 -m compileall src server.py
py -3.14 -m pytest -q
py -3.14 -m modeldesk_mcp.smoke --skip-com-status
.\ModelDeskMCP.cmd --help
```

Use the launcher directly in MCP clients; the check commands validate the source checkout without requiring a live ModelDesk connection.

## Configuration table

| Item | Value | Notes |
| --- | --- | --- |
| Runtime | Python 3.14 | Required for the Windows server checkout |
| Transport | stdio | Local MCP transport over stdin/stdout |
| Launcher | `ModelDeskMCP.cmd` | Source-checkout entry point in the repo root |
| Client entry | `.vscode/mcp.json` | Example local VS Code configuration |
| COM dependency | Local ModelDesk installation | Required for COM-backed operations |
| Testing mode | COM-free smoke + pytest | No live COM required for verification |

## Architecture summary

The public flow is intentionally narrow:

- FastMCP exposes the registry-defined tool surface.
- The registry maps each tool to a stable service contract.
- Service logic translates named requests into ModelDesk operations.
- The COM gateway formats and invokes the ModelDesk Automation interface.
- `ComStaDispatcher` serializes COM calls onto a single STA thread.
- ModelDesk performs the requested action, and child objects are reacquired by selector when a stale COM reference is reused.

This structure keeps COM access centralized and makes the server easier to validate in deterministic, COM-free tests.

## Development and test commands

```powershell
python -m compileall src server.py
python -m pytest -q
python -m modeldesk_mcp.smoke --skip-com-status
```

The source checkout is the authoritative install path for development. The repository does not include an authoring package manager lockfile, generated release artifacts, or a separate packaging workflow.

## Troubleshooting

- `py` is not recognized: install Python 3.14 and ensure the launcher can find `py` on PATH.
- Client cannot start the server: confirm the path in the MCP config points to the repository root and that `ModelDeskMCP.cmd` exists.
- COM calls fail: confirm ModelDesk is installed, registered, and accessible on the local machine.
- Smoke checks fail before COM is used: verify the editable install and run `python -m pytest -q` to isolate a deterministic failure.
- Client requests are rejected: verify that the tool name matches the public registry contract and that the client is not using a stale config file.

## Documentation index

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/clients.md](docs/clients.md)
- [docs/error-handling.md](docs/error-handling.md)
- [docs/extending.md](docs/extending.md)

## Support

This repository is a source-only server checkout for local ModelDesk automation. Support is limited to the public server contract and the documentation in this repo. ModelDesk licensing, local project content, and machine-level COM setup remain the responsibility of the local environment and the ModelDesk installation itself.
