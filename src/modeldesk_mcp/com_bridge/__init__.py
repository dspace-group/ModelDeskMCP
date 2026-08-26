"""COM bridge boundary for ModelDesk Automation access."""

from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher
from modeldesk_mcp.com_bridge.gateway import ModelDeskAutomationGateway

__all__ = ["ComStaDispatcher", "ModelDeskAutomationGateway"]