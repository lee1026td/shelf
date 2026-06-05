"""The SQLite metadata store.

``Store`` is a thin, dependency-free wrapper over ``sqlite3`` providing schema
initialization, library counts (for ``/status``), and basic CRUD for the entities
needed this milestone (sources, items). Higher-level repositories arrive with the
phases that need them.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shelf.store.migrations import migrate

# Source score axes (plan §6.3) → columns on `sources`.
SCORE_FIELDS: tuple[str, ...] = (
    "relevance",
    "authority",
    "originality",
    "freshness",
    "update_frequency",
    "extractability",
    "uniqueness",
    "noise_risk",
    "watchability",
)

_SCHEMA_SQL = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LibraryCounts:
    """Aggregate counts surfaced by ``/status`` and ``/local``."""

    topics: int = 0
    sources: int = 0
    items: int = 0
    inbox: int = 0  # items with status == 'new'
    reviews_pending: int = 0
    claims: int = 0
    compilations: int = 0
    snapshots: int = 0
    watch_runs: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class Store:
    """Owns a single SQLite connection to a workspace's ``library.sqlite``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    # --- lifecycle ----------------------------------------------------------
    @classmethod
    def open(cls, path: Path | str) -> Store:
        """Open (creating the file if needed) a store at ``path``.

        Pass ``":memory:"`` for an ephemeral in-memory database (tests).
        """
        target = str(path)
        if target != ":memory:":
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target)
        return cls(conn)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def initialize(self, shelf_version: str | None = None) -> int:
        """Create tables (idempotent) and stamp metadata. Returns schema version."""
        self._conn.executescript(_SCHEMA_SQL)
        now = _utc_now_iso()
        self._set_meta("created_at", now, only_if_absent=True)
        if shelf_version is not None:
            self._set_meta("shelf_version", shelf_version)
        version = migrate(self._conn)
        self._conn.commit()
        return version

    @property
    def schema_version(self) -> int:
        from shelf.store.migrations import get_schema_version

        return get_schema_version(self._conn)

    def is_initialized(self) -> bool:
        """True if the core schema exists. Never raises on an empty/blank DB.

        ``Store.open`` creates the file but not the tables, so a present
        ``.shelf/`` marker with a missing/blank ``library.sqlite`` would otherwise
        let table queries raise ``OperationalError``. Callers check this first.
        """
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'topics'"
        ).fetchone()
        return row is not None

    def commit(self) -> None:
        self._conn.commit()

    @contextmanager
    def savepoint(self, name: str = "shelf_sp") -> Iterator[None]:
        """Scope a unit of work so it rolls back cleanly on error.

        Used by batch importers so one failing file leaves no partially-written DB
        rows while other files still succeed.
        """
        self._conn.execute(f"SAVEPOINT {name}")
        try:
            yield
        except Exception:
            self._conn.execute(f"ROLLBACK TO {name}")
            raise
        finally:
            self._conn.execute(f"RELEASE {name}")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            if exc[0] is None:
                self._conn.commit()
        finally:
            self._conn.close()

    # --- metadata -----------------------------------------------------------
    def _set_meta(self, key: str, value: str, only_if_absent: bool = False) -> None:
        if only_if_absent:
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES(?, ?)", (key, value)
            )
        else:
            self._conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    # --- counts -------------------------------------------------------------
    def _count(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        return int(self._conn.execute(sql, params).fetchone()[0])

    def counts(self) -> LibraryCounts:
        return LibraryCounts(
            topics=self._count("SELECT COUNT(*) FROM topics"),
            sources=self._count("SELECT COUNT(*) FROM sources"),
            items=self._count("SELECT COUNT(*) FROM items"),
            inbox=self._count("SELECT COUNT(*) FROM items WHERE status = 'new'"),
            reviews_pending=self._count(
                "SELECT COUNT(*) FROM review_items WHERE status = 'pending'"
            ),
            claims=self._count("SELECT COUNT(*) FROM claims"),
            compilations=self._count("SELECT COUNT(*) FROM compilations"),
            snapshots=self._count("SELECT COUNT(*) FROM snapshots"),
            watch_runs=self._count("SELECT COUNT(*) FROM watch_runs"),
        )

    # --- sources ------------------------------------------------------------
    def add_source(
        self,
        slug: str,
        url: str,
        *,
        name: str | None = None,
        role: str | None = None,
        status: str = "candidate",
        topic_id: int | None = None,
        score: dict[str, float] | None = None,
        extraction_health: str | None = None,
        discovered_from: dict[str, Any] | None = None,
    ) -> int:
        """Insert a source and return its id."""
        now = _utc_now_iso()
        score = score or {}
        columns = [
            "slug",
            "url",
            "name",
            "role",
            "status",
            "topic_id",
            *SCORE_FIELDS,
            "extraction_health",
            "discovered_from",
            "created_at",
            "updated_at",
        ]
        values: list[Any] = [
            slug,
            url,
            name,
            role,
            status,
            topic_id,
            *[score.get(field) for field in SCORE_FIELDS],
            extraction_health,
            json.dumps(discovered_from) if discovered_from is not None else None,
            now,
            now,
        ]
        placeholders = ", ".join("?" for _ in columns)
        cur = self._conn.execute(
            f"INSERT INTO sources({', '.join(columns)}) VALUES({placeholders})", values
        )
        return int(cur.lastrowid)

    def get_source(self, slug: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM sources WHERE slug = ?", (slug,)).fetchone()
        return _row_to_dict(row)

    def list_sources(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM sources ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sources WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        return [d for d in (_row_to_dict(r) for r in rows) if d is not None]

    # --- items --------------------------------------------------------------
    def add_item(
        self,
        *,
        title: str | None = None,
        url: str | None = None,
        source_id: int | None = None,
        published_at: str | None = None,
        summary: str | None = None,
        novelty: float | None = None,
        status: str = "new",
        local_path: str | None = None,
    ) -> int:
        """Insert an item and return its id. New items default to the inbox."""
        now = _utc_now_iso()
        cur = self._conn.execute(
            "INSERT INTO items(source_id, title, url, published_at, captured_at, "
            "summary, novelty, status, local_path, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, title, url, published_at, now, summary, novelty, status,
             local_path, now, now),
        )
        return int(cur.lastrowid)

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _row_to_dict(row)

    # --- snapshots ----------------------------------------------------------
    def add_snapshot(
        self,
        *,
        hash: str,
        fetched_at: str,
        source_id: int | None = None,
        item_id: int | None = None,
        raw_path: str | None = None,
        normalized_path: str | None = None,
        parser_version: str | None = None,
    ) -> int:
        """Insert a snapshot row and return its id."""
        now = _utc_now_iso()
        cur = self._conn.execute(
            "INSERT INTO snapshots(source_id, item_id, hash, raw_path, normalized_path, "
            "fetched_at, parser_version, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, item_id, hash, raw_path, normalized_path, fetched_at,
             parser_version, now),
        )
        return int(cur.lastrowid)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {key: row[key] for key in row.keys()}
