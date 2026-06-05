"""Rich-based output components used by the CLI.

This package is presentation-only (no business logic). The full-screen Textual
application is a separate, later concern under ``shelf.tui`` (Phase 5).
"""

from __future__ import annotations

from shelf.ui.console import console, err_console, error, info, success, warn
from shelf.ui.status_view import StatusReport, render_status, status_bar_line

__all__ = [
    "StatusReport",
    "console",
    "err_console",
    "error",
    "info",
    "render_status",
    "status_bar_line",
    "success",
    "warn",
]
