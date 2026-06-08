"""The REPL loop and per-line dispatch.

Design notes:
- ``ReplSession.handle(line)`` is the testable unit: feed it a line, it dispatches
  and prints. ``run_repl`` is the thin I/O loop around it.
- Output uses *literal* Rich styles (not theme names) so a bare ``Console`` passed
  in tests never hits a MissingStyle error. ``render_status`` manages its own theme.
- All emitted text is ASCII (the cp949 console constraint - see ui/console.py).
"""

from __future__ import annotations

import os
import sys
import unicodedata
from collections import namedtuple
from collections.abc import Callable
from urllib.parse import urlsplit

from rich.console import Console
from rich.table import Table

from shelf.config import Config, load_config
from shelf.discovery import compile_topic, explore_topic
from shelf.errors import ShelfError
from shelf.ingestion import Fetcher, clip_url, import_path
from shelf.llm import ModelGateway, ask_library, summarize_item
from shelf.llm.client import ChatClient
from shelf.llm.gateway import API_KEY_ENV, LOCAL_HOSTS
from shelf.repl.commands import (
    COMMANDS_BY_NAME,
    EXIT_ALIASES,
    HELP_ALIASES,
    SLASH_COMMANDS,
)
from shelf.services import (
    enable_remote_llm,
    enable_remote_search,
    gather_status,
    set_model,
    track_topic,
)
from shelf.store import Store
from shelf.ui.console import console as default_console
from shelf.ui.ingest_view import render_clip_outcome, render_import_outcome
from shelf.ui.library_view import render_items, render_sources
from shelf.ui.model_view import render_model_list, render_models
from shelf.ui.status_view import render_status, status_bar_line
from shelf.workspace import Workspace

PROMPT = "shelf> "

# Provider menu for the `/model` picker. ``base_url=None`` means "ask the user"
# (custom endpoint) unless ``coming_soon`` is set. Ollama/custom/OpenAI all speak
# the OpenAI-compatible wire protocol the gateway already implements; Anthropic is
# native (/v1/messages) and needs a dedicated adapter, so it's parked for now.
_Provider = namedtuple("_Provider", "label note provider base_url coming_soon")
_PROVIDERS: tuple[_Provider, ...] = (
    _Provider("Ollama", "local, no API key", "ollama", "http://localhost:11434/v1", False),
    _Provider(
        "Custom OpenAI-compatible endpoint",
        "LM Studio / vLLM / llama.cpp ...",
        "openai_compatible",
        None,
        False,
    ),
    _Provider(
        "OpenAI", "remote, needs $SHELF_API_KEY", "openai", "https://api.openai.com/v1", False
    ),
    _Provider(
        "Anthropic (Claude)", "coming soon - not OpenAI-compatible", "anthropic", None, True
    ),
)

# Roles the picker can configure, with a short hint. ``planner`` is the chat model.
_ROLES: tuple[tuple[str, str], ...] = (
    ("planner", "planner (chat)"),
    ("embeddings", "embeddings"),
)

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


def _extract_option(arg: str, name: str) -> tuple[str, str | None]:
    """Pull a ``--name value`` option out of a free-text arg; return (rest, value)."""
    tokens = arg.split()
    value: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] == name and i + 1 < len(tokens):
            value = tokens[i + 1]
            i += 2
            continue
        rest.append(tokens[i])
        i += 1
    return " ".join(rest), value


def _clamp_steps(value: str | None, *, default: int = 12, lo: int = 1, hi: int = 40) -> int:
    """Parse/clamp a ``--steps`` value into a sane agent step budget."""
    if value and value.isdigit():
        return max(lo, min(hi, int(value)))
    return default


class ReplSession:
    """Holds REPL state and dispatches one input line at a time."""

    def __init__(
        self,
        workspace: Workspace,
        console: Console | None = None,
        fetcher: Fetcher | None = None,
        gateway: ModelGateway | None = None,
        client: ChatClient | None = None,
        asker: Callable[[str], str] | None = None,
        event_sink: Callable[[str, str], None] | None = None,
    ) -> None:
        self.workspace = workspace
        self.console = console or default_console
        self.fetcher = fetcher  # injectable for tests; None -> default HttpFetcher
        self._gateway = gateway  # injectable for tests; None -> built from config
        self._client = client  # injectable client; survives gateway rebuilds (picker)
        # ``asker`` reads one interactive line for a prompt; None => non-interactive
        # (piped/tests), which disables the `/model` picker in favor of the table view.
        self._asker = asker
        # ``event_sink`` receives agent-loop trace events; the TUI sets this to render
        # tool-call cards. None => events print to the console (the line REPL).
        self._event_sink = event_sink
        self.running = True

    def _get_gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = ModelGateway(
                load_config(self.workspace.config_path), client=self._client
            )
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
            "explore": self._handle_explore,
            "track": self._handle_track,
            "compile": self._handle_compile,
        }

    def _handle_text(self, text: str) -> None:
        # Free text is a chat: conversational, grounded in the library when relevant
        # (Phase 2). Discovery/web routing arrives in Phase 3.
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
        if not answer.strip():
            self.console.print(
                "(the model returned an empty answer - try a larger model "
                "or a non-thinking one)",
                style="yellow",
            )
            return
        # markup=False: LLM text often contains '[' which Rich would mis-parse.
        self.console.print(answer, highlight=False, markup=False)

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
        self.console.print(f"Item {item_id}: {summary}", style="green", highlight=False, markup=False)

    def _event_printer(self) -> Callable[[str, str], None]:
        """A live-trace callback for the agent loop, styled by event kind.

        Returns the injected ``event_sink`` (the TUI's card renderer) when present,
        else a console printer for the line REPL.
        """
        if self._event_sink is not None:
            return self._event_sink
        styles = {"retry": "yellow", "error": "red", "final": "green", "note": "dim"}

        def _on_event(kind: str, message: str) -> None:
            self.console.print(f"  - {message}", style=styles.get(kind, "dim"), highlight=False)

        return _on_event

    def _handle_explore(self, arg: str) -> None:
        rest, steps_value = _extract_option(arg, "--steps")
        topic = rest.strip()
        if not topic:
            self.console.print("Usage: /explore <topic> [--steps N]", style="yellow")
            return
        config = load_config(self.workspace.config_path)
        if config.planner_model == "none":
            self.console.print("No model configured. Run /model to pick one first.", style="yellow")
            return
        if not config.privacy.remote_search:
            config = self._maybe_enable_web_search(config)
        self.console.print(f"Exploring: {topic}", style="bold cyan", highlight=False)
        try:
            gateway = self._get_gateway()
            with Store.open(self.workspace.db_path) as store:
                outcome = explore_topic(
                    self.workspace,
                    gateway,
                    topic,
                    store=store,
                    fetcher=self.fetcher,
                    config=config,
                    max_steps=_clamp_steps(steps_value),
                    on_event=self._event_printer(),
                )
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        if outcome.candidates:
            render_sources(self.console, outcome.candidates)
        self.console.print(outcome.brief or "(no brief)", highlight=False, markup=False)
        self.console.print(
            f"(stopped: {outcome.stopped_reason}; {outcome.steps} tool step(s); "
            f"{len(outcome.candidates)} source(s) proposed -> review queue)",
            style="dim",
        )

    def _handle_track(self, arg: str) -> None:
        rest, frequency = _extract_option(arg, "--frequency")
        topic = rest.strip()
        if not topic:
            self.console.print(
                "Usage: /track <topic> [--frequency weekly|daily|monthly]", style="yellow"
            )
            return
        frequency = frequency or "weekly"
        track_topic(self.workspace, topic, frequency=frequency)
        self.console.print(
            f"Topic '{topic}' is now tracked ({frequency}). Its candidate sources stay in "
            "the review queue until approved; periodic collection arrives with the watcher "
            "(Phase 4).",
            style="green",
            highlight=False,
        )

    def _handle_compile(self, arg: str) -> None:
        rest, kind = _extract_option(arg, "--kind")
        rest, steps_value = _extract_option(rest, "--steps")
        topic = rest.strip()
        if not topic:
            self.console.print(
                "Usage: /compile <topic> [--kind brief|landscape|faq|timeline] [--steps N]",
                style="yellow",
            )
            return
        config = load_config(self.workspace.config_path)
        if config.planner_model == "none":
            self.console.print("No model configured. Run /model to pick one first.", style="yellow")
            return
        kind = kind or "brief"
        self.console.print(f"Compiling {kind}: {topic}", style="bold cyan", highlight=False)
        try:
            gateway = self._get_gateway()
            with Store.open(self.workspace.db_path) as store:
                outcome = compile_topic(
                    self.workspace,
                    gateway,
                    topic,
                    store=store,
                    kind=kind,
                    fetcher=self.fetcher,
                    config=config,
                    max_steps=_clamp_steps(steps_value, default=10),
                    on_event=self._event_printer(),
                )
        except ShelfError as exc:
            self.console.print(f"Error: {exc}", style="red")
            return
        self.console.print(outcome.document or "(empty)", highlight=False, markup=False)
        if outcome.output_path:
            self.console.print(
                f"(saved to {outcome.output_path}; stopped: {outcome.stopped_reason})", style="dim"
            )
        else:
            self.console.print(f"(not saved; stopped: {outcome.stopped_reason})", style="yellow")

    def _maybe_enable_web_search(self, config: Config) -> Config:
        """Web search is off: offer to enable it (interactive), else note library-only.

        Mirrors the model picker's egress confirm. On a yes, persist
        ``privacy.remote_search`` and return the reloaded config so this run uses it.
        """
        if self._asker is None:  # non-interactive: don't silently flip egress
            self.console.print(
                "Note: web search is off (privacy.remote_search) - exploring your local "
                "library only. Enable it in .shelf/config.yaml to search the web.",
                style="yellow",
                highlight=False,
            )
            return config
        answer = (
            self._ask(
                "Web search is off. Enable it for this run? It sends your query to a "
                "web search engine. [y/N]: "
            )
            or ""
        ).strip().lower()
        if answer not in ("y", "yes"):
            self.console.print("Exploring your local library only.", style="dim")
            return config
        enable_remote_search(self.workspace)
        self.console.print(
            "Web search enabled (privacy.remote_search) - it stays on until you disable "
            "it in .shelf/config.yaml.",
            style="green",
            highlight=False,
        )
        return load_config(self.workspace.config_path)

    def _handle_model(self, arg: str = "") -> None:
        tokens = arg.split()
        sub = tokens[0].lower() if tokens else ""

        if not sub:  # /model -> interactive picker on a TTY, else the profile table
            if self._asker is not None:
                self._run_model_picker()  # asks which role, then provider -> model
            else:
                self._show_models()
            return

        if sub == "show":  # /model show -> always the profile table + probe
            self._show_models()
            return

        if sub in {role for role, _label in _ROLES}:  # /model planner | /model embeddings
            if self._asker is not None:
                self._run_model_picker(sub)  # picker straight into that role
            else:
                self._show_models()
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

    def _show_models(self) -> None:
        config = load_config(self.workspace.config_path)
        render_models(self.console, config, self._get_gateway().probe("planner"))

    def _ask(self, prompt: str) -> str | None:
        """Read one interactive line; None if non-interactive or the user aborts."""
        if self._asker is None:
            return None
        try:
            return self._asker(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

    # --- /model picker (interactive) ---------------------------------------
    def _run_model_picker(self, role: str | None = None) -> None:
        """Guided role -> provider -> model flow. See ``_PROVIDERS`` / ``_ROLES``."""
        # Show what's already configured so the user sees the current connection.
        render_models(self.console, load_config(self.workspace.config_path))

        if role is None:  # bare /model: choose which role to configure
            self.console.print("Configure which role?", style="bold cyan")
            for i, (_role, label) in enumerate(_ROLES, 1):
                self.console.print(f"  {i}. {label}", highlight=False)
            raw = self._ask(f"Choice [1-{len(_ROLES)}]: ")
            if raw is None or not raw.strip():
                self.console.print("(cancelled)", style="dim")
                return
            if not raw.strip().isdigit() or not 1 <= int(raw) <= len(_ROLES):
                self.console.print("Invalid choice.", style="yellow")
                return
            role = _ROLES[int(raw) - 1][0]

        self.console.print(f"Select a model provider for {role}:", style="bold cyan")
        for i, provider in enumerate(_PROVIDERS, 1):
            self.console.print(f"  {i}. {provider.label}  ({provider.note})", highlight=False)
        raw = self._ask(f"Choice [1-{len(_PROVIDERS)}]: ")
        if raw is None or not raw.strip():
            self.console.print("(cancelled)", style="dim")
            return
        if not raw.strip().isdigit() or not 1 <= int(raw) <= len(_PROVIDERS):
            self.console.print("Invalid choice.", style="yellow")
            return
        provider = _PROVIDERS[int(raw) - 1]

        if provider.coming_soon:
            self.console.print(
                f"{provider.label} isn't available yet: it isn't OpenAI-compatible "
                "(native /v1/messages API), so it needs a dedicated adapter - planned.",
                style="yellow",
                highlight=False,
            )
            return

        self._configure_provider(role, provider)

    def _configure_provider(self, role: str, provider: _Provider) -> None:
        """Resolve endpoint -> verify connectivity -> pick a model.

        For a custom endpoint, a failed connection loops back to re-enter the URL
        (a wrong URL is the likely cause) instead of pretending success. Fixed
        endpoints (Ollama/OpenAI) report the failure and stop without a model.
        """
        custom = provider.base_url is None
        while True:
            if custom:
                entered = self._ask("Endpoint base URL (e.g. http://localhost:1234/v1): ")
                base_url = (entered or "").strip()
                if not base_url:
                    self.console.print("(cancelled)", style="dim")
                    return
            else:
                base_url = provider.base_url

            if not self._confirm_egress(role, base_url, provider):
                return  # remote declined: endpoint saved, calls blocked, nothing more to do

            set_model(self.workspace, role, base_url=base_url, provider=provider.provider)
            self._gateway = None  # rebuild against the new endpoint (+ egress flag)

            try:
                models = self._get_gateway().list_models(role)
            except ShelfError as exc:
                self.console.print(
                    f"Could not connect to {base_url}: {exc}", style="red", highlight=False
                )
                if custom:
                    self.console.print(
                        "Enter a different endpoint URL (blank to cancel).", style="dim"
                    )
                    continue  # not connected -> re-ask the URL, don't fake a selection
                self.console.print(
                    f"Left the {role} endpoint set but selected no model.", style="dim"
                )
                return

            self._choose_model(role, base_url, models)
            return

    def _confirm_egress(self, role: str, base_url: str, provider: _Provider) -> bool:
        """Gate a remote endpoint. Returns False if the user declines (caller stops)."""
        host = (urlsplit(base_url).hostname or "").lower()
        if host in LOCAL_HOSTS:
            return True
        if not load_config(self.workspace.config_path).privacy.remote_llm:
            self.console.print(
                f"This sends library content to {host} (off-machine).",
                style="yellow",
                highlight=False,
            )
            answer = (self._ask("Enable remote LLM egress? [y/N]: ") or "").strip().lower()
            if answer not in ("y", "yes"):
                set_model(self.workspace, role, base_url=base_url, provider=provider.provider)
                self._gateway = None
                self.console.print(
                    f"Saved {provider.label} endpoint, but remote egress stays OFF - "
                    "calls are blocked until you enable privacy.remote_llm.",
                    style="yellow",
                    highlight=False,
                )
                return False
            enable_remote_llm(self.workspace)
            self.console.print("Remote LLM egress enabled.", style="green")
        if not os.environ.get(API_KEY_ENV):
            self.console.print(
                f"Note: set the {API_KEY_ENV} env var with your API key before querying.",
                style="dim",
                highlight=False,
            )
        return True

    def _choose_model(self, role: str, base_url: str, models: list[str]) -> None:
        """Pick a model from a reachable endpoint and persist it."""
        if models:
            self.console.print(f"Models at {base_url}:", style="bold cyan", highlight=False)
            for i, model in enumerate(models, 1):
                self.console.print(f"  {i}. {model}", highlight=False)
            raw = (self._ask(f"Pick a model [1-{len(models)}] or type a name: ") or "").strip()
            if not raw:
                self.console.print("(no model selected)", style="dim")
                return
            chosen = models[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(models) else raw
        else:
            # Reachable, but the endpoint exposes no /models list - allow a manual id.
            self.console.print(
                f"{base_url} is reachable but lists no models.", style="yellow", highlight=False
            )
            entered = self._ask("Enter a model id (blank to skip): ")
            chosen = (entered or "").strip()
            if not chosen:
                self.console.print("(no model selected)", style="dim")
                return

        profile = set_model(self.workspace, role, model=chosen)
        self._gateway = None
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
    read = reader or _make_reader()
    # Only offer the interactive picker when we own a real TTY (reader not injected).
    asker = _make_asker() if reader is None else None
    session = ReplSession(workspace, console=out, asker=asker)

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


def _make_asker() -> Callable[[str], str] | None:
    """Build a prompt-with-message reader for the `/model` picker, or None.

    Returns None off a TTY: interactive multi-step prompts don't make sense when
    stdin is piped (the sub-prompt would swallow the next queued line), so the
    picker falls back to the non-interactive profile table in that case.
    """
    is_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    if not is_tty:
        return None
    try:
        from prompt_toolkit import PromptSession

        ptk: PromptSession = PromptSession()
        return lambda prompt: ptk.prompt(prompt)
    except Exception:
        return lambda prompt: input(prompt)
