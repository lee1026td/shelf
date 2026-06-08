"""The uniform Tool interface + execution context (Phase 3, ARCHITECTURE.md §3).

A ``Tool`` is a named capability the agent can invoke: a JSON-schema-ish parameter
spec, a handler, and an optional availability check. Tools are deliberately tiny and
pure-ish — they take parsed args + a :class:`ToolContext` and return an observation
*string* the model reads back. Keeping the contract string-in/string-out (rather than
provider-specific function-calling objects) is what lets a small local model drive the
loop through the text protocol in ``shelf.agent``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid import cycles / heavy imports at module load
    from shelf.config import Config
    from shelf.ingestion.base import Fetcher
    from shelf.llm import ModelGateway
    from shelf.store import Store
    from shelf.workspace import Workspace


@dataclass
class ToolContext:
    """Everything a tool handler may need, assembled once per agent run.

    All fields are optional so tools can be unit-tested with only what they use, and
    so a tool that needs an absent capability (e.g. a gateway) can fail cleanly.
    """

    workspace: Workspace | None = None
    store: Store | None = None
    gateway: ModelGateway | None = None
    fetcher: Fetcher | None = None
    config: Config | None = None
    # Scratch space shared across a single run (e.g. the active topic id / slug).
    scratch: dict[str, Any] = field(default_factory=dict)


# A handler takes coerced args + the run context and returns an observation string.
ToolHandler = Callable[[dict[str, Any], ToolContext], str]


@dataclass(frozen=True)
class Tool:
    """A single agent-invokable capability."""

    name: str
    description: str
    toolset: str
    handler: ToolHandler
    # JSON-schema-ish: {"properties": {name: {"type": ..., "description": ...}}, "required": [...]}
    parameters: dict[str, Any] = field(default_factory=dict)
    # Optional availability gate (e.g. requires a store). False -> hidden from the catalog.
    check_fn: Callable[[ToolContext], bool] | None = None

    @property
    def properties(self) -> dict[str, Any]:
        return dict(self.parameters.get("properties") or {})

    @property
    def required(self) -> list[str]:
        return list(self.parameters.get("required") or [])

    def available(self, ctx: ToolContext) -> bool:
        if self.check_fn is None:
            return True
        try:
            return bool(self.check_fn(ctx))
        except Exception:  # an availability probe must never crash catalog assembly
            return False
