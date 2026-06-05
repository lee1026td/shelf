"""`shelf model` / `shelf summarize` / `shelf ask` - the Phase 2 LLM commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

from shelf.cli.errors import cli_errors
from shelf.config import load_config
from shelf.llm import ModelGateway, ask_library, summarize_item
from shelf.store import Store
from shelf.ui.console import console
from shelf.ui.model_view import render_models
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def model_command(
    probe: bool = typer.Option(True, "--probe/--no-probe", help="Test endpoint reachability."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Show configured model profiles and (by default) probe the planner endpoint."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        config = load_config(ws.config_path)
        result = ModelGateway(config).probe("planner") if probe else None
        render_models(console, config, result)


def summarize_command(
    item_id: int = typer.Argument(..., help="Item id to summarize (see `shelf inbox`)."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Generate and store an LLM summary for an item."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        gateway = ModelGateway(load_config(ws.config_path))
        with Store.open(ws.db_path) as store:
            summary = summarize_item(ws, store, gateway, item_id)
        console.print(Panel(summary, title=f"item {item_id} summary", border_style="green"))


def ask_command(
    question: str = typer.Argument(..., help="A question to answer from the local library."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Answer a question grounded in the local library."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        gateway = ModelGateway(load_config(ws.config_path))
        with Store.open(ws.db_path) as store:
            answer = ask_library(ws, store, gateway, question)
        console.print(Panel(answer, title="answer", border_style="cyan"))
