"""Render clip/import outcomes (presentation only)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shelf.ingestion import ClipOutcome, ImportOutcome


def render_clip_outcome(console: Console, outcome: ClipOutcome) -> None:
    if outcome.dry_run:
        console.print(
            f"[dry-run] would clip '{outcome.title}' ({outcome.kind}) from {outcome.url}",
            style="cyan",
            highlight=False,
        )
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="bold")
    table.add_column()
    table.add_row("Title", outcome.title)
    table.add_row("Source", f"{outcome.source_slug} (ephemeral)")
    table.add_row("Item", outcome.item_path or "")
    table.add_row("Snapshot", (outcome.snapshot_hash or "")[:16] + "...")
    console.print(
        Panel(table, title="clipped", border_style="green", expand=False), highlight=False
    )


def render_import_outcome(console: Console, outcome: ImportOutcome) -> None:
    verb = "would import" if outcome.dry_run else "imported"
    if outcome.imported:
        table = Table(
            title=f"{verb} {len(outcome.imported)} file(s) from {outcome.root}",
            title_style="bold green",
            expand=False,
        )
        table.add_column("Kind")
        table.add_column("Title")
        table.add_column("Item path")
        for entry in outcome.imported:
            table.add_row(entry.kind, entry.title, entry.item_path or "(dry-run)")
        console.print(table, highlight=False)
    else:
        console.print(f"No supported files found under {outcome.root}.", style="yellow")

    if outcome.skipped:
        console.print(f"Skipped {len(outcome.skipped)} file(s):", style="yellow", highlight=False)
        for path, reason in outcome.skipped:
            console.print(f"  - {path}  ({reason})", style="bright_black", highlight=False)
