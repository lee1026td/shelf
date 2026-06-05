"""`shelf model` / `shelf summarize` / `shelf ask` - the Phase 2 LLM commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.text import Text

from shelf.cli.errors import cli_errors
from shelf.config import load_config
from shelf.llm import ModelGateway, ask_library, summarize_item
from shelf.services import set_model
from shelf.store import Store
from shelf.ui.console import console, success
from shelf.ui.model_view import render_model_list, render_models
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)

# `shelf model` is a group: bare `shelf model` shows profiles; subcommands manage them.
model_app = typer.Typer(
    help="Show, list, and select models (chat + embeddings).",
    no_args_is_help=False,
    add_completion=False,
)


@model_app.callback(invoke_without_command=True)
def model_main(
    ctx: typer.Context,
    probe: bool = typer.Option(True, "--probe/--no-probe", help="Test endpoint reachability."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Show configured model profiles and (by default) probe the planner endpoint."""
    if ctx.invoked_subcommand is not None:
        return
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        config = load_config(ws.config_path)
        result = ModelGateway(config).probe("planner") if probe else None
        render_models(console, config, result)


@model_app.command("list")
def model_list(
    role: str = typer.Argument("planner", help="Role to list models for (planner/embeddings)."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """List the models the role's endpoint offers."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        config = load_config(ws.config_path)
        models = ModelGateway(config).list_models(role)
        base_url = config.models[role].base_url if role in config.models else "?"
        render_model_list(console, role, base_url, models)


@model_app.command("set")
def model_set(
    role: str = typer.Argument(..., help="planner | embeddings (or any role)."),
    model: str = typer.Argument(..., help="Model id to use for that role."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Also set the endpoint URL."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Select the model (and optionally endpoint) for a role; persists to config."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        profile = set_model(ws, role, model=model, base_url=base_url)
        success(f"{role} -> {profile.model} @ {profile.base_url}")


@model_app.command("use")
def model_use(
    model: str = typer.Argument(..., help="Model id for the planner (chat) role."),
    workspace: Optional[Path] = _WORKSPACE_OPT,
) -> None:
    """Shorthand: set the planner (chat) model."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        profile = set_model(ws, "planner", model=model)
        success(f"planner -> {profile.model}")


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
        console.print(Panel(Text(summary), title=f"item {item_id} summary", border_style="green"))


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
        console.print(Panel(Text(answer), title="answer", border_style="cyan"))
