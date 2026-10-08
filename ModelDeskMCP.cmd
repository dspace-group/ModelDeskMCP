@rem MCP clients launch this source-checkout stdio server through uv from any working directory.
@rem Keep stdout owned by JSON-RPC and let uv/server failures propagate as a nonzero exit.
@where uv >nul 2>&1
@if errorlevel 1 (
	@py -3.14 -m uv --directory "%~dp0." run python -m modeldesk_mcp.server %*
) else (
	@uv --directory "%~dp0." run python -m modeldesk_mcp.server %*
)
@exit /b %errorlevel%
