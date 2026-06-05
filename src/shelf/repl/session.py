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

from shelf.config import load_config
from shelf.errors import ShelfError
from shelf.ingestion import Fetcher, clip_url, import_path
from shelf.llm import ModelGateway, ask_library, summarize_item
from shelf.repl.commands import (
    COMMANDS_BY_NAME,
    EXIT_ALIASES,
    HELP_ALIASES,
    SLASH_COMMANDS,
)
from shelf.services import gather_status, set_model
from shelf.store import Store
from shelf.ui.console import console as default_console
from shelf.ui.ingest_view import render_clip_outcome, render_import_outcome
from shelf.ui.library_view import render_items, render_sources
from shelf.ui.model_view import render_model_list, render_models
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

    def __init__(
        self,
        workspace: Workspace,
        console: Console | None = None,
        fetcher: Fetcher | None = None,
        gateway: ModelGateway | None = None,
    ) -> None:
        self.workspace = workspace
        self.console = console or default_console
        self.fetcher = fetcher  # injectable for tests; None -> default HttpFetcher
        self._gateway = gateway  # injectable for tests; None -> built from config
        self.running = True

    def _get_gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = ModelGateway(load_config(self.workspace.config_path))
        return self._gateway

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
        parts = body.split(maxsplit=1)
        name = parts[0].lower() if parts and parts[0] else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        if name in EXIT_ALIASES:
            self.running = False
            self.console.print("Bye.", style="dim")
            return
        if name in HELP_ALIASES:
            self._print_help()
            return
        handler = self._dispatch().get(name)
        if handler is not None:
            handler(arg)
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

    def _dispatch(self) -> dict[str, Callable[[str], None]]:
        """Map implemented slash-command names to their handlers."""
        return {
            "status": lambda _arg: self._print_status(),
            "clip": self._handle_clip,
            "import": self._handle_import,
            "inbox": self._handle_inbox,
            "search": self._handle_search,
            "sources": lambda _arg: self._handle_sources(),
            "save": lambda arg: self._set_item_status(arg, "saved"),
            "mute": lambda arg: self._set_item_status(arg, "muted"),
            "ask": self._handle_ask,
            "summarize": self._handle_summarize,
            "model": self._handle_model,
        }

    def _handle_text(self, text: str) -> None:
        # Free text is a library-grounded question (Phase 2). Discovery/web (Phase 3).
        self._answer(text)

    def _handle_ask(self, arg: str) -> None:
        if not arg:
            self.console.print("Usage: /ask <question>", style="yellow")
            return
        self._answer(arg)

    def _answer(self, question: str) -> None:
        try:
            gateway = self._get_gateway()
            with Store.open(self.workspace.db_path) as store:
                answer = ask_library(self.workspace, store, gateway, question)
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        self.console.print(answer, highlight=False)

    def _handle_summarize(self, arg: str) -> None:
        if not arg.strip().isdigit():
            self.console.print("Usage: /summarize <item-id>", style="yellow")
            return
        item_id = int(arg.strip())
        try:
            gateway = self._get_gateway()
            with Store.open(self.workspace.db_path) as store:
                summary = summarize_item(self.workspace, store, gateway, item_id)
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        self.console.print(f"Item {item_id}: {summary}", style="green", highlight=False)

    def _handle_model(self, arg: str = "") -> None:
        tokens = arg.split()
        sub = tokens[0].lower() if tokens else ""

        if not sub:  # /model -> show profiles + probe
            config = load_config(self.workspace.config_path)
            render_models(self.console, config, self._get_gateway().probe("planner"))
            return

        if sub == "list":  # /model list [role]
            role = tokens[1] if len(tokens) > 1 else "planner"
            try:
                models = self._get_gateway().list_models(role)
            except ShelfError as exc:
                self.console.print(f"Error: {exc}", style="red")
                return
            config = load_config(self.workspace.config_path)
            base_url = config.models[role].base_url if role in config.models else "?"
            render_model_list(self.console, role, base_url, models)
            return

        if sub == "set" and len(tokens) >= 3:  # /model set <role> <model> [base_url]
            self._apply_model(tokens[1], tokens[2], tokens[3] if len(tokens) > 3 else None)
            return

        if sub == "use" and len(tokens) >= 2:  # /model use <model> (planner shorthand)
            self._apply_model("planner", tokens[1], None)
            return

        self.console.print(
            "Usage: /model | /model list [role] | /model set <role> <model> [base_url] | "
            "/model use <model>",
            style="yellow",
        )

    def _apply_model(self, role: str, model: str, base_url: str | None) -> None:
        profile = set_model(self.workspace, role, model=model, base_url=base_url)
        self._gateway = None  # rebuild from the new config on next use
        self.console.print(
            f"{role} -> {profile.model} @ {profile.base_url}", style="green", highlight=False
        )

    def _handle_clip(self, arg: str) -> None:
        if not arg:
            self.console.print("Usage: /clip <url>", style="yellow")
            return
        try:
            with Store.open(self.workspace.db_path) as store:
                outcome = clip_url(self.workspace, arg, fetcher=self.fetcher, store=store)
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        except Exception as exc:  # network/parse surprises - keep the REPL alive
            self.console.print(f"Error: clip failed: {exc}", style="red")
            return
        render_clip_outcome(self.console, outcome)

    def _handle_import(self, arg: str) -> None:
        if not arg:
            self.console.print("Usage: /import <path>", style="yellow")
            return
        try:
            with Store.open(self.workspace.db_path) as store:
                outcome = import_path(self.workspace, arg, store=store)
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        render_import_outcome(self.console, outcome)

    def _handle_inbox(self, arg: str) -> None:
        limit = int(arg) if arg.strip().isdigit() else 20
        with Store.open(self.workspace.db_path) as store:
            items = store.list_items(status="new", limit=limit)
        render_items(self.console, items, title="inbox")
        if items:
            self.console.print(
                "Triage: /save <id>  /mute <id>   (open a file under Items/ to read)",
                style="dim",
            )

    def _handle_search(self, arg: str) -> None:
        if not arg:
            self.console.print("Usage: /search <query>", style="yellow")
            return
        with Store.open(self.workspace.db_path) as store:
            items = store.search_items(arg)
        render_items(self.console, items, title=f"search: {arg}")

    def _handle_sources(self) -> None:
        with Store.open(self.workspace.db_path) as store:
            sources = store.list_sources()
        render_sources(self.console, sources)

    def _set_item_status(self, arg: str, status: str) -> None:
        if not arg.strip().isdigit():
            self.console.print(f"Usage: /{ 'save' if status=='saved' else 'mute' } <item-id>", style="yellow")
            return
        item_id = int(arg.strip())
        with Store.open(self.workspace.db_path) as store:
            changed = store.set_item_status(item_id, status)
        if changed:
            self.console.print(f"Item {item_id} -> {status}.", style="green")
        else:
            self.console.print(f"No item with id {item_id}.", style="yellow")

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
            "Type a question in plain text to ask the library. /exit to quit.",
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
