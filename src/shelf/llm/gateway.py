"""OpenAI-compatible model gateway. STUB (Phase 2, plan §11.1).

The real gateway routes role profiles (``planner``, ``embeddings``, …) to
OpenAI-compatible endpoints and runs a capability probe rather than trusting the
configured ``capabilities``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shelf.errors import FeatureNotReady

if TYPE_CHECKING:  # avoid importing config at runtime for a stub
    from shelf.config import Config


class ModelGateway:
    """Stub gateway. Construct freely; calling a method raises FeatureNotReady."""

    PHASE = 2

    def __init__(self, config: "Config | None" = None) -> None:
        self._config = config

    def complete(self, prompt: str, *, role: str = "planner", **kwargs: Any) -> str:
        raise FeatureNotReady("LLM completion", self.PHASE)

    def embed(self, texts: list[str], *, role: str = "embeddings") -> list[list[float]]:
        raise FeatureNotReady("LLM embeddings", self.PHASE)

    def probe(self, role: str = "planner") -> dict[str, Any]:
        raise FeatureNotReady("LLM capability probe", self.PHASE)
