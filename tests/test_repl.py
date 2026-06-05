"""REPL dispatch and loop behavior."""

from __future__ import annotations

from rich.console import Console

from shelf.config import load_config
from shelf.ingestion import import_path
from shelf.llm import ModelGateway
from shelf.repl.session import ReplSession, run_repl
from shelf.store import Store
from tests.fixtures import FakeChatClient, FakeFetcher


def _gateway(workspace, reply="canned answer"):
    return ModelGateway(load_config(workspace.config_path), client=FakeChatClient(reply=reply))


def _rec() -> Console:
    return Console(record=True, width=100)


def test_clip_import_registered_as_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    assert COMMANDS_BY_NAME["clip"].available is True
    assert COMMANDS_BY_NAME["import"].available is True
    assert COMMANDS_BY_NAME["explore"].available is False  # still Phase 3


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


def test_free_text_asks_the_library(workspace):
    console = _rec()
    session = ReplSession(workspace, console=console, gateway=_gateway(workspace, "the answer"))
    session.handle("무엇이든 물어봐")
    assert "the answer" in console.export_text()


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


def test_llm_commands_registered_as_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    for name in ("ask", "summarize", "model"):
        assert COMMANDS_BY_NAME[name].available is True


def test_repl_ask_uses_gateway(workspace):
    console = _rec()
    session = ReplSession(workspace, console=console, gateway=_gateway(workspace, "grounded reply"))
    session.handle("/ask what is in my library?")
    assert "grounded reply" in console.export_text()


def test_repl_ask_without_arg_shows_usage(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("/ask")
    assert "Usage" in console.export_text()


def test_repl_summarize_updates_item(workspace, tmp_path):
    docs = tmp_path / "d"
    docs.mkdir()
    (docs / "a.md").write_text("# Topic\n\nA long body about local agents.", encoding="utf-8")
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, docs, store=store)
    item_id = outcome.imported[0].item_id

    console = _rec()
    session = ReplSession(workspace, console=console, gateway=_gateway(workspace, "short summary"))
    session.handle(f"/summarize {item_id}")
    assert "short summary" in console.export_text()
    with Store.open(workspace.db_path) as store:
        assert store.get_item(item_id)["summary"] == "short summary"


def test_repl_model_shows_profiles_and_probe(workspace):
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model")
    out = console.export_text()
    assert "qwen3:32b" in out
    assert "reachable" in out.lower()


def test_repl_model_list(workspace):
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model list")
    assert "qwen3:8b" in console.export_text()  # from the fake client's model list


def test_repl_model_set_persists(workspace):
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle(
        "/model set planner qwen3:8b"
    )
    assert "qwen3:8b" in console.export_text()
    assert load_config(workspace.config_path).models["planner"].model == "qwen3:8b"


def test_repl_model_set_embeddings(workspace):
    ReplSession(workspace, console=_rec(), gateway=_gateway(workspace)).handle(
        "/model set embeddings bge-m3"
    )
    assert load_config(workspace.config_path).models["embeddings"].model == "bge-m3"


def test_repl_model_use_is_planner_shorthand(workspace):
    ReplSession(workspace, console=_rec(), gateway=_gateway(workspace)).handle("/model use llama3.1")
    assert load_config(workspace.config_path).models["planner"].model == "llama3.1"
