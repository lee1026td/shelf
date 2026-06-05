"""End-to-end CLI behavior via Typer's CliRunner."""

from __future__ import annotations

from shelf import __version__
from shelf.cli.app import app
from shelf.store import Store
from shelf.workspace import resolve_workspace


def test_help_lists_commands(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output


def test_version_command(runner):
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_flag(runner):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_then_status(runner, tmp_path):
    lib = tmp_path / "lib"
    init_result = runner.invoke(app, ["init", str(lib)])
    assert init_result.exit_code == 0, init_result.output
    assert (lib / ".shelf").is_dir()

    status_result = runner.invoke(app, ["status", "--workspace", str(lib)])
    assert status_result.exit_code == 0, status_result.output
    out = status_result.output
    assert "[Shelf: " in out
    assert "[model: qwen3:32b]" in out
    assert "[remote: off]" in out
    assert "[sources: 0]" in out
    assert "[review: 0]" in out


def test_init_refuses_existing_without_force(runner, tmp_path):
    lib = tmp_path / "lib"
    assert runner.invoke(app, ["init", str(lib)]).exit_code == 0
    second = runner.invoke(app, ["init", str(lib)])
    assert second.exit_code == 1


def test_init_force_reinitializes(runner, tmp_path):
    lib = tmp_path / "lib"
    runner.invoke(app, ["init", str(lib)])
    forced = runner.invoke(app, ["init", str(lib), "--force"])
    assert forced.exit_code == 0, forced.output


def test_status_reflects_nonzero_counts(runner, tmp_path):
    """Acceptance criterion E: counts shown reflect the store, end-to-end."""
    lib = tmp_path / "lib"
    assert runner.invoke(app, ["init", str(lib)]).exit_code == 0
    ws = resolve_workspace(explicit=lib)
    with Store.open(ws.db_path) as store:
        store.add_source("a", "https://a", status="watched")
        store.add_source("b", "https://b", status="candidate")
        store.add_item(title="new one", status="new")
        store.add_item(title="saved one", status="saved")
        store.connection.execute(
            "INSERT INTO review_items(type, priority, status, created_at, updated_at) "
            "VALUES('source_candidate', 'high', 'pending', 't', 't')"
        )

    result = runner.invoke(app, ["status", "--workspace", str(lib)])
    assert result.exit_code == 0, result.output
    assert "[sources: 2]" in result.output
    assert "[inbox: 1]" in result.output  # only the status='new' item
    assert "[review: 1]" in result.output


def test_status_on_missing_db_fails_cleanly(runner, tmp_path):
    """A present .shelf/ marker with a missing DB must not raise a raw traceback."""
    lib = tmp_path / "lib"
    runner.invoke(app, ["init", str(lib)])
    ws = resolve_workspace(explicit=lib)
    ws.db_path.unlink()  # remove library.sqlite but keep the .shelf/ marker

    result = runner.invoke(app, ["status", "--workspace", str(lib)])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_status_without_workspace_fails_cleanly(runner, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["status", "--workspace", str(empty)])
    assert result.exit_code == 1
    # A clean Exit, not an unhandled crash.
    assert not isinstance(result.exception, Exception) or isinstance(
        result.exception, SystemExit
    )


def test_bare_shelf_enters_repl_in_workspace(runner, workspace):
    result = runner.invoke(
        app, [], input="/status\n/exit\n", env={"SHELF_HOME": str(workspace.root)}
    )
    assert result.exit_code == 0, result.output
    assert "shelf REPL" in result.output
    assert "[sources: 0]" in result.output


def test_bare_shelf_outside_workspace_hints(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # empty dir, no .shelf anywhere up the tree
    result = runner.invoke(app, [], env={"SHELF_HOME": ""})
    assert result.exit_code == 0
    assert "No shelf workspace" in result.output


def test_chat_enters_repl(runner, workspace):
    result = runner.invoke(
        app, ["chat"], input="/exit\n", env={"SHELF_HOME": str(workspace.root)}
    )
    assert result.exit_code == 0, result.output
    assert "shelf REPL" in result.output


def test_inbox_search_sources_cli(runner, tmp_path):
    lib = tmp_path / "lib"
    assert runner.invoke(app, ["init", str(lib)]).exit_code == 0
    ws = resolve_workspace(explicit=lib)
    with Store.open(ws.db_path) as store:
        store.add_source("example", "https://example.com", status="watched")
        store.add_item(title="Findable Title", url="https://example.com/1", status="new")

    inbox = runner.invoke(app, ["inbox", "--workspace", str(lib)])
    assert inbox.exit_code == 0, inbox.output
    assert "Findable Title" in inbox.output

    search = runner.invoke(app, ["search", "Findable", "--workspace", str(lib)])
    assert search.exit_code == 0, search.output
    assert "Findable Title" in search.output

    sources = runner.invoke(app, ["sources", "--workspace", str(lib)])
    assert sources.exit_code == 0, sources.output
    assert "example" in sources.output
