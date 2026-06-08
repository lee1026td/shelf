"""Phase 3 /explore: agent-driven discovery, propose-don't-mutate, offline path."""

from __future__ import annotations

import json

from shelf.config import load_config
from shelf.discovery import compile_topic, explore_topic
from shelf.llm import ModelGateway
from shelf.services import track_topic
from shelf.store import Store
from tests.fixtures import FakeFetcher, ScriptedChatClient


def _gateway(workspace, replies):
    cfg = load_config(workspace.config_path)
    cfg.models["planner"].model = "m"  # default ships unset
    return ModelGateway(cfg, client=ScriptedChatClient(replies))


def test_explore_proposes_candidates_and_returns_brief(workspace):
    # remote_search is off by default -> the agent works the library + proposes.
    replies = [
        '{"tool":"library_search","args":{"query":"local-first"}}',
        '{"tool":"propose_source","args":{"url":"https://example.com/lf",'
        '"name":"LF Weekly","role":"blog","reason":"covers local-first"}}',
        '{"tool":"final","args":{"answer":"Local-first keeps data on-device '
        '(https://example.com/lf)."}}',
    ]
    gateway = _gateway(workspace, replies)
    with Store.open(workspace.db_path) as store:
        outcome = explore_topic(
            workspace, gateway, "local-first software", store=store, fetcher=FakeFetcher(b"")
        )

    assert outcome.remote_search is False
    assert "example.com/lf" in outcome.brief
    assert len(outcome.candidates) == 1
    assert outcome.candidates[0]["status"] == "candidate"
    assert outcome.candidates[0]["slug"] == "lf-weekly"

    # propose-don't-mutate: a pending review item, and a topic row was created.
    with Store.open(workspace.db_path) as verify:
        counts = verify.counts()
        assert counts.reviews_pending == 1
        assert counts.topics == 1
        assert [s["status"] for s in verify.list_sources()] == ["candidate"]


def test_explore_handles_web_search_disabled_gracefully(workspace):
    # The agent tries web_search first; it must get a disabled message, not crash,
    # and still be able to finish.
    replies = [
        '{"tool":"web_search","args":{"query":"local-first"}}',
        '{"tool":"final","args":{"answer":"Nothing found in the library yet."}}',
    ]
    gateway = _gateway(workspace, replies)
    with Store.open(workspace.db_path) as store:
        outcome = explore_topic(
            workspace, gateway, "local-first", store=store, fetcher=FakeFetcher(b"")
        )
    assert outcome.steps == 1  # web_search ran (returned the disabled message), then final
    assert outcome.candidates == []


def test_track_topic_marks_tracked_with_frequency(workspace):
    slug = track_topic(workspace, "Local First Software", frequency="daily")
    with Store.open(workspace.db_path) as store:
        topic = store.get_topic(slug)
    assert topic is not None
    assert topic["status"] == "tracked"
    assert json.loads(topic["discovery_policy"])["frequency"] == "daily"


def test_compile_writes_cited_document_and_records_it(workspace):
    cfg = load_config(workspace.config_path)
    cfg.models["planner"].model = "m"
    answer = "## Overview\nLocal-first keeps data on-device (https://example.com/lf)."
    reply = json.dumps({"tool": "final", "args": {"answer": answer}})
    gateway = ModelGateway(cfg, client=ScriptedChatClient([reply]))
    with Store.open(workspace.db_path) as store:
        outcome = compile_topic(
            workspace, gateway, "local-first", store=store, kind="brief", fetcher=FakeFetcher(b"")
        )
    assert outcome.output_path and outcome.output_path.endswith(".md")
    assert "Overview" in outcome.document
    assert (workspace.root / outcome.output_path).is_file()  # written under Compilations/
    with Store.open(workspace.db_path) as verify:
        assert verify.counts().compilations == 1
