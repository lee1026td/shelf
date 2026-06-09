"""Phase 5 TUI: slash dropdown, dispatch through the worker, imports.

Driven by Textual's headless ``App.run_test()`` pilot, wrapped in ``asyncio.run`` so
no pytest-asyncio dependency is needed. Fakes (no network/model) come from fixtures.
"""

from __future__ import annotations

import asyncio

from textual.widgets import Input, OptionList

from shelf.config import load_config
from shelf.services import enable_remote_search, set_model
from shelf.store import Store
from shelf.tui import ShelfApp, launch_tui
from tests.fixtures import FakeChatClient, FakeFetcher, ScriptedChatClient


def _run(coro) -> None:
    asyncio.run(coro)


async def _answer(pilot, app, text: str) -> None:
    """Wait until the session's picker is blocked on a prompt, then submit ``text``."""
    for _ in range(100):
        if app._awaiting_input:
            break
        await pilot.pause()
    app.query_one("#entry", Input).value = text
    await pilot.press("enter")
    await pilot.pause()


def test_tui_imports_are_real():
    # Replaces the old stub-gating test: the TUI is implemented now.
    assert callable(launch_tui)
    assert ShelfApp is not None


def test_slash_shows_command_palette(workspace):
    async def scenario():
        app = ShelfApp(workspace, client=FakeChatClient(), fetcher=FakeFetcher(b""))
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            assert app.query_one("#palette", OptionList).display is True
            names = {c.name for c in app._matches}
            assert {"status", "explore", "model"} <= names

    _run(scenario())


def test_palette_hidden_for_plain_text(workspace):
    async def scenario():
        app = ShelfApp(workspace, client=FakeChatClient(), fetcher=FakeFetcher(b""))
        async with app.run_test() as pilot:
            await pilot.press("h", "i")
            await pilot.pause()
            assert app.query_one("#palette", OptionList).display is False

    _run(scenario())


def test_free_text_routes_to_chat(workspace):
    set_model(workspace, "planner", model="m")
    client = FakeChatClient(reply="the answer")

    async def scenario():
        app = ShelfApp(workspace, client=client, fetcher=FakeFetcher(b""))
        async with app.run_test() as pilot:
            app.query_one("#entry", Input).value = "hello there"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

    _run(scenario())
    assert client.calls  # the message went through the gateway


def test_explore_through_tui_proposes_candidate(workspace):
    set_model(workspace, "planner", model="m")
    # Now that the TUI has a live asker, /explore's egress confirm fires when web search
    # is off; pre-enable it so this test exercises explore->candidate, not the prompt.
    enable_remote_search(workspace)
    replies = [
        '{"tool":"propose_source","args":{"url":"https://ex.com/a","name":"A","reason":"r"}}',
        '{"tool":"final","args":{"answer":"brief (https://ex.com/a)"}}',
    ]

    async def scenario():
        app = ShelfApp(workspace, client=ScriptedChatClient(replies), fetcher=FakeFetcher(b""))
        async with app.run_test() as pilot:
            app.query_one("#entry", Input).value = "/explore deep RL"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

    _run(scenario())
    with Store.open(workspace.db_path) as store:
        assert any(s["status"] == "candidate" for s in store.list_sources())


def test_model_picker_sets_custom_endpoint_through_tui(workspace):
    # The guided /model picker (role -> provider -> custom endpoint URL -> model) must be
    # reachable in the TUI, not just the line REPL. Drive it to a local custom endpoint.
    async def scenario():
        app = ShelfApp(workspace, client=FakeChatClient(), fetcher=FakeFetcher(b""))
        async with app.run_test() as pilot:
            app.query_one("#entry", Input).value = "/model"
            await pilot.press("enter")
            await _answer(pilot, app, "1")  # role: planner
            await _answer(pilot, app, "2")  # provider: Custom OpenAI-compatible endpoint
            await _answer(pilot, app, "http://localhost:8080/v1")  # custom base URL
            await _answer(pilot, app, "1")  # model: first one FakeChatClient lists
            await app.workers.wait_for_complete()
            await pilot.pause()

    _run(scenario())
    profile = load_config(workspace.config_path).models["planner"]
    assert profile.base_url == "http://localhost:8080/v1"
    assert profile.provider == "openai_compatible"
    assert profile.model == "qwen3:32b"
