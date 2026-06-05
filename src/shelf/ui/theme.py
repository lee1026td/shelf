"""Rich theme / named styles for shelf."""

from __future__ import annotations

from rich.theme import Theme

SHELF_THEME = Theme(
    {
        "shelf.success": "bold green",
        "shelf.error": "bold red",
        "shelf.warn": "yellow",
        "shelf.info": "cyan",
        "shelf.dim": "dim",
        "shelf.status": "bold cyan",
        "shelf.key": "bold",
        "shelf.value": "white",
        "shelf.muted": "bright_black",
    }
)
