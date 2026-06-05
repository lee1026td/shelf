"""`shelf chat` - enter the research REPL (slash commands + chat).

Both bare `shelf` and `shelf chat` open the same REPL. The REPL is a thin shell
today: `/status`/`/help`/`/exit` work for real, other slash commands and free-text
chat announce the phase that will deliver them. The full Textual TUI is Phase 5.
"""

import typer

from shelf.cli.errors import cli_errors
from shelf.repl import run_repl
from shelf.ui.console import info
from shelf.workspace import Workspace


def chat_command() -> None:
    """Open the shelf research REPL."""
    with cli_errors():
        workspace = Workspace.discover()
        if workspace is None:
            info("No shelf workspace found here. Run `shelf init` first.")
            raise typer.Exit(0)
        run_repl(workspace)
