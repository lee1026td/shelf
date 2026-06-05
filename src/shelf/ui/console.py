"""Shared Rich consoles and small message helpers.

The consoles are created without an explicit ``file`` so Rich resolves ``sys.stdout``
/ ``sys.stderr`` lazily at print time — this keeps output capturable under test
runners (e.g. Typer's ``CliRunner``) that swap the streams.

Markers are intentionally ASCII. Windows consoles using a non-UTF-8 code page (e.g.
cp949) raise ``UnicodeEncodeError`` on glyphs like ``✓``/``✗``, and the reported
stream encoding can't be trusted under redirection — so we don't gamble on Unicode
decoration. Color conveys success/error on capable terminals; the ASCII prefix keeps
the meaning when color is stripped (pipes, capture, dumb terminals).
"""

from __future__ import annotations

from rich.console import Console

from shelf.ui.theme import SHELF_THEME

console = Console(theme=SHELF_THEME, highlight=False)
err_console = Console(theme=SHELF_THEME, stderr=True, highlight=False)


def success(message: str) -> None:
    console.print(message, style="shelf.success")


def info(message: str) -> None:
    console.print(message, style="shelf.info")


def warn(message: str) -> None:
    console.print(f"Warning: {message}", style="shelf.warn")


def error(message: str) -> None:
    """Print a user-facing error to stderr."""
    err_console.print(f"Error: {message}", style="shelf.error")


def notice(message: str) -> None:
    """Print a neutral 'not yet / coming soon' notice to stderr."""
    err_console.print(f"Note: {message}", style="shelf.warn")
