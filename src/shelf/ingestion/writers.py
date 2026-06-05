"""Filesystem writers for ingested content: Item markdown, snapshots, ledgers.

All paths returned are **relative to the workspace root** (POSIX style) so they are
portable and match what the SQLite store records.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from shelf.ingestion.base import ParsedDocument
from shelf.ingestion.parsers import KIND_EXTENSION
from shelf.util import slugify
from shelf.workspace import Workspace

SUMMARY_MAXLEN = 280


def summarize(text: str | None) -> str:
    """A short one-line summary: the first non-empty paragraph, truncated."""
    if not text:
        return ""
    for block in text.split("\n\n"):
        line = " ".join(block.split()).strip()
        if line:
            return line[:SUMMARY_MAXLEN] + ("..." if len(line) > SUMMARY_MAXLEN else "")
    return ""


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    for n in range(2, 1000):
        candidate = parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Too many collisions for {path}")  # pragma: no cover


def write_item(
    workspace: Workspace,
    parsed: ParsedDocument,
    *,
    url: str,
    captured_at: str,
    kind: str,
    source_slug: str | None = None,
) -> str:
    """Write an ``Items/YYYY/MM/<slug>.md`` file. Returns the workspace-relative path."""
    slug = slugify(parsed.title or url)
    folder = workspace.items_dir / captured_at[:4] / captured_at[5:7]
    folder.mkdir(parents=True, exist_ok=True)
    path = _unique_path(folder / f"{slug}.md")

    frontmatter: dict[str, object] = {
        "title": parsed.title or slug,
        "url": url,
        "captured_at": captured_at,
        "kind": kind,
    }
    if source_slug:
        frontmatter["source"] = source_slug
    summary = summarize(parsed.text)
    if summary:
        frontmatter["summary"] = summary

    body = (parsed.markdown or parsed.text or "").strip()
    document = (
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n\n"
        + body
        + "\n"
    )
    path.write_text(document, encoding="utf-8")
    return path.relative_to(workspace.root).as_posix()


def write_snapshot(
    workspace: Workspace,
    raw: bytes,
    normalized_text: str,
    digest: str,
    kind: str,
) -> tuple[str, str]:
    """Persist raw + normalized snapshot files keyed by content hash.

    Returns ``(raw_rel, normalized_rel)`` workspace-relative paths.
    """
    ext = KIND_EXTENSION.get(kind, "bin")
    raw_path = workspace.snapshots_dir / f"{digest}.{ext}"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(raw)

    # Key the normalized file by kind too: the same raw bytes parsed under a
    # different kind produce different normalized text, so they must not share a file.
    norm_path = workspace.normalized_dir / f"{digest}.{kind}.md"
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    if not norm_path.exists():
        norm_path.write_text(normalized_text or "", encoding="utf-8")

    return (
        raw_path.relative_to(workspace.root).as_posix(),
        norm_path.relative_to(workspace.root).as_posix(),
    )


def append_source_ledger(workspace: Workspace, record: dict[str, object]) -> None:
    """Append a JSON line to the append-only source ledger."""
    workspace.source_ledger.parent.mkdir(parents=True, exist_ok=True)
    with workspace.source_ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
