"""Deferred features expose stable interfaces that raise FeatureNotReady."""

from __future__ import annotations

import pytest

from shelf.errors import FeatureNotReady, ShelfError
from shelf.mcp import McpRegistry, McpServer
from shelf.notion import NotionAdapter
from shelf.tui import ShelfTUI, launch_tui
from shelf.watcher import WatcherDaemon


def test_feature_not_ready_is_shelf_and_notimplemented():
    assert issubclass(FeatureNotReady, ShelfError)
    assert issubclass(FeatureNotReady, NotImplementedError)


STUBS = [
    # Phase 3 (discovery / `/explore`) is now implemented — see test_discovery.py.
    (lambda: WatcherDaemon().run_once(), 4),
    (lambda: WatcherDaemon().start(), 4),
    (lambda: launch_tui(), 5),
    (lambda: ShelfTUI().run(), 5),
    (lambda: NotionAdapter().sync(), 6),
    (lambda: NotionAdapter().import_reviews(), 6),
    (lambda: McpRegistry().register(McpServer("s", "stdio", "e")), 7),
    (lambda: McpRegistry().list_servers(), 7),
]


@pytest.mark.parametrize("call, phase", STUBS)
def test_stub_raises_with_phase(call, phase):
    with pytest.raises(FeatureNotReady) as excinfo:
        call()
    assert excinfo.value.phase == phase
