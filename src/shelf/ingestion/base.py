"""Ingestion interfaces and value objects shared by fetchers/parsers/services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Bumped whenever parsing output changes in a way that invalidates snapshots.
PARSER_VERSION = "p1"


@dataclass
class FetchResult:
    """Raw result of fetching a URL/source."""

    url: str
    status: int
    content_type: str | None = None
    raw: bytes = b""
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
