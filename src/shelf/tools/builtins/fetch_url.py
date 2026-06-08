"""``fetch_url`` — fetch and parse a single URL to title + text (truncated).

Reuses the Phase 1 ingestion stack (``HttpFetcher`` + ``parse_document``), so it
honors the same scheme allow-list (http/https/file) and parsers. Fetching a remote
http(s) URL is egress, but it's an explicit, user-or-agent-chosen single URL (the
same posture as ``/clip``), not background crawling.
"""

from __future__ import annotations

from typing import Any

from shelf.ingestion.parsers import parse_document
from shelf.tools.base import Tool, ToolContext

_MAX_CHARS = 2400

_PARAMETERS = {
    "properties": {
        "url": {"type": "string", "description": "An http(s):// or file:// URL to read."},
    },
    "required": ["url"],
}


def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    if ctx.fetcher is None:
        return "error: no fetcher available"
    url = str(args.get("url") or "").strip()
    result = ctx.fetcher.fetch(url)
    doc = parse_document(result.raw, content_type=result.content_type, filename=result.url)
    text = (doc.text or "").strip()
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS].rstrip() + "\n...[truncated]"
    title = doc.title or "(untitled)"
    return f"Title: {title}\nURL: {result.url}\n\n{text or '(no extractable text)'}"


TOOL = Tool(
    name="fetch_url",
    description="Fetch a single web page or file and return its title and main text "
    "(truncated). Use to read a promising search result before proposing it.",
    toolset="discovery",
    parameters=_PARAMETERS,
    handler=_handler,
    check_fn=lambda ctx: ctx.fetcher is not None,
)
