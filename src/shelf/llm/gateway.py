"""OpenAI-compatible model gateway (Phase 2, plan §11.1).

Routes role profiles (``planner``, ``embeddings``, ...) from config to an
OpenAI-compatible endpoint, enforces the egress policy (localhost allowed; a
non-local endpoint requires ``privacy.remote_llm: true``), and exposes a capability
probe so callers don't assume tools/json/vision/embeddings work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from shelf.errors import LLMError
from shelf.llm.client import ChatClient, OpenAICompatibleClient

if TYPE_CHECKING:
    from shelf.config import Config, ModelProfile

API_KEY_ENV = "SHELF_API_KEY"
# Hostnames treated as "local" (no egress, allowed by default).
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", ""})


@dataclass(frozen=True)
class ProbeResult:
    role: str
    model: str
    base_url: str
    reachable: bool
    error: str | None = None


class ModelGateway:
    """OpenAI-compatible gateway. Inject a fake ``client`` in tests."""

    def __init__(
        self,
        config: "Config",
        client: ChatClient | None = None,
        api_key: str | None = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAICompatibleClient()
        self._api_key = api_key if api_key is not None else os.environ.get(API_KEY_ENV)

    def _profile(self, role: str) -> "ModelProfile":
        profile = self._config.models.get(role)
        if profile is None or not profile.model:
            raise LLMError(
                f"No model configured for role '{role}'. "
                "Set it in .shelf/config.yaml (see /model)."
            )
        return profile

    def _check_egress(self, profile: "ModelProfile") -> None:
        host = (urlsplit(profile.base_url).hostname or "").lower()
        if host in LOCAL_HOSTS:
            return
        if not self._config.privacy.remote_llm:
            raise LLMError(
                f"Remote LLM endpoint {profile.base_url} is blocked by default. "
                "Set privacy.remote_llm: true to allow sending content off-machine."
            )

    def complete(
        self,
        prompt: str,
        *,
        role: str = "planner",
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        profile = self._profile(role)
        self._check_egress(profile)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._client.chat(
            profile.base_url,
            profile.model,
            messages,
            api_key=self._api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def embed(self, texts: list[str], *, role: str = "embeddings") -> list[list[float]]:
        profile = self._profile(role)
        self._check_egress(profile)
        return self._client.embeddings(
            profile.base_url, profile.model, texts, api_key=self._api_key
        )

    def probe(self, role: str = "planner") -> ProbeResult:
        """Best-effort reachability check; never raises."""
        try:
            profile = self._profile(role)
        except LLMError as exc:
            return ProbeResult(role, "(none)", "(none)", reachable=False, error=str(exc))
        try:
            self._check_egress(profile)
            self._client.chat(
                profile.base_url,
                profile.model,
                [{"role": "user", "content": "ping"}],
                api_key=self._api_key,
                max_tokens=1,
            )
            return ProbeResult(role, profile.model, profile.base_url, reachable=True)
        except Exception as exc:  # probe must report, not raise
            return ProbeResult(
                role, profile.model, profile.base_url, reachable=False, error=str(exc)
            )
