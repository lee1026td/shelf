"""`shelf chat` / `shelf tui` - enter the research chat surface.

Bare `shelf` and `shelf chat` open the chat: the full-screen **Textual TUI** on an
interactive terminal, falling back to the line **REPL** when stdin/stdout is piped or
textual is unavailable (so scripting and tests keep working). `shelf tui` forces the TUI.
"""

import sys
from pathlib import Path

import typer

from shelf.cli.errors import cli_errors
from shelf.repl import run_repl
from shelf.ui.console import info
from shelf.workspace import Workspace, resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def _tui_available() -> bool:
    """True when we own an interactive terminal and textual can be imported."""
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return False
    try:
        import textual  # noqa: F401

        return True
    except Exception:
        return False


def enter_chat(workspace: Workspace) -> None:
    """Launch the TUI on an interactive terminal, else the line REPL."""
    if _tui_available():
        from shelf.tui import launch_tui

        launch_tui(workspace)
    else:
        run_repl(workspace)


def chat_command() -> None:
    """Open the shelf research chat (TUI on a terminal, line REPL when piped)."""
    with cli_errors():
        workspace = Workspace.discover()
        if workspace is None:
            info("No shelf workspace found here. Run `shelf init` first.")
            raise typer.Exit(0)
        enter_chat(workspace)


def tui_command(workspace: Path | None = _WORKSPACE_OPT) -> None:
    """Open the full-screen Textual TUI."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        from shelf.tui import launch_tui

        launch_tui(ws)
