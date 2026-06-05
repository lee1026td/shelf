"""OpenAI-compatible HTTP client (chat + embeddings) over the standard library.

Kept dependency-free (urllib) and behind a small ``ChatClient`` protocol so the
gateway can be tested with a fake client and later swap in httpx/streaming.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from shelf.errors import LLMError

DEFAULT_TIMEOUT = 60
# Generous so reasoning models (qwen3, deepseek-r1, ...) can think AND still emit a
# final answer within budget. Too low and `content` comes back empty (all thinking).
DEFAULT_MAX_TOKENS = 4096

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _message_text(message: dict[str, Any]) -> str:
    """Extract the assistant text from a chat message.

    Prefers ``content``; falls back to ``reasoning``/``reasoning_content`` for
    thinking models that leave ``content`` empty (e.g. qwen3 via Ollama). Strips any
    inline ``<think>...</think>`` block.
    """
    content = (message.get("content") or "").strip()
    if not content:
        content = (message.get("reasoning") or message.get("reasoning_content") or "").strip()
    return _THINK_RE.sub("", content).strip()


class ChatClient(Protocol):
    """Minimal OpenAI-compatible surface the gateway depends on."""

    def chat(
        self,
        base_url: str,
        model: str,
        messages: list[dict[str, str]],
        *,
        api_key: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str: ...

    def embeddings(
        self, base_url: str, model: str, texts: list[str], *, api_key: str | None = None
    ) -> list[list[float]]: ...

    def list_models(self, base_url: str, *, api_key: str | None = None) -> list[str]: ...


class OpenAICompatibleClient:
    """Talks to any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, OpenAI...)."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def _request(
        self, url: str, *, data: bytes | None, api_key: str | None, method: str
    ) -> dict[str, Any]:
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:200].decode("utf-8", "replace")
            raise LLMError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise LLMError(f"Could not reach {url}: {exc}") from exc

    def _post(self, url: str, payload: dict[str, Any], api_key: str | None) -> dict[str, Any]:
        return self._request(
            url, data=json.dumps(payload).encode("utf-8"), api_key=api_key, method="POST"
        )

    def _get(self, url: str, api_key: str | None) -> dict[str, Any]:
        return self._request(url, data=None, api_key=api_key, method="GET")

    def chat(
        self,
        base_url: str,
        model: str,
        messages: list[dict[str, str]],
        *,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.2,
    ) -> str:
        url = base_url.rstrip("/") + "/chat/completions"
        body = self._post(
            url,
            {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            api_key,
        )
        try:
            message = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected chat response from {url}: {body!r:.200}") from exc
        return _message_text(message)

    def embeddings(
        self, base_url: str, model: str, texts: list[str], *, api_key: str | None = None
    ) -> list[list[float]]:
        url = base_url.rstrip("/") + "/embeddings"
        body = self._post(url, {"model": model, "input": texts}, api_key)
        try:
            return [list(row["embedding"]) for row in body["data"]]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected embeddings response from {url}: {body!r:.200}") from exc

    def list_models(self, base_url: str, *, api_key: str | None = None) -> list[str]:
        url = base_url.rstrip("/") + "/models"
        body = self._get(url, api_key)
        try:
            return [str(entry["id"]) for entry in body.get("data", [])]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected models response from {url}: {body!r:.200}") from exc
