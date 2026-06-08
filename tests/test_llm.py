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
    # default_config ships empty model ids now; pick concrete ones for routing tests.
    cfg.models["planner"].model = "qwen3:8b"
    cfg.models["embeddings"].model = "nomic-embed-text"
    cfg.privacy.remote_llm = remote_llm
    return cfg


def test_complete_routes_to_planner_profile():
    client = FakeChatClient(reply="hello")
    gateway = ModelGateway(_cfg(), client=client)
    assert gateway.complete("hi") == "hello"
    base_url, model, _messages = client.calls[0]
    assert model == "qwen3:8b"  # the planner profile
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
    assert result.model == "qwen3:8b"


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


def test_client_chat_falls_back_to_reasoning_when_content_empty(monkeypatch):
    # Thinking models (qwen3 via Ollama) can return content='' + reasoning=...
    client = OpenAICompatibleClient()
    monkeypatch.setattr(
        client,
        "_post",
        lambda url, payload, api_key: {
            "choices": [{"message": {"content": "", "reasoning": "The answer is Paris."}}]
        },
    )
    assert client.chat("http://x/v1", "m", [{"role": "user", "content": "q"}]) == "The answer is Paris."


def test_client_chat_strips_think_tags(monkeypatch):
    client = OpenAICompatibleClient()
    monkeypatch.setattr(
        client,
        "_post",
        lambda url, payload, api_key: {
            "choices": [{"message": {"content": "<think>hmm let me see</think>Paris."}}]
        },
    )
    assert client.chat("http://x/v1", "m", [{"role": "user", "content": "q"}]) == "Paris."


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
    cfg = load_config(workspace.config_path)
    cfg.models["planner"].model = "qwen3:8b"  # default ships unset; chat needs one
    gateway = ModelGateway(cfg, client=client)
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
    cfg = load_config(workspace.config_path)
    cfg.models["planner"].model = "qwen3:8b"  # default ships unset; chat needs one
    gateway = ModelGateway(cfg, client=client)
    with Store.open(workspace.db_path) as store:
        answer = ask_library(workspace, store, gateway, "what do I have?")
    assert answer == "based on your items..."
    _base, _model, messages = client.calls[0]
    assert "Local agents" in messages[-1]["content"]  # library context grounded the prompt


def test_ask_library_empty_is_plain_chat(workspace):
    # Empty library + a greeting must NOT become a RAG refusal prompt.
    client = FakeChatClient(reply="Hi! How can I help?")
    cfg = load_config(workspace.config_path)
    cfg.models["planner"].model = "qwen3:8b"
    gateway = ModelGateway(cfg, client=client)
    with Store.open(workspace.db_path) as store:
        answer = ask_library(workspace, store, gateway, "Hello")
    assert answer == "Hi! How can I help?"
    system, user = client.calls[0][2]
    assert "ONLY from the provided library items" not in system["content"]  # not strict RAG
    assert "library is empty" not in user["content"].lower()  # no empty-RAG framing
    assert "Hello" in user["content"]


# --- model selection -------------------------------------------------------


def test_gateway_list_models():
    models = ModelGateway(_cfg(), client=FakeChatClient()).list_models("planner")
    assert "qwen3:8b" in models


def test_client_list_models_parses(monkeypatch):
    client = OpenAICompatibleClient()
    monkeypatch.setattr(client, "_get", lambda url, api_key: {"data": [{"id": "a"}, {"id": "b"}]})
    assert client.list_models("http://x/v1") == ["a", "b"]


def test_set_model_persists_both_roles(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="qwen3:8b")
    set_model(workspace, "embeddings", model="bge-m3", base_url="http://localhost:11434/v1")
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].model == "qwen3:8b"
    assert cfg.models["planner"].base_url == "http://localhost:11434/v1"  # preserved
    assert cfg.models["embeddings"].model == "bge-m3"
    assert cfg.models["embeddings"].base_url == "http://localhost:11434/v1"


def test_set_model_to_remote_endpoint(workspace):
    from shelf.services import set_model

    set_model(workspace, "planner", model="gpt-4o-mini", base_url="https://api.openai.com/v1")
    cfg = load_config(workspace.config_path)
    assert cfg.models["planner"].base_url == "https://api.openai.com/v1"
    # ...but still blocked unless remote_llm is enabled (egress gate)
    with pytest.raises(LLMError):
        ModelGateway(cfg, client=FakeChatClient()).complete("hi")
