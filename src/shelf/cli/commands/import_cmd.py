"""`shelf import PATH` - the ``/import`` command."""

from pathlib import Path
from typing import Optional

import typer

from shelf.cli.errors import cli_errors
from shelf.ingestion import import_path
from shelf.store import Store
from shelf.ui.console import console
from shelf.ui.ingest_view import render_import_outcome
from shelf.workspace import resolve_workspace


def import_command(
    path: Path = typer.Argument(..., help="File or folder of PDF/HTML/Markdown/text to import."),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Recurse into subfolders (default: yes)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan, write nothing."),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace directory (else discovered)."
    ),
) -> None:
    """Import local files into the library as Items."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        if dry_run:
            outcome = import_path(ws, path, recursive=recursive, dry_run=True)
        else:
            with Store.open(ws.db_path) as store:
                outcome = import_path(ws, path, store=store, recursive=recursive)
        render_import_outcome(console, outcome)
