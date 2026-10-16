# MCP Clients

[../README.md](../README.md) | [tools.md](tools.md) | [error-handling.md](error-handling.md)

An MCP client starts the server as a local stdio child process on the Windows machine that hosts ModelDesk. There is no HTTP endpoint, browser interface, or remote ModelDesk session service.

## Prepare the Checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the checkout root:

```powershell
uv sync
.\ModelDeskMCP.cmd --version
uv run python -m modeldesk_mcp.smoke --skip-com-status
```

uv manages Python and the checkout-local `.venv`. You do not need to create or activate an environment manually. Dependency installation and the COM-free smoke check do not require a ModelDesk project.

For automation calls, install and register ModelDesk locally and make the intended project and assets available. Start with status/capability inspection rather than immediately opening or modifying content.

## VS Code

Add the server entry to [.vscode/mcp.json](../.vscode/mcp.json), preserving any other configured servers:

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

Use the MCP controls in VS Code to start or restart the server and inspect its log. `${workspaceFolder}` assumes this checkout is the workspace folder; use an absolute path when configuring the server from a different workspace.

After editing server source, restart the MCP server and refresh its tools. Reusing an old process can leave old tool descriptions or behavior loaded.

## Other Stdio Clients

Use the client's own server configuration schema. Many desktop clients use `mcpServers` rather than VS Code's `servers`. On Windows, a batch launcher can be invoked through `cmd.exe`:

```json
{
  "mcpServers": {
    "modeldesk-mcp": {
      "command": "cmd.exe",
      "args": [
        "/d",
        "/c",
        "C:\\tools\\ModelDeskMCP\\ModelDeskMCP.cmd"
      ]
    }
  }
}
```

Replace the example path with your checkout. The launcher locates the project relative to its own location, so it does not depend on the client's current directory. Where supported, setting the working directory to the checkout makes startup behavior easier to inspect.

Run the stdio server on native Windows with access to local COM. A client running remotely, inside a container, or in WSL does not by itself provide access to the Windows ModelDesk session.

## Launcher and Metadata

The [../ModelDeskMCP.cmd](../ModelDeskMCP.cmd) launcher forwards arguments and exit codes, and starts `python -m modeldesk_mcp.server` through uv from the checkout directory:

| Available command | Launcher behavior |
| --- | --- |
| `uv` on PATH | Use `uv --directory ... run python -m modeldesk_mcp.server`. |
| No `uv` on PATH, but Python 3.14 and its uv module exist | Use `py -3.14 -m uv --directory ... run python -m modeldesk_mcp.server`. |
| Neither available | Startup fails; install uv or repair the client's inherited PATH. |

The module fallback uses an existing Python 3.14 installation; it cannot install a missing Python launcher or uv module. Check it with `py -3.14 -m uv --version`. After installing uv or changing PATH, restart the MCP client so its child processes inherit the updated environment.

With no arguments, the process serves MCP on stdin/stdout. Do not add a metadata flag to the persistent client configuration: it prints a result and exits.

```powershell
.\ModelDeskMCP.cmd --help
.\ModelDeskMCP.cmd --version
.\ModelDeskMCP.cmd --list-tools
.\ModelDeskMCP.cmd --list-resources
.\ModelDeskMCP.cmd --list-prompts
```

`--list-tools` prints the 83 registered names. `--list-resources` prints `modeldesk://workflow-catalog`, the static resource containing workflow names and use-case identifiers. No prompts are registered. Metadata commands do not initialize the ModelDesk runtime. Keep stdout reserved for MCP protocol traffic during a normal stdio session; inspect startup diagnostics in the client log/stderr.

## Server Configuration

Set these environment variables in the MCP client's server environment when a non-default value is needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODELDESK_MCP_PROG_ID` | `ModelDesk.Application` | COM ProgID used to connect to ModelDesk. |
| `MODELDESK_MCP_OPERATION_TIMEOUT_SECONDS` | `60` | Maximum time the caller waits for a dispatched COM operation. |
| `MODELDESK_MCP_MAX_COLLECTION_ITEMS` | `500` | Maximum number of items included in collection snapshots. |

Blank ProgIDs and invalid or non-positive numeric values fall back to the defaults. A client can impose an additional timeout of its own. Increasing the server timeout does not change the client's timeout or cancel running COM work; see [error-handling.md](error-handling.md).

Collection snapshots can be truncated. Inspect their message and count rather than treating the returned items as an exhaustive catalog.

## Package Sources and CI

uv records registry and artifact URLs in the lockfile. A file resolved against an organization-local mirror can therefore reference hosts that are unavailable on another machine. A DNS/download error for such a host is a package-source problem, not a ModelDesk COM error.

Use a package index approved and reachable in the target environment. If an explicit override is appropriate, set `UV_DEFAULT_INDEX` in that environment before invoking uv. An index change can re-resolve and update the local lockfile; review that diff rather than silently discarding it. Do not commit credentials, disable certificate validation, or change organization-wide package policy to work around a checkout-specific issue.

The [../.github/workflows/python-tests.yml](../.github/workflows/python-tests.yml) test job sets `UV_DEFAULT_INDEX=https://pypi.org/simple` for all its uv calls, including launcher checks. This lets hosted GitHub runners resolve public package sources without changing a developer's local configuration.

## Safe First Calls

1. Read `modeldesk_get_status` and `modeldesk_get_capabilities`.
2. Inspect the active project/experiment and the relevant domain summary.
3. List objects before choosing selectors; do not assume index 0 is the intended target.
4. Read [tools.md](tools.md) and [use-cases.md](use-cases.md) before edits or execution.
5. Obtain intent for persistence, downloads, processing, test execution, and runtime controls separately from read-only inspection.

Context switches and closing a project may save by default. Editing with `save=false` and `download=false` still changes in-memory state. The MCP client and its tools inherit local process access; this server is not a security boundary for untrusted callers.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv` is not recognized | Verify PATH or the Python-module fallback; restart the client after installation. |
| Server exits immediately | Remove metadata flags from the persistent configuration; inspect the reported exit code and startup log. |
| Tool list is stale | Restart the server and refresh client discovery. |
| Package host cannot be resolved | Check configured and locked registry/artifact hosts against the target network. |
| COM is unavailable | Check native Windows execution, local installation/registration, and user-session accessibility. |
| Domain is unavailable | Inspect capabilities and active experiment; not every project provides every domain. |
| Call times out or mutation fails | Reinspect state before any retry; see [error-handling.md](error-handling.md). |
