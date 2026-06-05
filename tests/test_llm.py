"""Phase 2 LLM gateway (with a fake client; no network)."""

from __future__ import annotations

import pytest

from shelf.config import default_config, load_config
from shelf.errors import LLMError
from shelf.ingestion import import_path
from shelf.llm import ModelGateway, OpenAICompatibleClient, ask_library, summarize_item
from shelf.store import Store
from tests.fixtures import FakeChatClient


def _cfg(remote_llm: bool = False):
    cfg = default_config("/tmp/lib", "lib")
    cfg.privacy.remote_llm = remote_llm
    return cfg


def test_complete_routes_to_planner_profile():
    client = FakeChatClient(reply="hello")
    gateway = ModelGateway(_cfg(), client=client)
    assert gateway.complete("hi") == "hello"
    base_url, model, _messages = client.calls[0]
    assert model == "qwen3:32b"  # the planner profile
    assert base_url == "http://localhost:11434/v1"


def test_complete_includes_system_prompt():
    client = FakeChatClient()
    ModelGateway(_cfg(), client=client).complete("q", system="be terse")
    _b, _m, messages = client.calls[0]
    assert messages[0] == {"role": "system", "content": "be terse"}
    assert messages[-1]["content"] == "q"


def test_embed_uses_embeddings_profile():
    gateway = ModelGateway(_cfg(), client=FakeChatClient(embedding=(1.0, 2.0)))
    assert gateway.embed(["a", "b"]) == [[1.0, 2.0], [1.0, 2.0]]


def test_probe_reachable():
    result = ModelGateway(_cfg(), client=FakeChatClient()).probe()
    assert result.reachable is True
    assert result.model == "qwen3:32b"


def test_probe_reports_error_without_raising():
    class Boom:
        def chat(self, *a, **k):
            raise LLMError("connection refused")

        def embeddings(self, *a, **k):
            raise LLMError("connection refused")

    result = ModelGateway(_cfg(), client=Boom()).probe()
    assert result.reachable is False
    assert "connection refused" in (result.error or "")


def test_remote_endpoint_blocked_by_default():
    cfg = _cfg(remote_llm=False)
    cfg.models["planner"].base_url = "https://api.openai.com/v1"
    with pytest.raises(LLMError):
        ModelGateway(cfg, client=FakeChatClient()).complete("hi")


def test_remote_endpoint_allowed_when_opted_in():
    cfg = _cfg(remote_llm=True)
    cfg.models["planner"].base_url = "https://api.openai.com/v1"
    assert ModelGateway(cfg, client=FakeChatClient(reply="ok")).complete("hi") == "ok"


def test_missing_model_raises():
    cfg = _cfg()
    cfg.models = {}
    with pytest.raises(LLMError):
        ModelGateway(cfg, client=FakeChatClient()).complete("hi")


# --- real client parsing (no network: _post is monkeypatched) --------------


def test_client_chat_parses_openai_format(monkeypatch):
    client = OpenAICompatibleClient()
    monkeypatch.setattr(
        client, "_post", lambda url, payload, api_key: {"choices": [{"message": {"content": "hi"}}]}
    )
    assert client.chat("http://x/v1", "m", [{"role": "user", "content": "q"}]) == "hi"


def test_client_embeddings_parses_openai_format(monkeypatch):
    client = OpenAICompatibleClient()
    monkeypatch.setattr(
        client, "_post", lambda url, payload, api_key: {"data": [{"embedding": [0.1, 0.2]}]}
    )
    assert client.embeddings("http://x/v1", "m", ["a"]) == [[0.1, 0.2]]


# --- tasks: summarize_item / ask_library -----------------------------------


def test_summarize_item_reads_body_and_persists(workspace, tmp_path):
    docs = tmp_path / "d"
    docs.mkdir()
    (docs / "a.md").write_text("# Topic\n\nbody about local agents", encoding="utf-8")
    with Store.open(workspace.db_path) as store:
        outcome = import_path(workspace, docs, store=store)
    item_id = outcome.imported[0].item_id

    client = FakeChatClient(reply="a tidy summary")
    gateway = ModelGateway(load_config(workspace.config_path), client=client)
    with Store.open(workspace.db_path) as store:
        summary = summarize_item(workspace, store, gateway, item_id)

    assert summary == "a tidy summary"
    _base, _model, messages = client.calls[0]
    assert "body about local agents" in messages[-1]["content"]  # body fed to the model
    with Store.open(workspace.db_path) as store:
        assert store.get_item(item_id)["summary"] == "a tidy summary"


def test_summarize_missing_item_raises(workspace):
    gateway = ModelGateway(load_config(workspace.config_path), client=FakeChatClient())
    with Store.open(workspace.db_path) as store:
        with pytest.raises(LLMError):
            summarize_item(workspace, store, gateway, 99999)


def test_ask_library_includes_item_context(workspace):
    with Store.open(workspace.db_path) as store:
        store.add_item(title="Local agents", summary="all about agents", status="new")
    client = FakeChatClient(reply="based on your items...")
    gateway = ModelGateway(load_config(workspace.config_path), client=client)
    with Store.open(workspace.db_path) as store:
        answer = ask_library(workspace, store, gateway, "what do I have?")
    assert answer == "based on your items..."
    _base, _model, messages = client.calls[0]
    assert "Local agents" in messages[-1]["content"]  # library context grounded the prompt
