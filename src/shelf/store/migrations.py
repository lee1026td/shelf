"""Schema versioning for the SQLite store.

This milestone ships schema version 1 created from ``schema.sql`` in one shot. When
the schema changes, bump :data:`SCHEMA_VERSION`, add an upgrade step in
:func:`migrate`, and update ``schema.sql`` + ``SCHEMA.md`` together.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the recorded schema version, or 0 if uninitialized."""
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def migrate(conn: sqlite3.Connection) -> int:
    """Upgrade ``conn`` to :data:`SCHEMA_VERSION`. Returns the resulting version.

    Currently a no-op beyond stamping the version, since version 1 is created
    wholesale from ``schema.sql``. Future versions add ``if current < N`` blocks.
    """
    current = get_schema_version(conn)
    if current >= SCHEMA_VERSION:
        return current
    # (no incremental upgrades yet)
    set_schema_version(conn, SCHEMA_VERSION)
    return SCHEMA_VERSION
