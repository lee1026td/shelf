"""Create a new shelf workspace on disk (the ``shelf init`` implementation)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shelf import __version__
from shelf.config import default_config, save_config
from shelf.errors import WorkspaceExists
from shelf.store import Store
from shelf.workspace.layout import (
    ALL_DIRS,
    DASHBOARD_FILE,
    LEDGER_FILES,
    REVIEW_QUEUE_FILE,
    dashboard_markdown,
    review_queue_markdown,
)
from shelf.workspace.paths import Workspace


def initialize_workspace(
    root: Path | str,
    name: str | None = None,
    force: bool = False,
) -> Workspace:
    """Create the full library layout, config, and databases at ``root``.

    Idempotent for directories and the schema; refuses to clobber an existing
    workspace unless ``force`` is set. Returns the initialized :class:`Workspace`.
    """
    ws = Workspace.at(root)
    if ws.exists() and not force:
        raise WorkspaceExists(str(ws.root))

    # 1. Directories (library tree + .shelf machine state).
    ws.root.mkdir(parents=True, exist_ok=True)
    for relative in ALL_DIRS:
        (ws.root / relative).mkdir(parents=True, exist_ok=True)

    # 2. Configuration (default = local-only, remote off).
    resolved_name = name or ws.root.name
    config = default_config(ws.root, resolved_name)
    save_config(config, ws.config_path)

    # 3. SQLite metadata store + an empty jobs database.
    with Store.open(ws.db_path) as store:
        store.initialize(shelf_version=__version__)
    sqlite3.connect(str(ws.jobs_db_path)).close()

    # 4. Seed human-facing files (only create when missing, even under --force,
    #    so a re-init never destroys edited content).
    created_at = config.workspace.created_at
    _write_if_absent(
        ws.root / DASHBOARD_FILE,
        dashboard_markdown(resolved_name, str(ws.root), created_at),
    )
    _write_if_absent(ws.root / REVIEW_QUEUE_FILE, review_queue_markdown())
    for ledger in LEDGER_FILES:
        _write_if_absent(ws.root / ledger, "")

    return ws


def _write_if_absent(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
