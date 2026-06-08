"""`shelf compile` - synthesize a cited brief from the library (the /compile command)."""

from pathlib import Path

import typer

from shelf.cli.errors import cli_errors
from shelf.config import load_config
from shelf.discovery import compile_topic
from shelf.llm import ModelGateway
from shelf.store import Store
from shelf.ui.console import console, info, warn
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def compile_command(
    topic: str = typer.Argument(..., help="The topic to compile a document for."),
    kind: str = typer.Option("brief", "--kind", "-k", help="brief | landscape | faq | timeline."),
    steps: int = typer.Option(10, "--steps", min=1, max=40, help="Agent step budget."),
    workspace: Path | None = _WORKSPACE_OPT,
) -> None:
    """Compile a cited document on a topic from the library, saved under Compilations/."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        config = load_config(ws.config_path)
        if config.planner_model == "none":
            warn("No model configured. Run `shelf model` to pick one first.")
            raise typer.Exit(1)

        styles = {"retry": "yellow", "error": "red", "final": "green", "note": "dim"}

        def on_event(kind_: str, message: str) -> None:
            console.print(f"  - {message}", style=styles.get(kind_, "dim"), highlight=False)

        gateway = ModelGateway(config)
        with Store.open(ws.db_path) as store:
            outcome = compile_topic(
                ws, gateway, topic, store=store, kind=kind, config=config,
                max_steps=steps, on_event=on_event,
            )
        console.print(outcome.document or "(empty)", highlight=False, markup=False)
        if outcome.output_path:
            info(f"Saved to {outcome.output_path} (stopped: {outcome.stopped_reason}).")
        else:
            warn(f"Not saved (stopped: {outcome.stopped_reason}).")
