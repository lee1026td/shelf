"""Small cross-cutting helpers (time, hashing, slugs)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a ``Z`` suffix (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    """Hex SHA-256 of ``data`` (used as a snapshot content hash)."""
    return hashlib.sha256(data).hexdigest()


# Reserved device names that must not be used as a bare filename stem on Windows.
_WINDOWS_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{i}" for i in range(1, 10)]
    + [f"lpt{i}" for i in range(1, 10)]
)


def slugify(text: str | None, *, fallback: str = "item", maxlen: int = 80) -> str:
    """Filesystem-safe slug.

    Keeps alphanumerics (Unicode letters/digits included, so Korean titles survive),
    collapses every other run into a single hyphen, and lowercases. Returns
    ``fallback`` if nothing usable remains. Windows reserved device names (con, nul,
    com1, ...) are prefixed so they never become a bare stem.
    """
    chars: list[str] = []
    prev_hyphen = False
    for ch in (text or "").strip().lower():
        if ch.isalnum():
            chars.append(ch)
            prev_hyphen = False
        elif not prev_hyphen:
            chars.append("-")
            prev_hyphen = True
    slug = "".join(chars).strip("-")
    if len(slug) > maxlen:
        slug = slug[:maxlen].rstrip("-")
    slug = slug or fallback
    if slug in _WINDOWS_RESERVED:
        slug = f"_{slug}"
    return slug
