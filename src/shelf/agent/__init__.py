"""The agent harness: a small-model-robust ReAct loop over the tool registry.

This is the "Agent Orchestrator" of ARCHITECTURE.md §2 — it selects a toolset + skill,
prompts the model with a text tool-call protocol, parses/repairs the reply, dispatches
tools, and loops to a final answer.
"""

from __future__ import annotations

from shelf.agent.loop import AgentLoop
from shelf.agent.protocol import Action, Final, ParseError, parse_action
from shelf.agent.trace import AgentResult, AgentStep

__all__ = [
    "AgentLoop",
    "AgentResult",
    "AgentStep",
    "Action",
    "Final",
    "ParseError",
    "parse_action",
]
