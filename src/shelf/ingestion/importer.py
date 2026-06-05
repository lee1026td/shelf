"""`/import` - parse local PDF/HTML/Markdown/text files into Items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shelf.errors import IngestionError
from shelf.ingestion.base import PARSER_VERSION
from shelf.ingestion.parsers import SUPPORTED_EXTENSIONS, detect_kind, parse_document
from shelf.ingestion.writers import (
    append_source_ledger,
    summarize,
    write_item,
    write_snapshot,
)
from shelf.store import Store
from shelf.util import sha256_hex, utc_now_iso
from shelf.workspace import Workspace

# Skip files larger than this to avoid reading a multi-GB file fully into memory.
MAX_IMPORT_BYTES = 50 * 1024 * 1024


@dataclass
class ImportedFile:
    source_file: str
    kind: str
    title: str
    item_path: str | None = None
    item_id: int | None = None


@dataclass
class ImportOutcome:
    root: str
    imported: list[ImportedFile] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    dry_run: bool = False


def _gather(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root]
    globber = root.rglob("*") if recursive else root.glob("*")
    return sorted(p for p in globber if p.is_file())


def import_path(
    workspace: Workspace,
    path: Path | str,
    *,
    store: Store | None = None,
    recursive: bool = True,
    dry_run: bool = False,
) -> ImportOutcome:
    """Import a file or a folder of supported files into the library.

    A single unreadable/unparseable file is recorded in ``skipped`` rather than
    aborting the whole batch.
    """
    root = Path(path).expanduser()
    if not root.exists():
        raise IngestionError(f"Path not found: {root}")

    outcome = ImportOutcome(root=str(root), dry_run=dry_run)
    planned: list[Path] = []
    for file in _gather(root, recursive):
        if workspace.is_internal_path(file):
            outcome.skipped.append((str(file), "inside workspace library"))
            continue
        if file.suffix.lower() not in SUPPORTED_EXTENSIONS:
            outcome.skipped.append((str(file), "unsupported extension"))
            continue
        try:
            if file.stat().st_size > MAX_IMPORT_BYTES:
                outcome.skipped.append((str(file), "too large"))
                continue
        except OSError:  # pragma: no cover - stat rarely fails after rglob
            pass
        planned.append(file)

    if dry_run:
        for file in planned:
            outcome.imported.append(
                ImportedFile(source_file=str(file), kind=detect_kind(filename=file.name), title=file.stem)
            )
        return outcome

    owns_store = store is None
    store = store or Store.open(workspace.db_path)
    try:
        for file in planned:
            try:
                with store.savepoint():  # one bad file leaves no partial DB rows
                    _import_one(workspace, file, store, outcome)
            except Exception as exc:  # one bad file must not abort the batch
                outcome.skipped.append((str(file), f"error: {exc}"))
        if owns_store:
            store.commit()
    finally:
        if owns_store:
            store.close()

    return outcome


def _import_one(workspace: Workspace, file: Path, store: Store, outcome: ImportOutcome) -> None:
    data = file.read_bytes()
    kind = detect_kind(filename=file.name)
    parsed = parse_document(data, filename=file.name)
    captured_at = utc_now_iso()
    digest = sha256_hex(data)
    title = parsed.title or file.stem
    file_uri = file.resolve().as_uri()

    raw_rel, norm_rel = write_snapshot(workspace, data, parsed.text or "", digest, kind)
    item_rel = write_item(workspace, parsed, url=file_uri, captured_at=captured_at, kind=kind)
    item_id = store.add_item(
        title=title,
        url=file_uri,
        source_id=None,
        summary=summarize(parsed.text),
        status="new",
        local_path=item_rel,
    )
    store.add_snapshot(
        hash=digest,
        fetched_at=captured_at,
        item_id=item_id,
        raw_path=raw_rel,
        normalized_path=norm_rel,
        parser_version=PARSER_VERSION,
    )
    append_source_ledger(
        workspace,
        {
            "event": "import",
            "at": captured_at,
            "file": str(file),
            "item": item_rel,
            "item_id": item_id,
            "kind": kind,
        },
    )
    outcome.imported.append(
        ImportedFile(
            source_file=str(file), kind=kind, title=title, item_path=item_rel, item_id=item_id
        )
    )
