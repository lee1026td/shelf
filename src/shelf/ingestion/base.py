"""Ingestion interfaces and a facade stub.

Defines the *contracts* the real fetchers/parsers (RSS, sitemap, HTML, PDF via
Docling) will satisfy in later phases. The :class:`Ingestor` facade is a stub: its
methods raise :class:`FeatureNotReady` so callers and tests can depend on a stable
signature today (plan §10.3 ``ingestion/``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from shelf.errors import FeatureNotReady


@dataclass
class FetchResult:
    """Raw result of fetching a URL/source."""

    url: str
    status: int
    content_type: str | None = None
    raw: bytes | None = None
    fetched_at: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Normalized content extracted from a :class:`FetchResult` or local file."""

    title: str | None = None
    text: str | None = None
    markdown: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class Fetcher(Protocol):
    """Anything that can retrieve content for a URL/source."""

    def fetch(self, url: str) -> FetchResult: ...


class Parser(Protocol):
    """Anything that can turn raw content into a :class:`ParsedDocument`."""

    def parse(self, raw: bytes, content_type: str | None = None) -> ParsedDocument: ...


class Ingestor:
    """Facade for ``/clip`` and ``/import``. STUB (Phase 1 remainder)."""

    PHASE = 1

    def clip(self, url: str) -> ParsedDocument:
        raise FeatureNotReady("/clip ingestion (URL → item)", self.PHASE)

    def import_path(self, path: str) -> list[ParsedDocument]:
        raise FeatureNotReady("/import ingestion (local PDF/HTML/Markdown)", self.PHASE)
