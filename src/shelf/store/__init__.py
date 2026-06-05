"""Local SQLite metadata store (canonical alongside the filesystem)."""

from __future__ import annotations

from shelf.store.migrations import SCHEMA_VERSION
from shelf.store.sqlite_store import LibraryCounts, Store

__all__ = ["SCHEMA_VERSION", "LibraryCounts", "Store"]
