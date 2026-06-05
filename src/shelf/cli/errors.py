"""Uniform CLI error handling.

Commands wrap their body in ``with cli_errors():`` so any :class:`ShelfError`
becomes a clean message + non-zero exit instead of a traceback. ``FeatureNotReady``
gets a softer "coming soon" notice.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

import typer

from shelf.errors import FeatureNotReady, ShelfError
from shelf.ui.console import error, notice


@contextmanager
def cli_errors() -> Iterator[None]:
    try:
        yield
    except FeatureNotReady as exc:
        notice(str(exc))
        raise typer.Exit(code=1) from None
    except ShelfError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from None
    except sqlite3.Error as exc:
        # Backstop: never surface a raw DB traceback to the user.
        error(f"Database error: {exc}")
        raise typer.Exit(code=1) from None
