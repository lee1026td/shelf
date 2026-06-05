"""`/clip` - fetch a URL, parse it, and save it as an Item."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from shelf.ingestion.base import PARSER_VERSION, Fetcher
from shelf.ingestion.fetch import HttpFetcher
from shelf.ingestion.parsers import detect_kind, parse_document
from shelf.ingestion.writers import (
    append_source_ledger,
    summarize,
    write_item,
    write_snapshot,
)
from shelf.store import Store
from shelf.util import sha256_hex, slugify, utc_now_iso
from shelf.workspace import Workspace


@dataclass
class ClipOutcome:
    url: str
    title: str
    kind: str
    dry_run: bool = False
    item_path: str | None = None
    item_id: int | None = None
    source_slug: str | None = None
    source_id: int | None = None
    snapshot_hash: str | None = None


def clip_url(
    workspace: Workspace,
    url: str,
    *,
    fetcher: Fetcher | None = None,
    store: Store | None = None,
    dry_run: bool = False,
) -> ClipOutcome:
    """Fetch + parse ``url`` and (unless ``dry_run``) write an Item, snapshot, and
    an ephemeral source, returning a :class:`ClipOutcome`.
    """
    fetcher = fetcher or HttpFetcher()
    result = fetcher.fetch(url)
    kind = detect_kind(result.content_type, filename=url)
    parsed = parse_document(result.raw, content_type=result.content_type, filename=url)
    title = parsed.title or url

    if dry_run:
        return ClipOutcome(url=url, title=title, kind=kind, dry_run=True)

    captured_at = utc_now_iso()
    digest = sha256_hex(result.raw)
    netloc = urlparse(url).netloc or "local-file"
    source_slug = slugify(netloc, fallback="source")

    owns_store = store is None
    store = store or Store.open(workspace.db_path)
    try:
        existing = store.get_source(source_slug)
        if existing:
            source_id = int(existing["id"])
        else:
            source_id = store.add_source(
                source_slug, url, name=netloc, role="clipped", status="ephemeral"
            )
        raw_rel, norm_rel = write_snapshot(workspace, result.raw, parsed.text or "", digest, kind)
        item_rel = write_item(
            workspace, parsed, url=url, captured_at=captured_at, kind=kind, source_slug=source_slug
        )
        item_id = store.add_item(
            title=title,
            url=url,
            source_id=source_id,
            summary=summarize(parsed.text),
            status="new",
            local_path=item_rel,
        )
        store.add_snapshot(
            hash=digest,
            fetched_at=captured_at,
            source_id=source_id,
            item_id=item_id,
            raw_path=raw_rel,
            normalized_path=norm_rel,
            parser_version=PARSER_VERSION,
        )
        append_source_ledger(
            workspace,
            {
                "event": "clip",
                "at": captured_at,
                "url": url,
                "source": source_slug,
                "item": item_rel,
                "item_id": item_id,
                "hash": digest,
                "kind": kind,
            },
        )
        if owns_store:
            store.commit()
    finally:
        if owns_store:
            store.close()

    return ClipOutcome(
        url=url,
        title=title,
        kind=kind,
        item_path=item_rel,
        item_id=item_id,
        source_slug=source_slug,
        source_id=source_id,
        snapshot_hash=digest,
    )
