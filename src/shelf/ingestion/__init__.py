"""Ingestion (fetch + parse). STUB — interfaces only (Phase 1 remainder / Phase 4)."""

from __future__ import annotations

from shelf.ingestion.base import (
    FetchResult,
    Fetcher,
    Ingestor,
    ParsedDocument,
    Parser,
)

__all__ = ["FetchResult", "Fetcher", "Ingestor", "ParsedDocument", "Parser"]
