"""`shelf status` - the ``/status`` command.

Shows the active workspace, model, remote posture, and library counts.
"""

from pathlib import Path
from typing import Optional

import typer

from shelf.cli.errors import cli_errors
from shelf.services import gather_status
from shelf.ui.console import console
from shelf.ui.status_view import render_status
from shelf.workspace import resolve_workspace


def status_command(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace directory (else discovered from CWD/$SHELF_HOME)."
    ),
) -> None:
    """Show workspace, model, remote posture, and counts."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        report = gather_status(ws)
        render_status(console, report)
