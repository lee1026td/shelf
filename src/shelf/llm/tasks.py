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
    "You are a research librarian. Answer ONLY from the provided library items. "
    "If they do not contain the answer, say so plainly. Reference the item titles you used."
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
    """Answer a question grounded in the most recent library items."""
    items = store.list_items(limit=k)
    if items:
        context = "\n".join(
            f"- {it.get('title') or '(untitled)'}: {(it.get('summary') or '').strip()}"
            for it in items
        )
    else:
        context = "(the library is empty)"
    prompt = f"Library items:\n{context}\n\nQuestion: {question}"
    return gateway.complete(prompt, role="planner", system=ASK_SYSTEM).strip()
