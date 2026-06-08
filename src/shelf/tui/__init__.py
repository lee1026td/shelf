"""Full-screen Textual TUI (Phase 5, first slice).

Distinct from ``shelf.ui`` (Rich components used by the plain CLI). This package is the
full Textual application; the first slice is the chat/agent surface with a scrollable
transcript, a bottom-docked input, a slash-command dropdown, and tool-call cards.
"""

from __future__ import annotations

from shelf.tui.app import ShelfApp, launch_tui

__all__ = ["ShelfApp", "launch_tui"]
