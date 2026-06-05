"""Status report rendering and the canonical status-bar line."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from shelf.store import LibraryCounts
from shelf.ui.status_view import StatusReport, render_status, status_bar_line


def _report(remote: bool = False) -> StatusReport:
    return StatusReport(
        workspace_root=Path("/var/data/ResearchLibrary"),
        workspace_name="ResearchLibrary",
        model="qwen3:32b",
        remote_enabled=remote,
        notion_sync_mode="off",
        schema_version=1,
        counts=LibraryCounts(sources=42, items=20, inbox=18, reviews_pending=5),
    )


def test_status_bar_segments():
    line = status_bar_line(_report())
    assert line.startswith("[Shelf: ")
    assert "[model: qwen3:32b]" in line
    assert "[remote: off]" in line
    assert "[sources: 42]" in line
    assert "[inbox: 18]" in line
    assert "[review: 5]" in line


def test_status_bar_remote_on():
    assert "[remote: on]" in status_bar_line(_report(remote=True))


def test_status_bar_abbreviates_home():
    home = Path.home()
    report = StatusReport(
        workspace_root=home / "ResearchLibrary",
        workspace_name="ResearchLibrary",
        model="m",
        remote_enabled=False,
        notion_sync_mode="off",
        schema_version=1,
        counts=LibraryCounts(),
    )
    assert "[Shelf: ~/ResearchLibrary]" in status_bar_line(report)


def test_render_status_outputs_panel_and_bar():
    console = Console(record=True, width=120)
    render_status(console, _report())
    out = console.export_text()
    assert "shelf status" in out
    assert "[sources: 42]" in out
    assert "[review: 5]" in out
