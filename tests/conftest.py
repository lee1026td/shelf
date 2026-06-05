"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from shelf.workspace import Workspace, initialize_workspace


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    """A freshly initialized workspace under a temp dir."""
    root = tmp_path / "ResearchLibrary"
    return initialize_workspace(root, name="ResearchLibrary")
