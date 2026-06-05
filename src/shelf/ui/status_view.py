"""Render the ``/status`` output: the canonical status bar + a details panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shelf.store import LibraryCounts
from shelf.ui.theme import SHELF_THEME


@dataclass(frozen=True)
class StatusReport:
    """Everything ``/status`` needs to render, assembled by the command layer."""

    workspace_root: Path
    workspace_name: str
    model: str
    remote_enabled: bool
    notion_sync_mode: str
    schema_version: int
    counts: LibraryCounts

    @property
    def remote_label(self) -> str:
        return "on" if self.remote_enabled else "off"


def _abbrev_home(path: Path) -> str:
    """Show ``~/...`` when ``path`` is under the home directory, else the full path."""
    try:
        home = Path.home()
    except RuntimeError:  # pragma: no cover - home undefined
        return str(path)
    try:
        rel = path.relative_to(home)
    except ValueError:
        return str(path)
    return "~/" + rel.as_posix() if rel.parts else "~"


def status_bar_line(report: StatusReport) -> str:
    """The one-line status bar (plan §4.2). Pure string for stable assertions.

    Example::

        [Shelf: ~/ResearchLibrary] [model: qwen3:32b] [remote: off] [sources: 42] [inbox: 18] [review: 5]
    """
    counts = report.counts
    return (
        f"[Shelf: {_abbrev_home(report.workspace_root)}] "
        f"[model: {report.model}] "
        f"[remote: {report.remote_label}] "
        f"[sources: {counts.sources}] "
        f"[inbox: {counts.inbox}] "
        f"[review: {counts.reviews_pending}]"
    )


def render_status(console: Console, report: StatusReport) -> None:
    """Print the details panel followed by the status bar line.

    The shelf theme is pushed for the duration so named styles resolve even when
    the caller passes a bare ``Console``.
    """
    counts = report.counts

    with console.use_theme(SHELF_THEME):
        table = Table.grid(padding=(0, 2))
        table.add_column(style="shelf.key", justify="right")
        table.add_column(style="shelf.value")
        table.add_row("Workspace", f"{report.workspace_name}")
        table.add_row("Root", _abbrev_home(report.workspace_root))
        table.add_row("Model (planner)", report.model)
        table.add_row(
            "Remote",
            f"{report.remote_label}"
            + (
                f"  -  notion: {report.notion_sync_mode}"
                if report.notion_sync_mode != "off"
                else ""
            ),
        )
        table.add_row("Schema", f"v{report.schema_version}")
        table.add_row("", "")
        table.add_row("Topics", str(counts.topics))
        table.add_row("Sources", str(counts.sources))
        table.add_row("Items", str(counts.items))
        table.add_row("Inbox (new)", str(counts.inbox))
        table.add_row("Pending review", str(counts.reviews_pending))
        table.add_row("Compilations", str(counts.compilations))

        console.print(
            Panel(table, title="shelf status", border_style="shelf.status", expand=False)
        )
        # The canonical status bar — soft_wrap keeps it on one line regardless of
        # the console width (important under non-terminal capture).
        console.print(
            status_bar_line(report),
            style="shelf.status",
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
