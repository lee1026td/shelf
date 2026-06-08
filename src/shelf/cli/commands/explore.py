"""`shelf explore` - the Phase 3 topic-discovery command (mirrors REPL `/explore`)."""

from pathlib import Path

import typer

from shelf.cli.errors import cli_errors
from shelf.config import load_config
from shelf.discovery import explore_topic
from shelf.llm import ModelGateway
from shelf.services import enable_remote_search
from shelf.store import Store
from shelf.ui.console import console, info, warn
from shelf.ui.library_view import render_sources
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def explore_command(
    topic: str = typer.Argument(..., help="A topic to research and discover sources for."),
    web: bool = typer.Option(
        False, "--web", help="Enable web search egress (persists privacy.remote_search)."
    ),
    steps: int = typer.Option(12, "--steps", min=1, max=40, help="Agent step budget."),
    workspace: Path | None = _WORKSPACE_OPT,
) -> None:
    """Discover and propose sources for a topic, then print a cited brief."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        config = load_config(ws.config_path)
        if config.planner_model == "none":
            warn("No model configured. Run `shelf model` to pick one first.")
            raise typer.Exit(1)
        if web and not config.privacy.remote_search:
            enable_remote_search(ws)
            config = load_config(ws.config_path)
            info("Web search enabled (privacy.remote_search).")
        if not config.privacy.remote_search:
            info(
                "Web search is off (privacy.remote_search) - exploring the local library "
                "only. Pass --web to enable it."
            )
        styles = {"retry": "yellow", "error": "red", "final": "green", "note": "dim"}

        def on_event(kind: str, message: str) -> None:
            console.print(f"  - {message}", style=styles.get(kind, "dim"), highlight=False)

        gateway = ModelGateway(config)
        with Store.open(ws.db_path) as store:
            outcome = explore_topic(
                ws, gateway, topic, store=store, config=config, max_steps=steps, on_event=on_event
            )
        if outcome.candidates:
            render_sources(console, outcome.candidates)
        console.print(outcome.brief or "(no brief)", highlight=False, markup=False)
        console.print(
            f"(stopped: {outcome.stopped_reason}; {outcome.steps} tool step(s); "
            f"{len(outcome.candidates)} source(s) proposed -> review queue)",
            style="dim",
        )
