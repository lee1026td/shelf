"""Phase 3 agent harness: tolerant protocol parsing + the ReAct loop."""

from __future__ import annotations

from shelf.agent import Action, AgentLoop, Final, ParseError, parse_action
from shelf.config import default_config
from shelf.llm import ModelGateway
from shelf.tools import ToolContext
from shelf.tools.base import Tool
from shelf.tools.registry import ToolRegistry
from tests.fixtures import ScriptedChatClient


def _gateway(replies):
    cfg = default_config("/tmp/x", "x")
    cfg.models["planner"].model = "m"
    return ModelGateway(cfg, client=ScriptedChatClient(replies))


# --- protocol --------------------------------------------------------------
def test_parse_bare_json_action():
    p = parse_action('{"tool": "library_search", "args": {"query": "x"}}')
    assert isinstance(p, Action) and p.tool == "library_search" and p.args == {"query": "x"}


def test_parse_fenced_action_takes_last_block():
    text = '```json\n{"tool":"a","args":{}}\n```\nthen\n```json\n{"tool":"b","args":{"k":1}}\n```'
    p = parse_action(text)
    assert isinstance(p, Action) and p.tool == "b" and p.args == {"k": 1}


def test_parse_final():
    p = parse_action('```json\n{"tool":"final","args":{"answer":"done"}}\n```')
    assert isinstance(p, Final) and p.answer == "done"


def test_parse_repairs_trailing_comma_and_unclosed_brace():
    # trailing comma + missing closing brace - both common from local models
    p = parse_action('{"tool": "x", "args": {"q": "hi",}')
    assert isinstance(p, Action) and p.tool == "x" and p.args == {"q": "hi"}


def test_parse_inline_args_at_top_level():
    p = parse_action('{"tool": "search", "query": "rust"}')
    assert isinstance(p, Action) and p.args == {"query": "rust"}


def test_parse_error_when_no_json():
    assert isinstance(parse_action("I think I should search the web."), ParseError)


# --- loop ------------------------------------------------------------------
def _recording_registry():
    calls: list[dict] = []
    reg = ToolRegistry()
    reg.register(
        Tool(
            "echo",
            "echo a string",
            "t",
            parameters={"properties": {"x": {"type": "string"}}, "required": ["x"]},
            handler=lambda args, ctx: calls.append(args) or f"echoed {args.get('x')}",
        )
    )
    reg.register_toolset("t", ["echo"])
    return reg, calls


def test_loop_calls_tool_then_finishes():
    reg, calls = _recording_registry()
    replies = [
        '```json\n{"tool":"echo","args":{"x":"hi"}}\n```',
        '```json\n{"tool":"final","args":{"answer":"all done"}}\n```',
    ]
    result = AgentLoop(_gateway(replies), reg, ToolContext()).run("goal", toolset="t", max_steps=5)
    assert calls == [{"x": "hi"}]
    assert result.answer == "all done"
    assert result.stopped_reason == "final"
    assert len(result.steps) == 1 and result.steps[0].tool == "echo"


def test_loop_reprompts_on_unknown_tool():
    reg, _ = _recording_registry()
    replies = [
        '{"tool":"nonexistent","args":{}}',  # hallucinated -> corrective note, no step
        '{"tool":"final","args":{"answer":"ok"}}',
    ]
    result = AgentLoop(_gateway(replies), reg, ToolContext()).run("goal", toolset="t", max_steps=5)
    assert result.answer == "ok"
    assert result.steps == []  # the bad call never became a step


def test_loop_emits_live_events():
    reg, _ = _recording_registry()
    events: list[tuple[str, str]] = []
    replies = [
        '{"tool":"echo","args":{"x":"hi"}}',
        '{"tool":"final","args":{"answer":"done"}}',
    ]
    AgentLoop(_gateway(replies), reg, ToolContext()).run(
        "goal", toolset="t", max_steps=5, on_event=lambda k, m: events.append((k, m))
    )
    kinds = [k for k, _ in events]
    assert "step" in kinds and "final" in kinds
    assert any("echo" in m for k, m in events if k == "step")  # step names the tool


def test_loop_emits_retry_event_on_unknown_tool():
    reg, _ = _recording_registry()
    events: list[tuple[str, str]] = []
    replies = ['{"tool":"nope","args":{}}', '{"tool":"final","args":{"answer":"ok"}}']
    AgentLoop(_gateway(replies), reg, ToolContext()).run(
        "g", toolset="t", on_event=lambda k, m: events.append((k, m))
    )
    assert any(k == "retry" for k, _ in events)


def test_loop_accepts_prose_reply_as_final():
    # A small model that answers in plain prose (no final-action JSON) shouldn't have
    # its answer discarded as an error after the retries.
    reg, _ = _recording_registry()
    result = AgentLoop(
        _gateway(["Here is the answer in plain prose, with no JSON action at all."]),
        reg,
        ToolContext(),
    ).run("g", toolset="t", max_steps=5)
    assert result.stopped_reason == "final"
    assert "plain prose" in result.answer
    assert result.steps == []


def test_loop_force_finals_at_step_budget():
    reg, _ = _recording_registry()
    replies = [
        '{"tool":"echo","args":{"x":"1"}}',
        '{"tool":"echo","args":{"x":"2"}}',
        '{"tool":"final","args":{"answer":"summary"}}',  # served to the forced-final call
    ]
    result = AgentLoop(_gateway(replies), reg, ToolContext()).run("goal", toolset="t", max_steps=2)
    assert result.stopped_reason == "max_steps"
    assert result.answer == "summary"
    assert len(result.steps) == 2
