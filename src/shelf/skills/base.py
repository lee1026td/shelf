"""Skill value object (Phase 3).

A *skill* is task-specific guidance (a SKILL.md body) plus the toolset it expects —
loaded into the agent's system prompt only when that task is selected. It differs from
a tool: a tool *does* something; a skill *tells the model how* to use tools for a task.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    toolset: str | None = None
    body: str = ""
