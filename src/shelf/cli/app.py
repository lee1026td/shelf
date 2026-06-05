"""The Typer application: command registration and the ``shelf`` entrypoint.

Bare ``shelf`` (no subcommand) enters the research REPL inside a workspace; with a
subcommand it behaves as a normal CLI. No ``from __future__ import annotations`` -
Typer introspects real annotations on the callback below.
"""

import typer

from shelf import __version__
from shelf.cli.commands.chat import chat_command
from shelf.cli.commands.clip import clip_command
from shelf.cli.commands.import_cmd import import_command
from shelf.cli.commands.init import init_command
from shelf.cli.commands.library import inbox_command, search_command, sources_command
from shelf.cli.commands.model import ask_command, model_command, summarize_command
from shelf.cli.commands.status import status_command
from shelf.cli.errors import cli_errors
from shelf.repl import run_repl
from shelf.ui.console import ensure_safe_streams, info
from shelf.workspace import Workspace

app = typer.Typer(
    name="shelf",
    help="Local-first, TUI-first CLI research library agent.",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the shelf version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """shelf - discover, watch, and compile sources into a personal library.

    Run `shelf` with no command inside a workspace to open the research REPL.
    """
    if ctx.invoked_subcommand is not None:
        return
    # Bare `shelf`: enter the REPL if we're in a workspace, else point the way.
    with cli_errors():
        workspace = Workspace.discover()
        if workspace is None:
            info(
                "No shelf workspace found here. Run `shelf init` to create one, "
                "or `shelf --help` for commands."
            )
            raise typer.Exit(0)
        run_repl(workspace)


# Register commands. Each command owns its own error handling via `cli_errors()`.
app.command("init", help="Create a local research-library workspace.")(init_command)
app.command("status", help="Show workspace, model, and library counts (the /status view).")(
    status_command
)
app.command("chat", help="Enter the research REPL (slash commands + chat).")(chat_command)
app.command("clip", help="Fetch a URL and save it as an Item (the /clip command).")(clip_command)
app.command("import", help="Import local PDF/HTML/Markdown files (the /import command).")(
    import_command
)
app.command("inbox", help="List newly collected items (the /inbox command).")(inbox_command)
app.command("search", help="Keyword search over collected items (the /search command).")(
    search_command
)
app.command("sources", help="List the source universe (the /sources command).")(sources_command)
app.command("model", help="Show model profiles and probe the endpoint (the /model command).")(
    model_command
)
app.command("summarize", help="LLM-summarize an item (the /summarize command).")(summarize_command)
app.command("ask", help="Answer a question from the library (the /ask command).")(ask_command)


@app.command("version", help="Print the installed shelf version.")
def version_command() -> None:
    typer.echo(__version__)


def main() -> None:
    """Console-script entrypoint (`shelf`)."""
    ensure_safe_streams()
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
