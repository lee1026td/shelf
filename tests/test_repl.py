"""REPL dispatch and loop behavior."""

from __future__ import annotations

from rich.console import Console

from shelf.repl.session import ReplSession, run_repl
from shelf.store import Store
from tests.fixtures import FakeFetcher


def _rec() -> Console:
    return Console(record=True, width=100)


def test_clip_import_registered_as_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    assert COMMANDS_BY_NAME["clip"].available is True
    assert COMMANDS_BY_NAME["import"].available is True
    assert COMMANDS_BY_NAME["ask"].available is False  # still Phase 2


def test_status_runs_for_real(workspace):
    console = _rec()
    session = ReplSession(workspace, console=console)
    session.handle("/status")
    out = console.export_text()
    assert "shelf status" in out
    assert "[sources: 0]" in out


def test_help_lists_available_and_upcoming(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("/help")
    out = console.export_text()
    assert "/status" in out
    assert "/explore" in out
    assert "now" in out  # available-now marker
    assert "Phase 3" in out  # upcoming marker


def test_unimplemented_slash_announces_phase(workspace):
    console = _rec()
    session = ReplSession(workspace, console=console)
    session.handle("/explore local-first agents")
    out = console.export_text()
    assert "Phase 3" in out
    assert session.running is True


def test_free_text_announces_chat_phase(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("이 주제가 궁금해")
    out = console.export_text()
    assert "Phase 2" in out
    assert out.isascii()  # the echoed notice must be ASCII (cp949 safety)


def test_exit_stops_loop(workspace):
    session = ReplSession(workspace, console=_rec())
    session.handle("/exit")
    assert session.running is False


def test_quit_alias(workspace):
    session = ReplSession(workspace, console=_rec())
    session.handle("/q")
    assert session.running is False


def test_unknown_command(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("/nope")
    assert "Unknown command" in console.export_text()


def test_blank_line_is_noop(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("   ")
    assert console.export_text() == ""


def test_bom_prefixed_command_dispatches(workspace):
    """Piped stdin (e.g. PowerShell) can prepend a BOM to the first line."""
    console = _rec()
    ReplSession(workspace, console=console).handle("﻿/status")
    assert "shelf status" in console.export_text()


def test_mojibake_bom_prefix_dispatches(workspace):
    """A UTF-8 BOM decoded under cp949 arrives as U+FFFD + a surrogate, not U+FEFF."""
    console = _rec()
    ReplSession(workspace, console=console).handle("�\udcbf/status")
    assert "shelf status" in console.export_text()


def test_run_repl_loop_with_scripted_reader(workspace):
    console = _rec()
    lines = iter(["/status", "", "/exit"])

    def reader() -> str:
        try:
            return next(lines)
        except StopIteration:  # pragma: no cover - loop exits on /exit first
            raise EOFError

    run_repl(workspace, console=console, reader=reader)
    out = console.export_text()
    assert "[sources: 0]" in out
    assert "Bye." in out


def test_run_repl_stops_on_eof(workspace):
    console = _rec()

    def reader() -> str:
        raise EOFError

    run_repl(workspace, console=console, reader=reader)  # must not hang/raise
    assert "shelf REPL" in console.export_text()


def test_repl_clip_with_fake_fetcher(workspace):
    html = b"<title>Zeta Post</title><body><article><p>zeta body</p></article></body>"
    session = ReplSession(workspace, console=_rec(), fetcher=FakeFetcher(html))
    session.handle("/clip https://example.com/zeta")
    with Store.open(workspace.db_path) as store:
        assert store.counts().items == 1


def test_repl_clip_usage_without_arg(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("/clip")
    assert "Usage" in console.export_text()


def test_repl_import_folder(workspace, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nbody", encoding="utf-8")
    console = _rec()
    ReplSession(workspace, console=console).handle(f"/import {docs}")
    with Store.open(workspace.db_path) as store:
        assert store.counts().items == 1


def test_browse_commands_registered_as_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    for name in ("inbox", "search", "sources", "save", "mute"):
        assert COMMANDS_BY_NAME[name].available is True


def _seed_library(workspace):
    with Store.open(workspace.db_path) as store:
        source_id = store.add_source("example", "https://example.com", status="watched")
        item_id = store.add_item(
            title="Local-first agents",
            url="https://example.com/1",
            source_id=source_id,
            summary="all about agents",
            status="new",
        )
        store.add_item(title="Weather report", url="https://example.com/2", status="new")
    return item_id


def test_repl_inbox_lists_new_items(workspace):
    _seed_library(workspace)
    console = _rec()
    ReplSession(workspace, console=console).handle("/inbox")
    out = console.export_text()
    assert "inbox" in out
    assert "Local-first agents" in out


def test_repl_search_filters(workspace):
    _seed_library(workspace)
    console = _rec()
    ReplSession(workspace, console=console).handle("/search agents")
    out = console.export_text()
    assert "Local-first agents" in out
    assert "Weather report" not in out


def test_repl_sources_lists(workspace):
    _seed_library(workspace)
    console = _rec()
    ReplSession(workspace, console=console).handle("/sources")
    out = console.export_text()
    assert "example" in out
    assert "watched" in out


def test_repl_save_changes_status(workspace):
    item_id = _seed_library(workspace)
    console = _rec()
    ReplSession(workspace, console=console).handle(f"/save {item_id}")
    assert "saved" in console.export_text()
    with Store.open(workspace.db_path) as store:
        assert store.get_item(item_id)["status"] == "saved"
        assert store.counts().inbox == 1  # the other item is still new


def test_repl_save_without_id_shows_usage(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("/save")
    assert "Usage" in console.export_text()
