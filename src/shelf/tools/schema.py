"""Argument coercion + validation for tool calls.

Small / open-weight local models routinely emit numbers as strings (``"5"``),
booleans as strings (``"true"``), or a bare scalar where the schema wants an array
(``"x"`` instead of ``["x"]``). Rather than reject these and burn a retry, we coerce
toward the declared types — the same pragmatic repair Hermes-Agent applies in
``model_tools.coerce_tool_args``. Coercion is best-effort: anything it can't safely
convert is passed through untouched for the handler (or ``validate_required``) to judge.
"""

from __future__ import annotations

from typing import Any

_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0", ""}


def _coerce_scalar(value: Any, json_type: str) -> Any:
    if json_type in ("integer", "number") and isinstance(value, str):
        text = value.strip()
        try:
            return int(text) if json_type == "integer" else float(text)
        except ValueError:
            return value
    if json_type == "boolean" and isinstance(value, str):
        low = value.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
    if json_type == "string" and isinstance(value, int | float | bool):
        return str(value)
    return value


def coerce_args(parameters: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Coerce ``args`` toward the types declared in a tool's ``parameters`` schema.

    Handles str->int/float/bool, scalar->bool, and wrapping a bare scalar in a
    single-element list when the schema declares ``"type": "array"``. Unknown keys
    pass through unchanged (handlers tolerate extras).
    """
    props: dict[str, Any] = parameters.get("properties") or {}
    out: dict[str, Any] = {}
    for key, value in (args or {}).items():
        spec = props.get(key)
        if not isinstance(spec, dict):
            out[key] = value
            continue
        json_type = spec.get("type")
        if json_type == "array" and not isinstance(value, list):
            # Open-weight models emit {"urls": "x"} when the tool wants {"urls": ["x"]}.
            item_type = (spec.get("items") or {}).get("type")
            out[key] = [_coerce_scalar(value, item_type) if item_type else value]
        elif isinstance(json_type, str):
            out[key] = _coerce_scalar(value, json_type)
        else:
            out[key] = value
    return out


def validate_required(parameters: dict[str, Any], args: dict[str, Any]) -> list[str]:
    """Return the names of required parameters missing/empty in ``args`` (empty if ok)."""
    required: list[str] = parameters.get("required") or []
    missing = []
    for name in required:
        value = args.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    return missing
