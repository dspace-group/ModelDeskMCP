# MCP clients

The server is designed for local MCP clients that start a stdio process on the current machine.

## Example VS Code config

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

## Launcher behavior

The root launcher uses a checkout-relative path and forwards all arguments unchanged:

```bat
@uv --directory "%~dp0." run python -m modeldesk_mcp.server %*
```

When no arguments are supplied, the server starts in stdio mode. Metadata flags are part of the backend contract and are not used as a public launcher feature in this repo.

## Safe client workflow

1. Run `uv sync` in the checkout.
2. Verify that `uv` and the launcher are available.
3. Run COM-free smoke checks before calling ModelDesk-backed tools.
4. Start with read-only discovery and status tools.
5. Back up project content before any tool that edits, saves, runs, or closes ModelDesk data.

## Operational note

ModelDesk, project assets, and a valid local COM registration remain external requirements of the environment. This repo does not bundle those assets or provide remote execution.
