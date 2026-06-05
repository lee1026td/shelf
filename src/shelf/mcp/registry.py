"""MCP registry. STUB (Phase 7, plan §11.2, §11.3).

Registers local/remote MCP servers with per-tool trust levels. Remote tools are
read-only by default and require a data-to-send preview before private content is
sent (plan permission model).
"""

from __future__ import annotations

from dataclasses import dataclass

from shelf.errors import FeatureNotReady


@dataclass
class McpServer:
    """A registered MCP server and its trust posture."""

    name: str
    transport: str  # "stdio" | "http"
    endpoint: str
    trust: str = "read_only"  # read_only | trusted
    scope: str = "local"  # local | remote


class McpRegistry:
    """Stub MCP registry."""

    PHASE = 7

    def register(self, server: McpServer) -> None:
        raise FeatureNotReady("MCP server registration", self.PHASE)

    def list_servers(self) -> list[McpServer]:
        raise FeatureNotReady("MCP registry listing", self.PHASE)

    def inspect(self, name: str) -> dict[str, object]:
        raise FeatureNotReady("MCP server inspection", self.PHASE)
