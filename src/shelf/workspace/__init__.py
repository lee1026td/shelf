"""Local workspace: on-disk layout, path resolution, and initialization."""

from __future__ import annotations

from shelf.workspace.initializer import initialize_workspace
from shelf.workspace.layout import DOT_SHELF, LIBRARY_DIRS, SHELF_DIRS
from shelf.workspace.paths import Workspace, resolve_workspace

__all__ = [
    "DOT_SHELF",
    "LIBRARY_DIRS",
    "SHELF_DIRS",
    "Workspace",
    "initialize_workspace",
    "resolve_workspace",
]
