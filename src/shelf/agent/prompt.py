"""Build the system + running prompts for the agent loop.

Small models need the action format spelled out with an example and the tool catalog
inlined (no native function-calling). The running prompt re-renders the goal + the
action/observation transcript each turn, since the gateway is single-turn
(``ModelGateway.complete(prompt, system=...)``) — a ReAct scratchpad in one prompt.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shelf.agent.trace import AgentStep
    from shelf.skills.base import Skill
    from shelf.tools.base import Tool

_IDENTITY = (
    "You are shelf's research agent. You accomplish a task by calling tools one at a "
    "time and reasoning over what they return. You are precise and never invent facts."
)

_FORMAT = """\
HOW TO RESPOND
Reply with exactly ONE fenced JSON block and nothing else around it:
```json
{"tool": "<tool_name>", "args": {<arguments>}}
```
You may add a short "thought" string. When the task is complete, finish with:
```json
{"tool": "final", "args": {"answer": "<your final answer>"}}
```
Call only ONE tool per reply. Use only the tools listed below."""

_EXAMPLE = """\
EXAMPLE
```json
{"thought": "check the library first", "tool": "library_search", "args": {"query": "rust"}}
```"""


def _format_tool(tool: Tool) -> str:
    lines = [f"- {tool.name}: {tool.description}"]
    for pname, spec in tool.properties.items():
        ptype = spec.get("type", "string") if isinstance(spec, dict) else "string"
        pdesc = spec.get("description", "") if isinstance(spec, dict) else ""
        req = " (required)" if pname in tool.required else ""
        lines.append(f"    - {pname} ({ptype}){req}: {pdesc}")
    return "\n".join(lines)


def build_system_prompt(catalog: list[Tool], skill: Skill | None = None) -> str:
    parts = [_IDENTITY, _FORMAT, _EXAMPLE]
    if skill and skill.body:
        parts.append("TASK GUIDANCE\n" + skill.body)
    catalog_text = "\n".join(_format_tool(t) for t in catalog) or "(no tools available)"
    parts.append("AVAILABLE TOOLS\n" + catalog_text)
    return "\n\n".join(parts)


def build_user_prompt(goal: str, steps: list[AgentStep], notes: list[str]) -> str:
    parts = [f"Task: {goal}"]
    if steps:
        parts.append("\nWork so far:")
        for i, step in enumerate(steps, 1):
            call = json.dumps({"tool": step.tool, "args": step.args}, ensure_ascii=False)
            parts.append(f"Action {i}: {call}")
            parts.append(f"Observation {i}: {step.observation}")
    for note in notes:
        parts.append(f"\n[note] {note}")
    parts.append("\nReply with your next action as a single JSON block.")
    return "\n".join(parts)
