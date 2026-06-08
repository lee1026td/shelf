"""LLM-backed library tasks: summarize an Item, ask the library.

These compose the gateway with the store/filesystem. They are the first real users
of Phase 2; richer, citation-backed retrieval arrives with discovery (Phase 3).
"""

from __future__ import annotations

from typing import Any

from shelf.errors import LLMError
from shelf.llm.gateway import ModelGateway
from shelf.store import Store
from shelf.workspace import Workspace

SUMMARY_SYSTEM = "You are a precise research assistant. Summarize faithfully; never invent."
ASK_SYSTEM = (
    "You are shelf, a friendly local research-library assistant. Respond naturally to "
    "greetings, small talk, and general questions. Some of the user's saved library "
    "items may be shown to you as context - use them only when they are relevant to what "
    "the user asked, and when you do, cite the item titles you drew from. If the user "
    "asks a research question the items do not cover (or none are shown), answer from "
    "general knowledge and make clear it is not from their library. Never refuse a casual "
    "message on the grounds that the library does not contain it."
)


def _item_body(workspace: Workspace, item: dict[str, Any]) -> str:
    """The Item's text: its Markdown body (frontmatter stripped), else summary/title."""
    local = item.get("local_path")
    if local:
        path = workspace.root / str(local)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) == 3:
                    text = parts[2]
            return text.strip()
    return (item.get("summary") or item.get("title") or "").strip()


def summarize_item(
    workspace: Workspace,
    store: Store,
    gateway: ModelGateway,
    item_id: int,
    *,
    max_chars: int = 8000,
) -> str:
    """Generate an LLM summary for an Item and persist it. Returns the summary."""
    item = store.get_item(item_id)
    if item is None:
        raise LLMError(f"No item with id {item_id}.")
    body = _item_body(workspace, item)
    if not body:
        raise LLMError(f"Item {item_id} has no text to summarize.")
    prompt = "Summarize this document in 2-4 sentences:\n\n" + body[:max_chars]
    summary = gateway.complete(prompt, role="planner", system=SUMMARY_SYSTEM).strip()
    store.update_item_summary(item_id, summary)
    return summary


def ask_library(
    workspace: Workspace,
    store: Store,
    gateway: ModelGateway,
    question: str,
    *,
    k: int = 6,
) -> str:
    """Chat with the model, surfacing recent library items as optional context.

    Conversational messages (a greeting, small talk) are answered naturally; only
    when the library holds items relevant to the question does the model ground and
    cite them. An empty library means a plain chat prompt - no RAG framing - so a
    "Hello" never gets a "the library does not contain that" refusal.
    """
    items = store.list_items(limit=k)
    if items:
        context = "\n".join(
            f"- {it.get('title') or '(untitled)'}: {(it.get('summary') or '').strip()}"
            for it in items
        )
        prompt = (
            "Library items that may be relevant (ignore any that don't pertain to the "
            f"message):\n{context}\n\nUser: {question}"
        )
    else:
        prompt = f"User: {question}"
    return gateway.complete(prompt, role="planner", system=ASK_SYSTEM).strip()
