"""Phase 1 ingestion: parsers, clip, import."""

from __future__ import annotations

import pytest

from shelf.errors import IngestionError, UnsupportedContentError
from shelf.ingestion import clip_url, import_path, parse_document
from shelf.store import Store
from tests.fixtures import FakeFetcher, make_minimal_pdf

# --- parsers ---------------------------------------------------------------


def test_parse_html_title_and_text():
    html = b"<html><head><title>My Title</title></head><body><article><p>Hello body.</p></article></body></html>"
    doc = parse_document(html, content_type="text/html")
    assert doc.title == "My Title"
    assert "Hello body." in (doc.text or "")


def test_parse_html_strips_scripts():
    html = b"<title>T</title><body><script>var x=1;</script><p>keep</p></body>"
    doc = parse_document(html, content_type="text/html")
    assert "var x" not in (doc.text or "")
    assert "keep" in (doc.text or "")


def test_parse_markdown_title_from_heading():
    doc = parse_document(b"# Heading One\n\nsome body", filename="note.md")
    assert doc.title == "Heading One"
    assert "some body" in (doc.markdown or "")


def test_parse_text_first_line_title():
    doc = parse_document(b"First line\nsecond line", filename="a.txt")
    assert doc.title == "First line"


def test_parse_pdf_extracts_text():
    doc = parse_document(make_minimal_pdf("Hello PDF Sample"), content_type="application/pdf")
    assert "Hello PDF Sample" in (doc.text or "")
    assert doc.metadata.get("pages") == 1


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedContentError):
        parse_document(b"\x00\x01", filename="weird.bin")


# --- clip ------------------------------------------------------------------


def test_clip_writes_item_source_snapshot(workspace):
    html = b"<title>Clipped Article</title><body><article><p>Interesting content here.</p></article></body>"
    with Store.open(workspace.db_path) as store:
        outcome = clip_url(
            workspace, "https://example.com/post", fetcher=FakeFetcher(html), store=store
        )
    assert outcome.title == "Clipped Article"
    item = workspace.root / outcome.item_path
    assert item.is_file()
    content = item.read_text(encoding="utf-8")
    assert "Clipped Article" in content  # frontmatter title
    assert "Interesting content here." in content  # body

    with Store.open(workspace.db_path) as store:
        counts = store.counts()
    assert counts.items == 1
    assert counts.inbox == 1
    assert counts.sources == 1  # ephemeral source created
    assert counts.snapshots == 1

    ledger = workspace.source_ledger.read_text(encoding="utf-8")
    assert '"event": "clip"' in ledger


def test_clip_dry_run_writes_nothing(workspace):
    html = b"<title>X</title><body><p>y</p></body>"
    outcome = clip_url(workspace, "https://example.com/x", fetcher=FakeFetcher(html), dry_run=True)
    assert outcome.dry_run is True
    assert outcome.item_path is None
    with Store.open(workspace.db_path) as store:
        assert store.counts().items == 0


def test_clip_preserves_unicode_title(workspace):
    html = "<title>로컬 우선 에이전트</title><body><p>본문</p></body>".encode("utf-8")
    with Store.open(workspace.db_path) as store:
        outcome = clip_url(workspace, "https://example.com/ko", fetcher=FakeFetcher(html), store=store)
    assert outcome.title == "로컬 우선 에이전트"
    assert (workspace.root / outcome.item_path).read_text(encoding="utf-8").count("로컬") >= 1


# --- import ----------------------------------------------------------------


def _make_docs(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# Alpha\n\nalpha body", encoding="utf-8")
    (docs / "b.html").write_text("<title>Beta</title><body><p>beta body</p></body>", encoding="utf-8")
    (docs / "c.txt").write_text("gamma text", encoding="utf-8")
    (docs / "skip.bin").write_bytes(b"\x00\x01\x02")
    return docs


def test_import_folder(workspace, tmp_path):
    docs = _make_docs(tmp_path)
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, docs, store=store)
    assert len(outcome.imported) == 3
    kinds = {entry.kind for entry in outcome.imported}
    assert kinds == {"markdown", "html", "text"}
    assert any("skip.bin" in path for path, _ in outcome.skipped)

    with Store.open(workspace.db_path) as store:
        counts = store.counts()
    assert counts.items == 3
    assert counts.inbox == 3
    assert counts.sources == 0  # local imports are not watchable sources
    assert counts.snapshots == 3

    for entry in outcome.imported:
        assert (workspace.root / entry.item_path).is_file()


def test_import_pdf_file(workspace, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(make_minimal_pdf("Hello PDF Sample"))
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, pdf, store=store)
    assert len(outcome.imported) == 1
    item = workspace.root / outcome.imported[0].item_path
    assert "Hello PDF Sample" in item.read_text(encoding="utf-8")


def test_import_dry_run_writes_nothing(workspace, tmp_path):
    docs = _make_docs(tmp_path)
    outcome = import_path(workspace, docs, dry_run=True)
    assert outcome.dry_run is True
    assert len(outcome.imported) == 3
    assert all(entry.item_path is None for entry in outcome.imported)
    with Store.open(workspace.db_path) as store:
        assert store.counts().items == 0


def test_import_missing_path_raises(workspace, tmp_path):
    with pytest.raises(IngestionError):
        import_path(workspace, tmp_path / "nope", dry_run=True)
