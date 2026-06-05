"""Full-screen Textual TUI. STUB — interface only (Phase 5).

Distinct from ``shelf.ui`` (Rich components used by the CLI today). This package is
the full Textual application: command palette, review queue, diff viewer, wizards.
"""

from __future__ import annotations

from shelf.tui.app import ShelfTUI, launch_tui

__all__ = ["ShelfTUI", "launch_tui"]
