"""Regression tests for Phase 1 review findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from shelf.errors import FetchError
from shelf.ingestion import clip_url, import_path, parse_document
from shelf.ingestion.fetch import HttpFetcher
from shelf.ingestion.parsers import detect_kind
from shelf.store import Store
from shelf.util import sha256_hex
from tests.fixtures import FakeFetcher


def _library_file_count(workspace) -> int:
    dirs = [workspace.items_dir, workspace.snapshots_dir, workspace.normalized_dir]
    return sum(1 for d in dirs for p in d.rglob("*") if p.is_file())


# --- parse_html title leak (finding #1) ------------------------------------


def test_parse_html_no_body_does_not_leak_title():
    doc = parse_document(b"<title>T</title><div><p>only body</p></div>", content_type="text/html")
    assert doc.title == "T"
    assert doc.text == "only body"  # title not duplicated into body


# --- detect_kind precedence + URL query (findings #6, #13) -----------------


def test_detect_kind_content_type_wins_over_extension():
    assert detect_kind("text/html", filename="x.pdf") == "html"


def test_detect_kind_url_with_query_string():
    assert detect_kind(None, filename="https://cdn.example.com/report.pdf?v=2") == "pdf"


# --- /import self-recursion exclusion (findings #2-5, #17, #21) -------------


def test_import_excludes_workspace_internal(workspace, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nbody", encoding="utf-8")
    with Store.open(workspace.db_path) as store:
        import_path(workspace, docs, store=store)
    with Store.open(workspace.db_path) as store:
        before = store.counts()

    # Importing the workspace root must NOT re-ingest .shelf/ or Items/.
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, workspace.root, store=store)
    assert outcome.imported == []
    assert any("inside workspace library" in reason for _, reason in outcome.skipped)
    with Store.open(workspace.db_path) as store:
        after = store.counts()
    assert after.items == before.items
    assert after.snapshots == before.snapshots


# --- snapshot dedup (finding #12) ------------------------------------------


def test_snapshot_dedup_same_content(workspace):
    html = b"<title>Dup</title><body><p>same content</p></body>"
    with Store.open(workspace.db_path) as store:
        clip_url(workspace, "https://example.com/a", fetcher=FakeFetcher(html), store=store)
        clip_url(workspace, "https://example.com/a", fetcher=FakeFetcher(html), store=store)
    digest = sha256_hex(html)
    raw_files = list(workspace.snapshots_dir.glob(f"{digest}.*"))
    assert len(raw_files) == 1  # one shared snapshot file
    with Store.open(workspace.db_path) as store:
        counts = store.counts()
    assert counts.snapshots == 2  # two rows pointing at the one file
    assert counts.items == 2
    assert counts.sources == 1  # same domain -> ephemeral source reused


# --- dry-run touches neither index nor filesystem (finding #15) ------------


def test_clip_dry_run_touches_no_files(workspace):
    html = b"<title>X</title><body><p>y</p></body>"
    clip_url(workspace, "https://example.com/x", fetcher=FakeFetcher(html), dry_run=True)
    assert _library_file_count(workspace) == 0
    assert workspace.source_ledger.read_text(encoding="utf-8") == ""


def test_import_dry_run_touches_no_files(workspace, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nb", encoding="utf-8")
    import_path(workspace, docs, dry_run=True)
    assert _library_file_count(workspace) == 0
    assert workspace.source_ledger.read_text(encoding="utf-8") == ""


# --- relative POSIX path columns (finding #22) -----------------------------


def test_db_paths_are_relative_posix(workspace, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nbody", encoding="utf-8")
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, docs, store=store)
        row = store.get_item(outcome.imported[0].item_id)
        snaps = store.connection.execute(
            "SELECT raw_path, normalized_path FROM snapshots"
        ).fetchall()

    local_path = row["local_path"]
    assert not Path(local_path).is_absolute()
    assert "\\" not in local_path
    assert (workspace.root / local_path).is_file()
    for raw_path, norm_path in snaps:
        for stored in (raw_path, norm_path):
            assert not Path(stored).is_absolute()
            assert "\\" not in stored
            assert (workspace.root / stored).is_file()


# --- fetcher scheme allow-list (finding #9) --------------------------------


def test_fetcher_rejects_non_allowed_scheme():
    with pytest.raises(FetchError):
        HttpFetcher().fetch("ftp://example.com/data")


# --- per-file savepoint atomicity (finding #8) -----------------------------


def test_import_failed_file_leaves_no_orphan_rows(workspace, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text("# Bad\n\nx", encoding="utf-8")
    (docs / "good.md").write_text("# Good\n\nok", encoding="utf-8")

    original = Store.add_snapshot
    calls = {"n": 0}

    def flaky(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # fail the first file's snapshot insert
            raise RuntimeError("boom")
        return original(self, **kwargs)

    monkeypatch.setattr(Store, "add_snapshot", flaky)
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, docs, store=store)

    assert len(outcome.imported) == 1
    assert any("error" in reason for _, reason in outcome.skipped)
    with Store.open(workspace.db_path) as store:
        counts = store.counts()
    assert counts.items == 1  # bad file's add_item was rolled back
    assert counts.snapshots == 1


# --- owns-store self-commit path (finding #18 commit-ownership) -------------


def test_clip_without_passed_store_self_commits(workspace):
    html = b"<title>Self</title><body><p>commit</p></body>"
    clip_url(workspace, "https://example.com/self", fetcher=FakeFetcher(html))  # no store=
    with Store.open(workspace.db_path) as store:
        assert store.counts().items == 1
