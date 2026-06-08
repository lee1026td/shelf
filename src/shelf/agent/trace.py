"""Records of an agent run: each tool step and the final result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    tool: str
    args: dict[str, Any]
    observation: str
    thought: str | None = None


@dataclass
class AgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    # "final" (model finished), "max_steps" (budget hit), or "error" (couldn't proceed).
    stopped_reason: str = "final"
