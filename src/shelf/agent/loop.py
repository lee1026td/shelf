"""The agent loop: drive a (small, local) model through tool calls to a final answer.

Single-turn gateway + a re-rendered ReAct scratchpad (see ``prompt.py``). The loop is
defensive by design — parse failures and unknown-tool hallucinations become corrective
notes fed back to the model (bounded), tool exceptions become observations, and every
observation is truncated — so a weak model degrades to fewer/poorer steps rather than
crashing the run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from shelf.agent.prompt import build_system_prompt, build_user_prompt
from shelf.agent.protocol import Action, Final, ParseError, parse_action
from shelf.agent.trace import AgentResult, AgentStep
from shelf.errors import ShelfError

if TYPE_CHECKING:
    from shelf.llm import ModelGateway
    from shelf.skills.base import Skill
    from shelf.tools.base import ToolContext
    from shelf.tools.registry import ToolRegistry

_MAX_PARSE_FAILURES = 3

# An observer of the loop's progress: on_event(kind, message). kind is one of
# "step" | "retry" | "note" | "final" | "error". Used to stream a live trace.
EventHook = Callable[[str, str], None]


def _compact_args(args: dict) -> str:
    text = json.dumps(args, ensure_ascii=False)
    return text if len(text) <= 80 else text[:79] + "..."


def _first_line(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "(empty)"
    line = stripped.splitlines()[0]
    return line if len(line) <= 120 else line[:119] + "..."


class AgentLoop:
    """Runs a tool-using task to completion against a model gateway."""

    def __init__(self, gateway: ModelGateway, registry: ToolRegistry, ctx: ToolContext) -> None:
        self.gateway = gateway
        self.registry = registry
        self.ctx = ctx

    def run(
        self,
        goal: str,
        *,
        toolset: str | None = None,
        skill: Skill | None = None,
        max_steps: int = 8,
        max_obs_chars: int = 1500,
        on_event: EventHook | None = None,
    ) -> AgentResult:
        catalog = self.registry.catalog(self.ctx, toolset=toolset)
        valid_names = {t.name for t in catalog} | {"final"}
        system = build_system_prompt(catalog, skill)

        def emit(kind: str, message: str) -> None:
            if on_event is not None:
                on_event(kind, message)

        steps: list[AgentStep] = []
        notes: list[str] = []
        parse_failures = 0

        for _ in range(max_steps):
            reply = self._complete(build_user_prompt(goal, steps, notes), system)
            notes = []
            if reply is None:
                emit("error", "model call failed")
                return AgentResult("(agent error: model call failed)", steps, "error")

            parsed = parse_action(reply)
            if isinstance(parsed, ParseError):
                parse_failures += 1
                emit(
                    "retry",
                    f"unparseable reply {parse_failures}/{_MAX_PARSE_FAILURES}; re-prompting",
                )
                if parse_failures > _MAX_PARSE_FAILURES:
                    return AgentResult(reply.strip() or "(no answer)", steps, "error")
                notes.append(
                    "Your last reply was not a valid action. Reply with exactly one "
                    '```json {"tool": "...", "args": {...}} ``` block.'
                )
                continue
            if isinstance(parsed, Final):
                emit("final", f"finished after {len(steps)} step(s)")
                return AgentResult(parsed.answer.strip() or "(no answer)", steps, "final")

            assert isinstance(parsed, Action)
            if parsed.tool not in valid_names:
                emit("retry", f"unknown tool '{parsed.tool}'; re-prompting")
                notes.append(
                    f"Unknown tool '{parsed.tool}'. Valid tools: {', '.join(sorted(valid_names))}."
                )
                continue

            observation = self.registry.dispatch(parsed.tool, parsed.args, self.ctx)
            if len(observation) > max_obs_chars:
                observation = observation[:max_obs_chars].rstrip() + "\n...[truncated]"
            steps.append(AgentStep(parsed.tool, parsed.args, observation, thought=parsed.thought))
            emit(
                "step",
                f"step {len(steps)}: {parsed.tool}({_compact_args(parsed.args)}) "
                f"-> {_first_line(observation)}",
            )

        return self._force_final(goal, system, steps, emit)

    # --- helpers ------------------------------------------------------------
    def _complete(self, prompt: str, system: str) -> str | None:
        try:
            return self.gateway.complete(prompt, role="planner", system=system, temperature=0.1)
        except ShelfError:
            return None

    def _force_final(
        self, goal: str, system: str, steps: list[AgentStep], emit: Callable[[str, str], None]
    ) -> AgentResult:
        """Step budget hit: ask once for a final answer, else summarize best-effort."""
        emit("note", f"step budget reached after {len(steps)} step(s); asking for a final answer")
        note = [
            "You have used all your tool steps. Reply now with the final action: "
            '{"tool": "final", "args": {"answer": "..."}}.'
        ]
        reply = self._complete(build_user_prompt(goal, steps, note), system)
        if reply is not None:
            parsed = parse_action(reply)
            if isinstance(parsed, Final) and parsed.answer.strip():
                return AgentResult(parsed.answer.strip(), steps, "max_steps")
            if isinstance(parsed, ParseError) and reply.strip():
                return AgentResult(reply.strip(), steps, "max_steps")
        return AgentResult("(reached the step limit without a final answer)", steps, "max_steps")
