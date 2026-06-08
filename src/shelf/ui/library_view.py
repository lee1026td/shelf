"""Render item/source listings for /inbox, /search, /sources (presentation only)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def _truncate(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1] + "."


def render_items(console: Console, items: list[dict[str, Any]], *, title: str = "items") -> None:
    if not items:
        console.print(f"(no items in {title})", style="dim")
        return
    table = Table(title=f"{title} ({len(items)})", title_style="bold cyan", expand=False)
    table.add_column("ID", justify="right")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Captured")
    table.add_column("URL")
    for item in items:
        table.add_row(
            str(item.get("id", "")),
            _truncate(item.get("title") or item.get("url") or "(untitled)", 48),
            item.get("status") or "",
            (item.get("captured_at") or "")[:10],
            _truncate(item.get("url") or "", 40),
        )
    console.print(table, highlight=False)


def render_sources(console: Console, sources: list[dict[str, Any]]) -> None:
    if not sources:
        console.print("(no sources yet)", style="dim")
        return
    table = Table(title=f"sources ({len(sources)})", title_style="bold cyan", expand=False)
    table.add_column("Status")
    table.add_column("Slug")
    table.add_column("Role")
    table.add_column("Rel", justify="right")
    table.add_column("URL")
    # Group by status for readability.
    for source in sorted(sources, key=lambda s: (s.get("status") or "", s.get("slug") or "")):
        relevance = source.get("relevance")
        rel = f"{relevance:.2f}" if isinstance(relevance, int | float) else ""
        table.add_row(
            source.get("status") or "",
            source.get("slug") or "",
            source.get("role") or "",
            rel,
            _truncate(source.get("url") or "", 48),
        )
    console.print(table, highlight=False)
