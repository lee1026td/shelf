"""Parse a small/local model's reply into a tool action or a final answer.

The text protocol: the model replies with a single fenced ```json {"tool": ...,
"args": {...}}``` block (or ``{"tool": "final", "args": {"answer": ...}}`` to stop).
Weak models mangle this constantly, so parsing is deliberately forgiving — it locates
the JSON, repairs the common breakages (trailing commas, unbalanced braces, raw control
characters inside strings), and tolerates args placed at the top level. This mirrors the
multi-pass repair in Hermes-Agent's ``message_sanitization._repair_tool_call_arguments``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    thought: str | None = None


@dataclass
class Final:
    answer: str
    thought: str | None = None


@dataclass
class ParseError:
    message: str


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _last_balanced_object(text: str) -> str | None:
    """Return the last top-level ``{...}`` block, string-aware (ignores braces in strings)."""
    objects: list[str] = []
    depth = 0
    start: int | None = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : i + 1])
                start = None
    return objects[-1] if objects else None


def _escape_control_in_strings(s: str) -> str:
    """Escape raw control chars that appear *inside* JSON string literals."""
    out: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch)
                esc = False
                continue
            if ch == "\\":
                out.append(ch)
                esc = True
                continue
            if ch == '"':
                in_str = False
                out.append(ch)
                continue
            if ch in "\n\r\t":
                out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
                continue
            if ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return "".join(out)


def _balance(s: str) -> str:
    """Append missing closing braces/brackets (string-aware brace counting)."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    closers = {"{": "}", "[": "]"}
    return s + "".join(closers[c] for c in reversed(stack))


def _loads_tolerant(block: str) -> Any | None:
    block = block.strip()
    candidates = [
        block,
        _TRAILING_COMMA_RE.sub(r"\1", block),
        _balance(_TRAILING_COMMA_RE.sub(r"\1", block)),
        _escape_control_in_strings(_balance(_TRAILING_COMMA_RE.sub(r"\1", block))),
    ]
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _extract_json(text: str) -> str | None:
    fenced = [m.strip() for m in _FENCE_RE.findall(text) if "{" in m]
    if fenced:
        return fenced[-1]  # models put the action last
    balanced = _last_balanced_object(text)
    if balanced is not None:
        return balanced
    # Fallback: an unclosed outer brace (common truncation). Take from the first '{'
    # to the end and let the tolerant loader balance it.
    idx = text.find("{")
    return text[idx:] if idx != -1 else None


def parse_action(text: str) -> Action | Final | ParseError:
    """Turn a model reply into an :class:`Action`, :class:`Final`, or :class:`ParseError`."""
    block = _extract_json(text or "")
    if block is None:
        return ParseError("no JSON action found")
    obj = _loads_tolerant(block)
    if not isinstance(obj, dict):
        return ParseError("could not parse a JSON object")
    tool = str(obj.get("tool") or obj.get("action") or "").strip()
    if not tool:
        return ParseError("JSON action has no 'tool' field")
    thought = obj.get("thought")
    thought = str(thought) if thought else None
    args = obj.get("args")
    if not isinstance(args, dict):
        # Some models inline args at the top level: {"tool": "x", "query": "y"}.
        args = {k: v for k, v in obj.items() if k not in ("tool", "action", "args", "thought")}
    if tool.lower() == "final":
        answer = args.get("answer") if isinstance(args, dict) else None
        if not answer:
            answer = obj.get("answer") or ""
        return Final(answer=str(answer), thought=thought)
    return Action(tool=tool, args=args, thought=thought)
