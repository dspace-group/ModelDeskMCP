"""MCPServer stdio server for ModelDesk Automation."""

from __future__ import annotations

import argparse

from modeldesk_mcp import __version__


def create_app() -> "MCPServer":
    """Create a configured MCPServer instance."""

    from mcp.server.mcpserver import MCPServer

    from modeldesk_mcp.com_bridge import ComStaDispatcher, ModelDeskAutomationGateway
    from modeldesk_mcp.config import ComGatewayOptions
    from modeldesk_mcp.domain import ModelDeskService, WorkflowCatalog
    from modeldesk_mcp.tools import register_tools

    options = ComGatewayOptions.load_from_environment()
    dispatcher = ComStaDispatcher()
    gateway = ModelDeskAutomationGateway(dispatcher, options)
    service = ModelDeskService(gateway, WorkflowCatalog())
    mcp = MCPServer("ModelDesk Automation")
    register_tools(mcp, service)
    return mcp


def main(argv: list[str] | None = None) -> int | None:
    """Run the stdio server or a COM-free metadata command."""

    parser = argparse.ArgumentParser(description="ModelDesk MCP stdio server.")
    metadata_group = parser.add_mutually_exclusive_group()
    metadata_group.add_argument("--version", action="store_true", help="Print the server version and exit.")
    metadata_group.add_argument("--list-tools", action="store_true", help="Print registered tool names and exit.")
    metadata_group.add_argument(
        "--list-resources",
        action="store_true",
        help="Print the registered resource status and exit.",
    )
    metadata_group.add_argument(
        "--list-prompts",
        action="store_true",
        help="Print the registered prompt status and exit.",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(f"modeldesk-mcp {__version__}")
        return 0
    if args.list_tools:
        from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES

        print(*EXPECTED_TOOL_NAMES, sep="\n")
        return 0
    if args.list_resources:
        print("No MCP resources are registered.")
        return 0
    if args.list_prompts:
        print("No MCP prompts are registered.")
        return 0

    create_app().run()


if __name__ == "__main__":
    main()
