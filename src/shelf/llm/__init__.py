"""LLM gateway (Phase 2) — OpenAI-compatible model access."""

from __future__ import annotations

from shelf.llm.client import ChatClient, OpenAICompatibleClient
from shelf.llm.gateway import ModelGateway, ProbeResult
from shelf.llm.tasks import ask_library, summarize_item

__all__ = [
    "ChatClient",
    "ModelGateway",
    "OpenAICompatibleClient",
    "ProbeResult",
    "ask_library",
    "summarize_item",
]
