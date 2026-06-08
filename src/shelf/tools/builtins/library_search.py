"""``library_search`` — search the local library (items + sources). Offline."""

from __future__ import annotations

from typing import Any

from shelf.tools.base import Tool, ToolContext

_PARAMETERS = {
    "properties": {
        "query": {"type": "string", "description": "Keywords to search item titles/summaries."},
    },
    "required": ["query"],
}


def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    store = ctx.store
    if store is None:
        return "error: no library available"
    query = str(args.get("query") or "").strip()
    items = store.search_items(query, limit=8) if query else store.list_items(limit=8)
    lines: list[str] = []
    if items:
        lines.append(f"Library items matching {query!r}:")
        for it in items:
            title = it.get("title") or it.get("url") or "(untitled)"
            lines.append(f"- [item {it.get('id')}] {title} ({it.get('url') or 'local'})")
    else:
        lines.append(f"No library items match {query!r}.")
    sources = store.list_sources()
    if sources:
        lines.append("Known sources:")
        for s in sources[:10]:
            lines.append(f"- {s.get('slug')} [{s.get('status')}] {s.get('url')}")
    return "\n".join(lines)


TOOL = Tool(
    name="library_search",
    description="Search the user's existing local library (collected items and known sources) "
    "by keyword. Use this first; it needs no network.",
    toolset="discovery",
    parameters=_PARAMETERS,
    handler=_handler,
    check_fn=lambda ctx: ctx.store is not None,
)
