"""``propose_source`` — stage a discovered source for review (propose-don't-mutate).

A discovered source is written as ``status='candidate'`` plus a pending
``review_item`` — it never enters the watchlist directly (ARCHITECTURE.md principle 3:
"discover freely, watch cautiously"). Re-proposing the same slug is a no-op, which
also stops small models from looping on the same URL.
"""

from __future__ import annotations

from typing import Any

from shelf.tools.base import Tool, ToolContext
from shelf.util import slugify

_PARAMETERS = {
    "properties": {
        "url": {"type": "string", "description": "The source URL (homepage, feed, or page)."},
        "name": {"type": "string", "description": "Human-readable source name."},
        "role": {"type": "string", "description": "e.g. blog, docs, news, paper, forum."},
        "reason": {"type": "string", "description": "Why this source is relevant to the topic."},
        "relevance": {
            "type": "number",
            "description": "How relevant to the topic, 0.0-1.0 (optional).",
        },
        "authority": {
            "type": "number",
            "description": "How authoritative/primary the source is, 0.0-1.0 (optional).",
        },
    },
    "required": ["url"],
}


def _clamp01(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    store = ctx.store
    if store is None:
        return "error: no library available"
    url = str(args.get("url") or "").strip()
    if not url:
        return "error: url is required"
    name = (str(args.get("name") or "").strip()) or None
    role = (str(args.get("role") or "").strip()) or None
    reason = (str(args.get("reason") or "").strip()) or None
    score = {
        axis: v
        for axis in ("relevance", "authority")
        if (v := _clamp01(args.get(axis))) is not None
    }
    slug = slugify(name or url, fallback="source")
    if store.get_source(slug) is not None:
        return f"Source '{slug}' was already proposed - do not propose it again."
    source_id = store.add_source(
        slug,
        url,
        name=name,
        role=role,
        status="candidate",
        topic_id=ctx.scratch.get("topic_id"),
        score=score or None,
        discovered_from={"topic": ctx.scratch.get("topic"), "reason": reason},
    )
    store.add_review_item(
        type="source",
        title=name or url,
        suggested_action="watch",
        ref_kind="source",
        ref_id=source_id,
        evidence={"url": url, "reason": reason},
    )
    store.commit()
    ctx.scratch.setdefault("proposed", []).append(slug)
    return f"Proposed '{slug}' ({url}) as a candidate, pending review. Do not propose it again."


TOOL = Tool(
    name="propose_source",
    description="Propose a discovered source for the user to review (saved as a candidate, "
    "never auto-watched). Call once per genuinely relevant source.",
    toolset="discovery",
    parameters=_PARAMETERS,
    handler=_handler,
    check_fn=lambda ctx: ctx.store is not None,
)
