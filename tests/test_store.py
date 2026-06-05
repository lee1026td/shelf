"""SQLite store schema, counts, and basic CRUD."""

from __future__ import annotations

from shelf.store import Store
from shelf.store.migrations import SCHEMA_VERSION


def make_store() -> Store:
    store = Store.open(":memory:")
    store.initialize(shelf_version="test")
    return store


def test_initialize_sets_schema_and_meta():
    store = make_store()
    assert store.schema_version == SCHEMA_VERSION
    assert store.get_meta("shelf_version") == "test"
    assert store.get_meta("created_at") is not None
    store.close()


def test_all_core_tables_created():
    """Acceptance criterion D: a fresh store creates every documented table."""
    store = make_store()
    rows = store.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tables = {r[0] for r in rows}
    assert tables == {
        "schema_meta",
        "topics",
        "sources",
        "items",
        "item_topics",
        "snapshots",
        "claims",
        "review_items",
        "compilations",
        "watch_runs",
    }
    assert store.is_initialized() is True
    store.close()


def test_uninitialized_store_reports_not_initialized(tmp_path):
    """An opened-but-not-initialized DB must not raise on the schema check."""
    store = Store.open(tmp_path / "blank.sqlite")
    assert store.is_initialized() is False
    store.close()


def test_counts_start_zero():
    store = make_store()
    counts = store.counts()
    assert counts.as_dict() == {
        "topics": 0,
        "sources": 0,
        "items": 0,
        "inbox": 0,
        "reviews_pending": 0,
        "claims": 0,
        "compilations": 0,
        "snapshots": 0,
        "watch_runs": 0,
    }
    store.close()


def test_add_and_get_source():
    store = make_store()
    sid = store.add_source(
        "example-blog",
        "https://example.com/blog",
        name="Example Blog",
        role="expert_commentary",
        status="candidate",
        score={"relevance": 0.86, "watchability": 0.81, "noise_risk": 0.35},
    )
    assert sid == 1
    assert store.counts().sources == 1
    row = store.get_source("example-blog")
    assert row is not None
    assert row["url"] == "https://example.com/blog"
    assert row["relevance"] == 0.86
    assert store.get_source("missing") is None
    store.close()


def test_list_sources_filtered_by_status():
    store = make_store()
    store.add_source("a", "https://a", status="candidate")
    store.add_source("b", "https://b", status="watched")
    assert len(store.list_sources()) == 2
    watched = store.list_sources(status="watched")
    assert [s["slug"] for s in watched] == ["b"]
    store.close()


def test_items_drive_inbox_count():
    store = make_store()
    store.add_item(title="New article", url="https://x/1", status="new")
    store.add_item(title="Saved article", url="https://x/2", status="saved")
    counts = store.counts()
    assert counts.items == 2
    assert counts.inbox == 1  # only status='new'
    store.close()


def test_list_items_by_status_and_limit():
    store = make_store()
    store.add_item(title="new one", status="new")
    store.add_item(title="new two", status="new")
    store.add_item(title="saved one", status="saved")
    assert len(store.list_items()) == 3
    assert len(store.list_items(status="new")) == 2
    assert len(store.list_items(limit=1)) == 1
    store.close()


def test_search_items_matches_title_and_summary():
    store = make_store()
    store.add_item(title="Local-first agents", url="https://x/1", summary="about agents")
    store.add_item(title="Weather report", url="https://x/2")
    hits = store.search_items("agent")
    assert len(hits) == 1
    assert hits[0]["title"] == "Local-first agents"
    assert store.search_items("nothing-here") == []
    store.close()


def test_set_item_status_moves_out_of_inbox():
    store = make_store()
    item_id = store.add_item(title="x", status="new")
    assert store.counts().inbox == 1
    assert store.set_item_status(item_id, "saved") is True
    assert store.counts().inbox == 0
    assert store.get_item(item_id)["status"] == "saved"
    assert store.set_item_status(999999, "saved") is False  # no such item
    store.close()


def test_context_manager_commits_and_closes(tmp_path):
    db = tmp_path / "library.sqlite"
    with Store.open(db) as store:
        store.initialize(shelf_version="x")
        store.add_source("s", "https://s")
    # Reopen: the committed row persists.
    with Store.open(db) as store:
        assert store.counts().sources == 1
