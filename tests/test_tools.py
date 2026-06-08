"""Phase 3 tool runtime: schema coercion, registry/toolsets, built-in tools."""

from __future__ import annotations

from shelf.config import default_config
from shelf.store import Store
from shelf.tools import ToolContext, build_default_registry
from shelf.tools.base import Tool
from shelf.tools.registry import ToolRegistry
from shelf.tools.schema import coerce_args, validate_required
from tests.fixtures import FakeFetcher


def test_coerce_args_str_to_scalar_and_array():
    params = {
        "properties": {
            "n": {"type": "integer"},
            "f": {"type": "number"},
            "b": {"type": "boolean"},
            "urls": {"type": "array", "items": {"type": "string"}},
        }
    }
    out = coerce_args(params, {"n": "5", "f": "1.5", "b": "true", "urls": "https://a"})
    assert out == {"n": 5, "f": 1.5, "b": True, "urls": ["https://a"]}


def test_validate_required_flags_missing_and_empty():
    params = {"required": ["q"]}
    assert validate_required(params, {"q": "x"}) == []
    assert validate_required(params, {"q": "  "}) == ["q"]
    assert validate_required(params, {}) == ["q"]


def test_registry_dispatch_known_and_coerces():
    seen = {}
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="echo",
            description="d",
            toolset="t",
            parameters={"properties": {"n": {"type": "integer"}}, "required": ["n"]},
            handler=lambda args, ctx: seen.update(args) or f"got {args['n']!r}",
        )
    )
    out = reg.dispatch("echo", {"n": "7"}, ToolContext())
    assert seen == {"n": 7}  # coerced str -> int before the handler saw it
    assert out == "got 7"


def test_registry_dispatch_missing_required_is_error_string():
    reg = ToolRegistry()
    reg.register(
        Tool("need", "d", "t", parameters={"required": ["q"]}, handler=lambda a, c: "ok")
    )
    assert "missing required" in reg.dispatch("need", {}, ToolContext())


def test_registry_toolset_includes_resolution():
    reg = ToolRegistry()
    for name in ("a", "b"):
        reg.register(Tool(name, "d", name, handler=lambda args, ctx: ""))
    reg.register_toolset("base", ["a"])
    reg.register_toolset("super", ["b"], includes=["base"])
    assert reg.resolve_toolset("super") == ["a", "b"]
    assert reg.resolve_toolset("unknown") == []  # typo degrades, never raises


def test_catalog_filters_by_check_fn():
    reg = ToolRegistry()
    reg.register(Tool("on", "d", "t", handler=lambda a, c: "", check_fn=lambda ctx: True))
    reg.register(Tool("off", "d", "t", handler=lambda a, c: "", check_fn=lambda ctx: False))
    names = {t.name for t in reg.catalog(ToolContext(), toolset=None)}
    assert names == {"on"}


def test_web_search_disabled_by_default():
    reg = build_default_registry()
    ctx = ToolContext(config=default_config("/tmp/x", "x"), fetcher=FakeFetcher(b""))
    out = reg.dispatch("web_search", {"query": "anything"}, ctx)
    assert "disabled" in out.lower()  # privacy.remote_search defaults off


def test_web_search_uses_injected_provider_when_enabled():
    class _FakeProvider:
        def search(self, query, fetcher, *, limit=6):
            return [{"title": "Hit", "url": "https://hit.example", "snippet": "s"}]

    cfg = default_config("/tmp/x", "x")
    cfg.privacy.remote_search = True
    reg = build_default_registry()
    ctx = ToolContext(
        config=cfg, fetcher=FakeFetcher(b""), scratch={"search_provider": _FakeProvider()}
    )
    out = reg.dispatch("web_search", {"query": "q"}, ctx)
    assert "https://hit.example" in out


def test_ddg_parse_results_extracts_rows():
    from shelf.tools.builtins.web_search import _parse_results

    html = b"""
    <div class="result">
      <a class="result__a" href="https://arxiv.org/abs/1312.5602">Playing Atari with Deep RL</a>
      <a class="result__snippet">We present the first deep learning model...</a>
    </div>
    <div class="result">
      <a class="result__a" href="https://example.com/ppo">PPO paper</a>
    </div>
    """
    results = _parse_results(html, limit=6)
    assert len(results) == 2
    assert results[0]["url"] == "https://arxiv.org/abs/1312.5602"
    assert "Atari" in results[0]["title"]
    assert results[0]["snippet"].startswith("We present")
    assert results[1]["snippet"] == ""


def test_ddg_real_url_unwraps_redirect_and_passes_direct():
    from shelf.tools.builtins.web_search import _ddg_real_url

    wrapped = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fx&rut=abc"
    assert _ddg_real_url(wrapped) == "https://example.com/x"
    assert _ddg_real_url("https://direct.example/y") == "https://direct.example/y"


def test_library_search_offline(workspace):
    reg = build_default_registry()
    with Store.open(workspace.db_path) as store:
        store.add_item(title="Local agents primer", summary="about agents", status="new")
        out = reg.dispatch("library_search", {"query": "agents"}, ToolContext(store=store))
    assert "Local agents primer" in out


def test_propose_source_stages_candidate_and_review(workspace):
    reg = build_default_registry()
    with Store.open(workspace.db_path) as store:
        ctx = ToolContext(store=store, scratch={"topic": "t", "topic_id": None, "proposed": []})
        out = reg.dispatch(
            "propose_source",
            {"url": "https://ex.com", "name": "Ex", "role": "blog", "reason": "relevant"},
            ctx,
        )
        assert "Proposed" in out
        sources = store.list_sources()
        assert [s["status"] for s in sources] == ["candidate"]
        assert store.counts().reviews_pending == 1
        # re-proposing the same slug is a no-op (stops small-model loops)
        again = reg.dispatch("propose_source", {"url": "https://ex.com", "name": "Ex"}, ctx)
        assert "already proposed" in again.lower()
        assert len(store.list_sources()) == 1


def test_propose_source_stores_relevance_score(workspace):
    reg = build_default_registry()
    with Store.open(workspace.db_path) as store:
        ctx = ToolContext(store=store, scratch={"topic": "t", "topic_id": None, "proposed": []})
        # relevance arrives as a string from the model; coercion -> float, then clamped
        reg.dispatch(
            "propose_source",
            {"url": "https://ex.com", "name": "Ex", "relevance": "0.9"},
            ctx,
        )
        assert store.get_source("ex")["relevance"] == 0.9
