"""`shelf track` - mark a topic as tracked with a refresh frequency (the /track command)."""

from pathlib import Path

import typer

from shelf.cli.errors import cli_errors
from shelf.services import track_topic
from shelf.ui.console import success
from shelf.workspace import resolve_workspace

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Workspace directory (else discovered)."
)


def track_command(
    topic: str = typer.Argument(..., help="The topic to promote to tracked."),
    frequency: str = typer.Option("weekly", "--frequency", "-f", help="Refresh cadence."),
    workspace: Path | None = _WORKSPACE_OPT,
) -> None:
    """Promote a topic to tracked (records intent; the watcher collects it in Phase 4)."""
    with cli_errors():
        ws = resolve_workspace(explicit=workspace)
        track_topic(ws, topic, frequency=frequency)
        success(
            f"Topic '{topic}' is now tracked ({frequency}). Candidate sources stay in the "
            "review queue until approved."
        )
