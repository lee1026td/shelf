"""`shelf init` - create a local research-library workspace.

Note: no ``from __future__ import annotations`` here - Typer introspects the real
runtime annotations of command parameters.
"""

from pathlib import Path
from typing import Optional

import typer

from shelf.cli.errors import cli_errors
from shelf.ui.console import info, success
from shelf.workspace import initialize_workspace


def init_command(
    path: Path = typer.Argument(
        Path("."),
        help="Directory to initialize as a shelf workspace (created if missing).",
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Library name (defaults to the directory name)."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Re-initialize even if a workspace already exists."
    ),
) -> None:
    """Create the local directory layout, config, and SQLite store."""
    with cli_errors():
        workspace = initialize_workspace(path, name=name, force=force)
        success(f"Initialized shelf workspace at {workspace.root}")
        info(
            "Next: run `shelf status` to see your library, "
            "or `shelf chat` to start research (Phase 5)."
        )
