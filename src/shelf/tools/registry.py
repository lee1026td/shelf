"""The tool registry + composable toolsets (Phase 3).

Single source of truth for which tools exist and how they group into named
*toolsets* (an agent run is given one toolset, not the whole catalog — progressive
disclosure keeps the prompt small for local models). Adapted from Hermes-Agent's
``tools/registry.py`` + ``toolsets.py``, minus the probability distributions, MCP
bridge, and async machinery shelf doesn't need yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shelf.tools.base import Tool, ToolContext
from shelf.tools.schema import coerce_args, validate_required


@dataclass
class _Toolset:
    description: str = ""
    tools: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)


class ToolRegistry:
    """Holds tools and toolsets; resolves, filters, and dispatches calls."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._toolsets: dict[str, _Toolset] = {}

    # --- registration -------------------------------------------------------
    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_toolset(
        self,
        name: str,
        tools: list[str],
        *,
        includes: list[str] | None = None,
        description: str = "",
    ) -> None:
        self._toolsets[name] = _Toolset(description, list(tools), list(includes or []))

    # --- lookup -------------------------------------------------------------
    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def resolve_toolset(self, name: str, _visited: set[str] | None = None) -> list[str]:
        """Recursively expand a toolset to a sorted, deduped list of tool names.

        Unknown toolset names and cycles resolve to whatever is reachable (no raise),
        so a typo degrades to a smaller toolset rather than crashing a run.
        """
        visited = _visited if _visited is not None else set()
        if name in visited:
            return []
        visited.add(name)
        spec = self._toolsets.get(name)
        if spec is None:
            return []
        found: set[str] = {t for t in spec.tools if t in self._tools}
        for included in spec.includes:
            found.update(self.resolve_toolset(included, visited))
        return sorted(found)

    def catalog(
        self,
        ctx: ToolContext,
        *,
        toolset: str | None = None,
        names: list[str] | None = None,
    ) -> list[Tool]:
        """Tools to expose this run: from a toolset (or explicit names, or all),
        filtered by each tool's availability check against ``ctx``."""
        if names is not None:
            wanted = list(names)
        elif toolset is not None:
            wanted = self.resolve_toolset(toolset)
        else:
            wanted = self.names()
        tools = [self._tools[n] for n in wanted if n in self._tools]
        return [t for t in tools if t.available(ctx)]

    # --- execution ----------------------------------------------------------
    def dispatch(self, name: str, args: dict, ctx: ToolContext) -> str:
        """Run a *known* tool, returning an observation string. Never raises.

        Missing required args and handler exceptions both become an error string the
        agent loop feeds back to the model, so one bad call can't abort the run.
        Callers detect *unknown* tools via :meth:`get` before dispatching.
        """
        tool = self._tools.get(name)
        if tool is None:  # defensive; the loop should have caught this
            return f"error: unknown tool '{name}'"
        coerced = coerce_args(tool.parameters, args or {})
        missing = validate_required(tool.parameters, coerced)
        if missing:
            return f"error: missing required argument(s): {', '.join(missing)}"
        try:
            return tool.handler(coerced, ctx)
        except Exception as exc:  # tools must not crash the loop
            return f"error: {tool.name} failed: {exc}"
