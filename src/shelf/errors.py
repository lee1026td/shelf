"""Error hierarchy for shelf.

The CLI catches :class:`ShelfError` and renders a clean, user-facing message
instead of a traceback (see ``shelf.cli.app``). Stubbed, not-yet-built features
raise :class:`FeatureNotReady`, which carries the phase that will deliver them.
"""

from __future__ import annotations


class ShelfError(Exception):
    """Base class for all expected, user-facing shelf errors."""


class WorkspaceError(ShelfError):
    """Problems locating or creating a workspace."""


class WorkspaceNotFound(WorkspaceError):
    """No initialized shelf workspace could be found.

    Raised when a command needs a workspace but none was supplied or discovered.
    """

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "No shelf workspace found. Run `shelf init <path>` to create one, "
            "or pass `--workspace <path>`."
        )


class WorkspaceExists(WorkspaceError):
    """The init target is already an initialized workspace."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"A shelf workspace already exists at {path!r}. "
            "Re-run with `--force` to re-initialize it."
        )


class ConfigError(ShelfError):
    """Invalid or unreadable configuration."""


class IngestionError(ShelfError):
    """A problem fetching, parsing, or importing content."""


class FetchError(IngestionError):
    """Could not retrieve a URL."""


class UnsupportedContentError(IngestionError):
    """The content type / file extension is not supported."""


class LLMError(ShelfError):
    """A problem configuring or calling the model gateway."""


class ToolError(ShelfError):
    """A tool could not run (bad args, unavailable, or handler failure).

    The agent loop catches these and feeds the message back to the model as an
    observation, so a single bad tool call doesn't abort the whole run.
    """


class AgentError(ShelfError):
    """The agent loop could not make progress (e.g. no model, repeated parse failures)."""


class FeatureNotReady(NotImplementedError, ShelfError):
    """A feature that is intentionally stubbed for a later phase was invoked.

    Subclasses ``NotImplementedError`` so tests can assert on either type, and
    ``ShelfError`` so the CLI renders it as a friendly notice rather than crashing.
    """

    def __init__(self, feature: str, phase: int, detail: str | None = None) -> None:
        self.feature = feature
        self.phase = phase
        msg = f"{feature} is not implemented yet - planned for Phase {phase}."
        if detail:
            msg = f"{msg} {detail}"
        super().__init__(msg)
