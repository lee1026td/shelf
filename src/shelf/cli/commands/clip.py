"""`shelf clip URL` - the ``/clip`` command."""

from pathlib import Path
from typing import Optional

import typer

from shelf.cli.errors import cli_errors
from shelf.ingestion import clip_url
from shelf.store import Store
from shelf.ui.console import console
from shelf.ui.ingest_view import render_clip_outcome
from shelf.workspace import resolve_workspace


def clip_command(
    url: str = typer.Argument(..., help="URL (http/https/file) to fetch and save."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be saved, write nothing."),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace directory (else discovered)."
    ),
) -> None:
    """Fetch a URL and save it as an Item in the library."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        if dry_run:
            outcome = clip_url(ws, url, dry_run=True)
        else:
            with Store.open(ws.db_path) as store:
                outcome = clip_url(ws, url, store=store)
        render_clip_outcome(console, outcome)
