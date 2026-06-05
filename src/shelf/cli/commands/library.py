"""`shelf inbox` / `shelf search` / `shelf sources` - browse the local library."""

from pathlib import Path
from typing import Optional

import typer

from shelf.cli.errors import cli_errors
from shelf.store import Store
from shelf.ui.console import console
from shelf.ui.library_view import render_items, render_sources
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def inbox_command(
    limit: int = typer.Option(20, "--limit", "-n", help="Max items to show."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """List newly collected items (status='new')."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        with Store.open(ws.db_path) as store:
            items = store.list_items(status="new", limit=limit)
        render_items(console, items, title="inbox")


def search_command(
    query: str = typer.Argument(..., help="Keyword to search in title/summary/url."),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Keyword search over collected items."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        with Store.open(ws.db_path) as store:
            items = store.search_items(query, limit=limit)
        render_items(console, items, title=f"search: {query}")


def sources_command(
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """List the source universe."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        with Store.open(ws.db_path) as store:
            sources = store.list_sources()
        render_sources(console, sources)
