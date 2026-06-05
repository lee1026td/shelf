"""Textual application. STUB (Phase 5, plan §4)."""

from __future__ import annotations

from shelf.errors import FeatureNotReady


class ShelfTUI:
    """Stub full-screen TUI app."""

    PHASE = 5

    def __init__(self, workspace: object | None = None) -> None:
        self._workspace = workspace

    def run(self) -> None:
        raise FeatureNotReady("Full Textual TUI", self.PHASE)


def launch_tui(workspace: object | None = None) -> None:
    """Entry point the REPL/`/` palette will call. STUB (Phase 5)."""
    raise FeatureNotReady("Full Textual TUI", ShelfTUI.PHASE)
