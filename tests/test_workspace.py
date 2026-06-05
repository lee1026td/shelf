"""Workspace initialization, idempotency, and discovery."""

from __future__ import annotations

import pytest

from shelf.errors import WorkspaceExists, WorkspaceNotFound
from shelf.workspace import Workspace, initialize_workspace, resolve_workspace
from shelf.workspace.layout import ALL_DIRS, LEDGER_FILES


def test_init_creates_full_layout(tmp_path):
    ws = initialize_workspace(tmp_path / "lib", name="lib")
    assert ws.exists()
    for relative in ALL_DIRS:
        assert (ws.root / relative).is_dir(), f"missing dir: {relative}"
    for ledger in LEDGER_FILES:
        assert (ws.root / ledger).is_file(), f"missing ledger: {ledger}"
    assert ws.config_path.is_file()
    assert ws.db_path.is_file()
    assert ws.jobs_db_path.is_file()
    assert ws.dashboard.is_file()
    assert "lib" in ws.dashboard.read_text(encoding="utf-8")


def test_reinit_without_force_raises(tmp_path):
    initialize_workspace(tmp_path / "lib", name="lib")
    with pytest.raises(WorkspaceExists):
        initialize_workspace(tmp_path / "lib", name="lib")


def test_force_preserves_edited_files(tmp_path):
    ws = initialize_workspace(tmp_path / "lib", name="lib")
    ws.dashboard.write_text("EDITED BY USER", encoding="utf-8")
    initialize_workspace(tmp_path / "lib", name="lib", force=True)
    assert ws.dashboard.read_text(encoding="utf-8") == "EDITED BY USER"


def test_discover_from_subdirectory(tmp_path):
    ws = initialize_workspace(tmp_path / "lib", name="lib")
    nested = ws.root / "Topics" / "Some Topic"
    nested.mkdir(parents=True, exist_ok=True)
    found = Workspace.discover(start=nested, env={})
    assert found is not None
    assert found.root == ws.root


def test_discover_via_shelf_home(tmp_path):
    ws = initialize_workspace(tmp_path / "lib", name="lib")
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    found = Workspace.discover(start=unrelated, env={"SHELF_HOME": str(ws.root)})
    assert found is not None
    assert found.root == ws.root


def test_discover_returns_none_when_absent(tmp_path):
    assert Workspace.discover(start=tmp_path, env={}) is None


def test_resolve_explicit_missing_raises(tmp_path):
    with pytest.raises(WorkspaceNotFound):
        resolve_workspace(explicit=tmp_path / "nope")
