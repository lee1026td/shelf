"""The shelf research REPL (thin shell).

Entered by bare ``shelf`` (or ``shelf chat``) inside a workspace. It hosts slash
commands and (later) natural-language chat. Implemented commands run for real today
(``/status``, ``/help``, ``/exit``); everything else announces the phase that will
deliver it. The full Textual command-palette TUI remains Phase 5.
"""

from __future__ import annotations

from shelf.repl.session import ReplSession, run_repl

__all__ = ["ReplSession", "run_repl"]
