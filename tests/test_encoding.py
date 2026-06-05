"""Guard the ASCII-only contract for console-reachable text.

These prevent regressions of the cp949 crash class: any string that reaches the
console (error/notice messages, CLI help, command docstrings) must be ASCII so it
never raises ``UnicodeEncodeError`` on a non-UTF-8 Windows code page.
"""

from __future__ import annotations

import io
import sys

from shelf.cli.app import app
from shelf.errors import FeatureNotReady, WorkspaceExists, WorkspaceNotFound
from shelf.ui.console import ensure_safe_streams


def test_feature_not_ready_messages_are_ascii():
    for phase in range(1, 8):
        msg = str(FeatureNotReady("some feature", phase))
        assert msg.isascii(), repr(msg)


def test_workspace_error_messages_are_ascii():
    assert str(WorkspaceNotFound()).isascii()
    assert str(WorkspaceExists("/some/path")).isascii()


def test_command_help_and_docstrings_are_ascii():
    # Command-level help= strings and command function docstrings.
    for command in app.registered_commands:
        if command.help:
            assert command.help.isascii(), repr(command.help)
        doc = (command.callback.__doc__ or "") if command.callback else ""
        assert doc.isascii(), repr(doc)
    # The main callback docstring (shown by `shelf --help`).
    callback = app.registered_callback
    if callback and callback.callback and callback.callback.__doc__:
        assert callback.callback.__doc__.isascii(), repr(callback.callback.__doc__)


def _combined_output(result) -> str:
    """stdout + stderr, robust across click versions (stderr may be merged or split)."""
    out = result.output or ""
    err = result.stderr if getattr(result, "stderr_bytes", None) else ""
    return out + err


def test_ensure_safe_streams_flips_error_handler(monkeypatch):
    # A strict cp949 stream would raise on non-cp949 content; ensure_safe_streams
    # must switch it to backslashreplace so ingested content degrades, not crashes.
    cp949_stream = io.TextIOWrapper(io.BytesIO(), encoding="cp949", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp949_stream)
    monkeypatch.setattr(sys, "stderr", cp949_stream)
    ensure_safe_streams()
    assert sys.stdout.errors == "backslashreplace"
    sys.stdout.write("cafe ✓ 안녕")  # non-cp949 chars -> must not raise
    sys.stdout.flush()


def test_ensure_safe_streams_noop_on_plain_stream(monkeypatch):
    # A StringIO has no reconfigure(); ensure_safe_streams must be a safe no-op.
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    ensure_safe_streams()


def test_chat_runtime_output_is_ascii(runner):
    # chat's placeholder notice is the user-facing output for a stub-ish command;
    # it routes through err_console, so check both streams.
    result = runner.invoke(app, ["chat"])
    combined = _combined_output(result)
    assert combined  # the notice was actually emitted somewhere
    assert combined.isascii(), repr(combined)
