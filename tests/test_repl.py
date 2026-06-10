"""REPL dispatch and loop behavior."""

from __future__ import annotations

from rich.console import Console

from shelf.config import load_config
from shelf.errors import LLMError
from shelf.ingestion import import_path
from shelf.llm import ModelGateway
from shelf.repl.session import ReplSession, run_repl
from shelf.services import set_model
from shelf.store import Store
from tests.fixtures import FakeChatClient, FakeFetcher, ScriptedChatClient


def _gateway(workspace, reply="canned answer"):
    cfg = load_config(workspace.config_path)
    if not cfg.models["planner"].model:  # default ships unset; chat needs a model
        cfg.models["planner"].model = "qwen3:8b"
    return ModelGateway(cfg, client=FakeChatClient(reply=reply))


def _rec() -> Console:
    return Console(record=True, width=100)


def test_clip_import_registered_as_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    assert COMMANDS_BY_NAME["clip"].available is True
    assert COMMANDS_BY_NAME["import"].available is True
    assert COMMANDS_BY_NAME["watch"].available is False  # still Phase 4


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
    assert "Phase 4" in out  # upcoming marker (watcher etc.)


def test_unimplemented_slash_announces_phase(workspace):
    console = _rec()
    session = ReplSession(workspace, console=console)
    session.handle("/track local-first agents")  # /track is still a Phase 3/4 stub
    out = console.export_text()
    assert "Phase" in out
    assert session.running is True


def test_free_text_routes_through_agent(workspace):
    # Free text (no slash) is agentic now: the model routes over read-only tools and the
    # final answer is printed. A lone 'final' reply exercises the path without tool calls.
    set_model(workspace, "planner", model="qwen3:8b")  # persisted so the model check passes
    gateway = ModelGateway(
        load_config(workspace.config_path),
        client=ScriptedChatClient(['{"tool":"final","args":{"answer":"the answer"}}']),
    )
    console = _rec()
    session = ReplSession(workspace, console=console, gateway=gateway)
    session.handle("무엇이든 물어봐")
    assert "the answer" in console.export_text()


def test_free_text_without_model_prompts_for_model(workspace):
    console = _rec()
    ReplSession(workspace, console=console).handle("무엇이든 물어봐")
    assert "No model configured" in console.export_text()


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
    from shelf.services import set_model

    set_model(workspace, "planner", model="qwen3:8b")  # a configured model shows in the table
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model")
    out = console.export_text()
    assert "qwen3:8b" in out
    assert "reachable" in out.lower()


def test_repl_model_unset_shows_none(workspace):
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model")
    out = console.export_text()
    assert "(none)" in out  # fresh workspace: no fabricated placeholder model


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


# --- /model interactive picker --------------------------------------------


def _asker(answers):
    """A scripted prompt reader; raises EOFError (clean cancel) when exhausted."""
    it = iter(answers)

    def ask(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return ask


def _picker(workspace, answers, console=None, client=None):
    # client= (not gateway=) so the gateway can be rebuilt from fresh config mid-picker
    # while still talking to the fake; asker= drives the interactive prompts.
    return ReplSession(
        workspace,
        console=console or _rec(),
        client=client or FakeChatClient(),
        asker=_asker(answers),
    )


class _RaisingListClient(FakeChatClient):
    """Reachable for chat, but /models always fails (e.g. endpoint unreachable)."""

    def list_models(self, base_url, *, api_key=None):
        raise LLMError("connection refused")


class _EmptyListClient(FakeChatClient):
    """Reachable, but exposes no /models list (returns [])."""

    def list_models(self, base_url, *, api_key=None):
        return []


class _OkAtUrlClient(FakeChatClient):
    """/models succeeds only at one URL; raises elsewhere (simulates a wrong URL)."""

    def __init__(self, ok_url):
        super().__init__()
        self.ok_url = ok_url

    def list_models(self, base_url, *, api_key=None):
        if base_url != self.ok_url:
            raise LLMError("connection refused")
        return ["good-model"]


# `/model planner` jumps the picker straight into the planner role (skips the role
# step); the role step itself is covered by the embeddings tests below.
def test_model_picker_ollama_local(workspace):
    # provider 1 (Ollama), then model index 2 from the fake list -> qwen3:8b
    console = _rec()
    _picker(workspace, ["1", "2"], console).handle("/model planner")
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].model == "qwen3:8b"
    assert cfg.models["planner"].base_url == "http://localhost:11434/v1"
    assert cfg.models["planner"].provider == "ollama"
    assert cfg.privacy.remote_llm is False  # local: no egress needed


def test_model_picker_model_pick_by_name(workspace):
    # typing a name instead of an index also works
    _picker(workspace, ["1", "mistral:7b"]).handle("/model planner")
    assert load_config(workspace.config_path).models["planner"].model == "mistral:7b"


def test_model_picker_custom_remote_enables_egress_after_confirm(workspace):
    # provider 2 (custom), remote URL, confirm egress, pick model 1
    _picker(
        workspace, ["2", "https://api.example.com/v1", "y", "1"]
    ).handle("/model planner")
    cfg = load_config(workspace.config_path)
    assert cfg.privacy.remote_llm is True  # enabled only after explicit confirm
    assert cfg.models["planner"].base_url == "https://api.example.com/v1"
    assert cfg.models["planner"].model == "qwen3:32b"  # index 1 of the fake list


def test_model_picker_remote_declined_keeps_egress_off(workspace):
    # provider 3 (OpenAI), decline egress -> endpoint saved, gate stays off, no model
    console = _rec()
    _picker(workspace, ["3", "n"], console).handle("/model planner")
    cfg = load_config(workspace.config_path)
    assert cfg.privacy.remote_llm is False
    assert cfg.models["planner"].base_url == "https://api.openai.com/v1"
    assert cfg.models["planner"].provider == "openai"
    assert cfg.models["planner"].model == ""  # never got to model selection
    assert "blocked" in console.export_text().lower()


def test_model_picker_anthropic_is_coming_soon(workspace):
    console = _rec()
    _picker(workspace, ["4"], console).handle("/model planner")
    out = console.export_text()
    assert "available" in out.lower()  # "isn't available yet"
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].model == ""  # nothing changed
    assert cfg.privacy.remote_llm is False


def test_model_picker_invalid_choice_is_noop(workspace):
    console = _rec()
    _picker(workspace, ["9"], console).handle("/model planner")
    assert "invalid" in console.export_text().lower()
    assert load_config(workspace.config_path).models["planner"].model == ""


def test_model_without_asker_shows_table_not_picker(workspace):
    # No asker (piped/non-interactive): bare /model must show the profile table.
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model")
    out = console.export_text()
    assert "Role" in out  # the render_models table header, not a picker prompt


def test_model_show_always_shows_table(workspace):
    console = _rec()
    ReplSession(workspace, console=console, gateway=_gateway(workspace)).handle("/model show")
    assert "Role" in console.export_text()


# --- /explore (Phase 3) ----------------------------------------------------


def test_explore_is_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    assert COMMANDS_BY_NAME["explore"].available is True


def test_repl_explore_runs_and_proposes(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="m")  # /explore guards on a configured model
    replies = [
        '{"tool":"propose_source","args":{"url":"https://ex.com/a","name":"Site A",'
        '"reason":"relevant"}}',
        '{"tool":"final","args":{"answer":"A short brief (https://ex.com/a)."}}',
    ]
    console = _rec()
    session = ReplSession(
        workspace, console=console, client=ScriptedChatClient(replies), fetcher=FakeFetcher(b"")
    )
    session.handle("/explore local-first software")
    out = console.export_text()
    assert "brief" in out.lower()
    assert "proposed" in out.lower()  # the trace summary line
    with Store.open(workspace.db_path) as store:
        assert any(s["status"] == "candidate" for s in store.list_sources())


def test_repl_explore_needs_a_model(workspace):
    console = _rec()  # fresh workspace ships no model
    ReplSession(workspace, console=console).handle("/explore something")
    assert "no model" in console.export_text().lower()


def test_repl_explore_offers_to_enable_web_search(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="m")
    assert load_config(workspace.config_path).privacy.remote_search is False
    session = ReplSession(
        workspace,
        console=_rec(),
        client=ScriptedChatClient(['{"tool":"final","args":{"answer":"done"}}']),
        fetcher=FakeFetcher(b""),
        asker=_asker(["y"]),  # confirm enabling web search
    )
    session.handle("/explore a topic")
    assert load_config(workspace.config_path).privacy.remote_search is True


def test_repl_explore_decline_keeps_web_search_off(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="m")
    session = ReplSession(
        workspace,
        console=_rec(),
        client=ScriptedChatClient(['{"tool":"final","args":{"answer":"done"}}']),
        fetcher=FakeFetcher(b""),
        asker=_asker(["n"]),  # decline
    )
    session.handle("/explore a topic")
    assert load_config(workspace.config_path).privacy.remote_search is False


def test_repl_explore_steps_flag_is_parsed_out_of_topic(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="m")
    session = ReplSession(
        workspace,
        console=_rec(),
        client=ScriptedChatClient(['{"tool":"final","args":{"answer":"done"}}']),
        fetcher=FakeFetcher(b""),
        asker=_asker(["n"]),
    )
    session.handle("/explore deep RL --steps 3")
    with Store.open(workspace.db_path) as store:
        assert store.get_topic("deep-rl") is not None  # --steps stripped from the topic
        assert store.get_topic("deep-rl-steps-3") is None


def test_repl_track_marks_topic_tracked(workspace):
    ReplSession(workspace, console=_rec()).handle("/track Local First --frequency daily")
    with Store.open(workspace.db_path) as store:
        assert store.get_topic("local-first")["status"] == "tracked"


def test_repl_compile_writes_and_records(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="m")
    session = ReplSession(
        workspace,
        console=_rec(),
        client=ScriptedChatClient(
            ['{"tool":"final","args":{"answer":"Overview: x (https://ex.com)"}}']
        ),
        fetcher=FakeFetcher(b""),
    )
    session.handle("/compile local-first --kind brief")
    with Store.open(workspace.db_path) as store:
        assert store.counts().compilations == 1


def test_repl_track_is_available_now():
    from shelf.repl.commands import COMMANDS_BY_NAME

    assert COMMANDS_BY_NAME["track"].available is True
    assert COMMANDS_BY_NAME["compile"].available is True


def test_model_picker_shows_current_config_table(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="already-set")
    console = _rec()
    _picker(workspace, ["4"], console).handle("/model planner")  # 4 = coming-soon, exits
    out = console.export_text()
    assert "Role" in out  # current-config table is rendered at the top of the picker
    assert "already-set" in out


def test_model_picker_custom_retries_url_on_failed_connection(workspace):
    # First URL fails to list -> picker must re-ask the URL, not fake a selection.
    good = "http://localhost:11434/v1"
    console = _rec()
    _picker(
        workspace,
        ["2", "http://localhost:9999/v1", good, "1"],
        console,
        client=_OkAtUrlClient(good),
    ).handle("/model planner")
    out = console.export_text()
    assert "could not connect" in out.lower()  # honest failure on the bad URL
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].base_url == good
    assert cfg.models["planner"].model == "good-model"


def test_model_picker_failed_connection_does_not_set_model(workspace):
    # Fixed endpoint (Ollama) that can't be reached: no model, no green "success".
    console = _rec()
    _picker(workspace, ["1"], console, client=_RaisingListClient()).handle("/model planner")
    out = console.export_text()
    assert "could not connect" in out.lower()
    assert "planner ->" not in out  # never prints the green confirmation
    assert load_config(workspace.config_path).models["planner"].model == ""


def test_model_picker_reachable_but_empty_allows_manual_id(workspace):
    # Reachable endpoint with no /models list: a manual id is still legitimate.
    _picker(workspace, ["1", "hand-typed"], client=_EmptyListClient()).handle("/model planner")
    assert load_config(workspace.config_path).models["planner"].model == "hand-typed"


def test_model_picker_role_step_configures_embeddings(workspace):
    # Bare /model: role 2 (embeddings) -> provider 1 (Ollama) -> model index 1.
    _picker(workspace, ["2", "1", "1"]).handle("/model")
    cfg = load_config(workspace.config_path)
    assert cfg.models["embeddings"].model == "qwen3:32b"  # index 1 of the fake list
    assert cfg.models["planner"].model == ""  # planner untouched


def test_model_embeddings_direct_shortcut(workspace):
    # /model embeddings jumps straight into the embeddings role (no role step).
    _picker(workspace, ["1", "2"]).handle("/model embeddings")
    cfg = load_config(workspace.config_path)
    assert cfg.models["embeddings"].model == "qwen3:8b"  # index 2 of the fake list
    assert cfg.models["planner"].model == ""


def test_model_picker_role_invalid_is_noop(workspace):
    console = _rec()
    _picker(workspace, ["9"], console).handle("/model")  # 9 is not a valid role
    assert "invalid" in console.export_text().lower()
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].model == ""
    assert cfg.models["embeddings"].model == ""
