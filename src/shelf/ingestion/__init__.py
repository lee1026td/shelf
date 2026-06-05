"""Ingestion: fetch + parse + import into the local library (Phase 1).

`/clip` (URL -> Item) and `/import` (local files -> Items) are implemented here.
RSS/sitemap discovery and the browser fallback arrive with the watcher (Phase 4).
"""

from __future__ import annotations

from shelf.ingestion.base import (
    PARSER_VERSION,
    Fetcher,
    FetchResult,
    ParsedDocument,
    Parser,
)
from shelf.ingestion.clip import ClipOutcome, clip_url
from shelf.ingestion.fetch import HttpFetcher
from shelf.ingestion.importer import ImportedFile, ImportOutcome, import_path
from shelf.ingestion.parsers import (
    SUPPORTED_EXTENSIONS,
    detect_kind,
    parse_document,
)

__all__ = [
    "PARSER_VERSION",
    "SUPPORTED_EXTENSIONS",
    "ClipOutcome",
    "FetchResult",
    "Fetcher",
    "HttpFetcher",
    "ImportOutcome",
    "ImportedFile",
    "ParsedDocument",
    "Parser",
    "clip_url",
    "detect_kind",
    "import_path",
    "parse_document",
]
