"""Watcher daemon. STUB (Phase 4, plan §9.2).

Schedules periodic source checks (RSS/sitemap first), hashes snapshots, computes
text/semantic diffs, files review items, and assembles weekly digests. Explicit-run
first; no autonomous background crawling in the MVP.
"""

from __future__ import annotations

from shelf.errors import FeatureNotReady


class WatcherDaemon:
    """Stub watcher daemon."""

    PHASE = 4

    def __init__(self, workspace: object | None = None) -> None:
        self._workspace = workspace

    def start(self) -> None:
        raise FeatureNotReady("Watcher daemon (start)", self.PHASE)

    def stop(self) -> None:
        raise FeatureNotReady("Watcher daemon (stop)", self.PHASE)

    def run_once(self, topic: str | None = None) -> None:
        raise FeatureNotReady("Watcher run", self.PHASE)
