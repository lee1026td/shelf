"""The REPL loop and per-line dispatch.

Design notes:
- ``ReplSession.handle(line)`` is the testable unit: feed it a line, it dispatches
  and prints. ``run_repl`` is the thin I/O loop around it.
- Output uses *literal* Rich styles (not theme names) so a bare ``Console`` passed
  in tests never hits a MissingStyle error. ``render_status`` manages its own theme.
- All emitted text is ASCII (the cp949 console constraint - see ui/console.py).
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Callable

from rich.console import Console
from rich.table import Table

from shelf.errors import ShelfError
from shelf.repl.commands import (
    COMMANDS_BY_NAME,
    EXIT_ALIASES,
    HELP_ALIASES,
    SLASH_COMMANDS,
)
from shelf.services import gather_status
from shelf.ui.console import console as default_console
from shelf.ui.status_view import render_status, status_bar_line
from shelf.workspace import Workspace

PROMPT = "shelf> "

# Unicode categories considered "leading junk": control, format (incl. BOM/ZWSP/
# bidi), surrogate, private-use. Piped stdin can prepend a UTF-8 BOM that, decoded
# under a non-UTF-8 code page (e.g. cp949), becomes U+FFFD + a surrogate rather than
# a clean U+FEFF - so we strip any leading run of these before dispatch.
_JUNK_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co"})


def _strip_leading_junk(line: str) -> str:
    index = 0
    for char in line:
        if char == "�" or unicodedata.category(char) in _JUNK_CATEGORIES:
            index += 1
        else:
            break
    return line[index:].strip()


class ReplSession:
    """Holds REPL state and dispatches one input line at a time."""

    def __init__(self, workspace: Workspace, console: Console | None = None) -> None:
        self.workspace = workspace
        self.console = console or default_console
        self.running = True

    def handle(self, line: str) -> None:
        text = _strip_leading_junk(line)
        if not text:
            return
        if text.startswith("/"):
            self._handle_slash(text[1:])
        else:
            self._handle_text(text)

    # --- dispatch -----------------------------------------------------------
    def _handle_slash(self, body: str) -> None:
        name = body.split(maxsplit=1)[0].lower() if body.strip() else ""
        if name in EXIT_ALIASES:
            self.running = False
            self.console.print("Bye.", style="dim")
            return
        if name in HELP_ALIASES:
            self._print_help()
            return
        if name == "status":
            self._print_status()
            return
        command = COMMANDS_BY_NAME.get(name)
        if command is None:
            self.console.print(
                f"Unknown command: /{name}. Type /help for the list.", style="yellow"
            )
            return
        self.console.print(
            f"Note: /{command.name} is not implemented yet - planned for Phase "
            f"{command.phase}.",
            style="yellow",
        )

    def _handle_text(self, text: str) -> None:
        self.console.print(
            "Note: free-text chat / research routing is not implemented yet - "
            "planned for Phase 2 (LLM gateway) + Phase 3 (discovery). Type /help.",
            style="yellow",
        )

    # --- built-ins ----------------------------------------------------------
    def _print_status(self) -> None:
        try:
            report = gather_status(self.workspace)
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        render_status(self.console, report)

    def _print_help(self) -> None:
        table = Table(title="shelf commands", title_style="bold cyan", expand=False)
        table.add_column("Command", style="bold")
        table.add_column("When")
        table.add_column("What")
        for command in SLASH_COMMANDS:
            when = "now" if command.available else f"Phase {command.phase}"
            when_style = "green" if command.available else "bright_black"
            table.add_row(
                f"/{command.name}", f"[{when_style}]{when}[/{when_style}]", command.summary
            )
        self.console.print(table)
        self.console.print(
            "Type a topic in plain text to chat (coming in Phase 2/3). /exit to quit.",
            style="dim",
        )


def run_repl(
    workspace: Workspace,
    *,
    console: Console | None = None,
    reader: Callable[[], str] | None = None,
) -> None:
    """Run the interactive loop until EOF / ``/exit``.

    ``reader`` is injectable for tests; in real use it reads from prompt_toolkit
    (history/editing) when attached to a TTY, falling back to ``input()``.
    """
    out = console or default_console
    session = ReplSession(workspace, console=out)

    out.print(f"shelf REPL - {workspace.root.name}", style="bold cyan")
    try:
        report = gather_status(workspace)
        out.print(
            status_bar_line(report),
            style="bold cyan",
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
    except ShelfError as exc:
        out.print(f"Error: {exc}", style="red")
    out.print("Type /help for commands, /exit to quit.", style="dim")

    read = reader or _make_reader()
    while session.running:
        try:
            line = read()
        except (EOFError, KeyboardInterrupt):
            out.print("")
            break
        session.handle(line)


def _make_reader() -> Callable[[], str]:
    """Build the default input reader: prompt_toolkit on a TTY, else ``input()``.

    On a TTY we use prompt_toolkit (history/editing). When stdin is piped, we
    normalize its encoding to UTF-8 first: PowerShell prepends a UTF-8 BOM that, if
    decoded under a code-page like cp949, becomes mojibake (a CJK letter + a
    surrogate) that ``_strip_leading_junk`` can't recognize. Decoding as UTF-8 turns
    it into a clean U+FEFF, which is then stripped.
    """
    is_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    if is_tty:
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory

            ptk: PromptSession = PromptSession(history=InMemoryHistory())
            return lambda: ptk.prompt(PROMPT)
        except Exception:
            pass
    else:
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass

    def _read() -> str:
        return input(PROMPT)

    return _read
