"""Notion adapter. STUB (Phase 6, plan §7, §9.2).

Notion is an *optional* GUI/review surface; the local store is always canonical.
The adapter creates the Notion schema, performs curated sync, and imports review
status — rate-limit, conflict, and privacy aware.
"""

from __future__ import annotations

from shelf.errors import FeatureNotReady


class NotionAdapter:
    """Stub Notion adapter."""

    PHASE = 6

    def __init__(self, config: object | None = None) -> None:
        self._config = config

    def setup(self, parent_page_id: str | None = None) -> None:
        raise FeatureNotReady("Notion setup (schema creation)", self.PHASE)

    def sync(self, mode: str = "curated") -> None:
        raise FeatureNotReady("Notion sync", self.PHASE)

    def import_reviews(self) -> list[dict[str, object]]:
        raise FeatureNotReady("Notion review-status import", self.PHASE)
