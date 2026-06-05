"""REPL dispatch and loop behavior."""

from __future__ import annotations

from rich.console import Console

from shelf.repl.session import ReplSession, run_repl
from shelf.store import Store
from tests.fixtures import FakeFetcher


def _rec() -> Console:
    return Console(record=True, width=100)


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
