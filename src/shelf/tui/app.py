"""The Textual TUI (Phase 5, first slice).

A thin full-screen shell over the existing :class:`~shelf.repl.session.ReplSession`:
a scrollable transcript on top, a bottom-docked input bordered by horizontal rules
with a ``>`` prompt, and a slash-command dropdown. It reuses every Rich renderer
(status/sources/models tables, the chat reply, the cited brief) by handing the session
a Console that writes into the transcript, and renders the agent loop's live trace as
tool-call cards via the session's ``event_sink``. Blocking commands run in a thread
worker so the UI stays responsive and scrollable.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from shelf.repl.commands import SLASH_COMMANDS
from shelf.repl.session import ReplSession

_EVENT_STYLES = {"retry": "yellow", "error": "red", "final": "green", "note": "dim"}


class _LogSink:
    """File-like sink: a Rich Console writes ANSI here; whole lines are forwarded to the
    transcript (parsed back into styled text). Always written from the worker thread, so
    it marshals to the UI thread via ``call_from_thread``."""

    def __init__(self, app: ShelfApp) -> None:
        self._app = app
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._app.call_from_thread(self._app.write_renderable, Text.from_ansi(line))
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self._app.call_from_thread(self._app.write_renderable, Text.from_ansi(self._buf))
            self._buf = ""


class ShelfApp(App):
    """The shelf research TUI."""

    CSS = """
    Screen { layout: vertical; }
    #log { height: 1fr; border: round $surface; padding: 0 1; scrollbar-gutter: stable; }
    #palette {
        display: none;
        height: auto;
        max-height: 10;
        border: round $accent;
        background: $panel;
    }
    #inputbar {
        height: auto;
        border-top: heavy $accent;
        border-bottom: heavy $accent;
        padding: 0 1;
    }
    #prompt { width: 2; color: $accent; content-align: left middle; }
    #entry { border: none; padding: 0; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("tab", "complete", "Complete", priority=True),
    ]

    def __init__(self, workspace, *, gateway=None, fetcher=None, client=None) -> None:
        super().__init__()
        self._workspace = workspace
        self._sink = _LogSink(self)
        self._console = Console(
            file=self._sink,
            force_terminal=True,
            color_system="standard",
            width=100,
            highlight=False,
            soft_wrap=False,
        )
        self._session = ReplSession(
            workspace,
            console=self._console,
            gateway=gateway,
            fetcher=fetcher,
            client=client,
            event_sink=self._event_sink,
        )
        self._matches: list = []

    # --- layout -------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield RichLog(id="log", highlight=False, markup=False, wrap=True)
        yield OptionList(id="palette")
        with Horizontal(id="inputbar"):
            yield Static(">", id="prompt")
            yield Input(id="entry", placeholder="ask, or type / for commands")

    def on_mount(self) -> None:
        self._log = self.query_one("#log", RichLog)
        self._palette = self.query_one("#palette", OptionList)
        self._input = self.query_one("#entry", Input)
        self._palette.display = False
        self._console.width = max(40, self.size.width - 4)
        self._input.focus()
        self._log.write(Text(f"shelf - {self._workspace.root.name}", style="bold cyan"))
        self._log.write(
            Text("Type / for commands, or ask anything. Ctrl+Q to quit.", style="dim")
        )

    def on_resize(self) -> None:
        self._console.width = max(40, self.size.width - 4)

    # --- output -------------------------------------------------------------
    def write_renderable(self, renderable) -> None:
        """Append a Rich renderable to the transcript (runs on the UI thread)."""
        self._log.write(renderable)

    def _event_sink(self, kind: str, message: str) -> None:
        """Render an agent-loop trace event (called from the worker thread)."""
        if kind == "step":
            renderable = Panel(message, title="tool", border_style="cyan", padding=(0, 1))
        else:
            renderable = Text(f"  {message}", style=_EVENT_STYLES.get(kind, "dim"))
        self.call_from_thread(self.write_renderable, renderable)

    # --- slash dropdown -----------------------------------------------------
    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        if value.startswith("/") and " " not in value:
            self._show_palette(value[1:].lower())
        else:
            self._hide_palette()

    def _show_palette(self, prefix: str) -> None:
        self._matches = [c for c in SLASH_COMMANDS if c.name.startswith(prefix)]
        self._palette.clear_options()
        if not self._matches:
            self._palette.display = False
            return
        self._palette.add_options(
            [
                Option(
                    f"/{c.name}   ({'now' if c.available else f'Phase {c.phase}'})  {c.summary}",
                    id=c.name,
                )
                for c in self._matches
            ]
        )
        self._palette.display = True

    def _hide_palette(self) -> None:
        self._palette.display = False
        self._matches = []

    def action_complete(self) -> None:
        if self._matches:
            self._input.value = f"/{self._matches[0].name} "
            self._input.cursor_position = len(self._input.value)
            self._hide_palette()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        name = event.option.id
        if name:
            self._input.value = f"/{name} "
            self._input.cursor_position = len(self._input.value)
        self._hide_palette()
        self._input.focus()

    # --- input / dispatch ---------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value
        self._input.value = ""
        self._hide_palette()
        if not line.strip():
            return
        self.write_renderable(Text(f"you> {line}", style="bold"))
        self._run_line(line)

    @work(thread=True, exclusive=True)
    def _run_line(self, line: str) -> None:
        try:
            self._session.handle(line)
        except Exception as exc:  # keep the TUI alive on any handler surprise
            self.call_from_thread(self.write_renderable, Text(f"Error: {exc}", style="red"))
        finally:
            self._sink.flush()
        if not self._session.running:
            self.call_from_thread(self.exit)


def launch_tui(workspace, *, gateway=None, fetcher=None, client=None) -> None:
    """Entry point used by ``shelf`` / ``shelf chat`` / ``shelf tui``."""
    ShelfApp(workspace, gateway=gateway, fetcher=fetcher, client=client).run()
