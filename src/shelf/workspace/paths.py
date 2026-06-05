"""Resolve and discover shelf workspaces.

A workspace is any directory containing a ``.shelf/`` marker. Discovery order:
``--workspace`` (explicit) → ``$SHELF_HOME`` → walk up from the current directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from shelf.errors import WorkspaceNotFound
from shelf.workspace.layout import DOT_SHELF

SHELF_HOME_ENV = "SHELF_HOME"


@dataclass(frozen=True)
class Workspace:
    """Typed view over a workspace's directory layout.

    Construction does not touch the filesystem; use :meth:`exists` to check whether
    the directory is actually an initialized workspace.
    """

    root: Path

    # --- construction -------------------------------------------------------
    @classmethod
    def at(cls, path: Path | str) -> Workspace:
        """Wrap ``path`` as a workspace root (expanded + absolute, no validation)."""
        return cls(Path(path).expanduser().resolve())

    # --- marker / state -----------------------------------------------------
    @property
    def dot_shelf(self) -> Path:
        return self.root / DOT_SHELF

    def exists(self) -> bool:
        """True if this looks like an initialized workspace (has ``.shelf/``)."""
        return self.dot_shelf.is_dir()

    # --- machine state under .shelf/ ---------------------------------------
    @property
    def config_path(self) -> Path:
        return self.dot_shelf / "config.yaml"

    @property
    def db_path(self) -> Path:
        return self.dot_shelf / "library.sqlite"

    @property
    def jobs_db_path(self) -> Path:
        return self.dot_shelf / "jobs.sqlite"

    @property
    def index_dir(self) -> Path:
        return self.dot_shelf / "index"

    @property
    def snapshots_dir(self) -> Path:
        return self.dot_shelf / "snapshots"

    @property
    def normalized_dir(self) -> Path:
        return self.dot_shelf / "normalized"

    @property
    def cache_dir(self) -> Path:
        return self.dot_shelf / "cache"

    # --- canonical library directories -------------------------------------
    @property
    def dashboard(self) -> Path:
        return self.root / "Dashboard.md"

    @property
    def inbox_dir(self) -> Path:
        return self.root / "Inbox"

    @property
    def topics_dir(self) -> Path:
        return self.root / "Topics"

    @property
    def sources_dir(self) -> Path:
        return self.root / "Sources"

    @property
    def items_dir(self) -> Path:
        return self.root / "Items"

    @property
    def wiki_dir(self) -> Path:
        return self.root / "Wiki"

    @property
    def digests_dir(self) -> Path:
        return self.root / "Digests"

    @property
    def compilations_dir(self) -> Path:
        return self.root / "Compilations"

    @property
    def review_dir(self) -> Path:
        return self.root / "Review"

    @property
    def review_pending_dir(self) -> Path:
        return self.review_dir / "pending"

    @property
    def ledgers_dir(self) -> Path:
        return self.root / "Ledgers"

    @property
    def source_ledger(self) -> Path:
        return self.ledgers_dir / "source_ledger.jsonl"

    @property
    def claim_ledger(self) -> Path:
        return self.ledgers_dir / "claim_ledger.jsonl"

    # --- discovery ----------------------------------------------------------
    @classmethod
    def discover(
        cls,
        start: Path | str | None = None,
        env: dict[str, str] | None = None,
    ) -> Workspace | None:
        """Find an initialized workspace, or return ``None``.

        Order: ``$SHELF_HOME`` (if it points at an initialized workspace), then a
        walk upward from ``start`` (default: current working directory).
        """
        environ = os.environ if env is None else env
        home = environ.get(SHELF_HOME_ENV)
        if home:
            candidate = cls.at(home)
            if candidate.exists():
                return candidate

        current = Path(start).expanduser().resolve() if start else Path.cwd().resolve()
        for directory in (current, *current.parents):
            if (directory / DOT_SHELF).is_dir():
                return cls(directory)
        return None


def resolve_workspace(
    explicit: Path | str | None = None,
    start: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> Workspace:
    """Resolve the workspace to operate on, raising :class:`WorkspaceNotFound`.

    If ``explicit`` is given it must already be initialized. Otherwise discovery
    runs (``$SHELF_HOME`` then upward walk from ``start``/cwd).
    """
    if explicit is not None:
        ws = Workspace.at(explicit)
        if not ws.exists():
            raise WorkspaceNotFound(
                f"No shelf workspace at {ws.root} (no {DOT_SHELF}/ directory). "
                "Run `shelf init` there first."
            )
        return ws

    found = Workspace.discover(start=start, env=env)
    if found is None:
        raise WorkspaceNotFound()
    return found
