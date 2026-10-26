"""
Model Context Protocol (MCP) Server for DocuChat.

Integrates DocuChat Document AI into Claude Desktop, Claude Code, Cursor,
and GPT chats via stdio and SSE transports.
"""

from .server import mcp_server

__all__ = ["mcp_server"]

