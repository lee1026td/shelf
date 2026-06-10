"""Tool runtime: a uniform ``Tool`` interface, a registry, and composable toolsets.

``build_default_registry()`` wires the built-in tools and the named toolsets the agent
uses. Built tools are registered explicitly (not AST-discovered) — the set is small and
explicit registration keeps imports obvious and testable.
"""

from __future__ import annotations

from shelf.tools.base import Tool, ToolContext, ToolHandler
from shelf.tools.registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolContext",
    "ToolHandler",
    "ToolRegistry",
    "build_default_registry",
]


def build_default_registry() -> ToolRegistry:
    """A registry with the built-in tools + the ``discovery`` toolset registered."""
    from shelf.tools.builtins import fetch_url, library_search, propose_source, web_search

    registry = ToolRegistry()
    for module in (library_search, fetch_url, web_search, propose_source):
        registry.register(module.TOOL)
    registry.register_toolset(
        "discovery",
        ["library_search", "web_search", "fetch_url", "propose_source"],
        description="Discover and propose sources for a research topic.",
    )
    registry.register_toolset(
        "compile",
        ["library_search", "fetch_url"],
        description="Read library + sources to synthesize a cited document (no proposing).",
    )
    registry.register_toolset(
        "answer",
        ["library_search", "fetch_url", "web_search"],
        description="Answer a question from the library (and the web when enabled); "
        "read-only, no proposing.",
    )
    return registry
