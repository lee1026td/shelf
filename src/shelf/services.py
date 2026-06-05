"""Application services shared by the CLI and the REPL.

This sits above the store/config/workspace layers and below the presentation
(`ui`, `cli`, `repl`) layers, so both `shelf status` and the REPL's `/status` build
the same :class:`StatusReport` from one place.
"""

from __future__ import annotations

from shelf.config import ModelProfile, load_config, save_config
from shelf.errors import WorkspaceError
from shelf.store import Store
from shelf.ui.status_view import StatusReport
from shelf.workspace import Workspace


def gather_status(workspace: Workspace) -> StatusReport:
    """Open the workspace's config + store and assemble a status report.

    Raises :class:`WorkspaceError` if the workspace marker exists but the SQLite
    schema is missing (uninitialized/corrupt DB).
    """
    config = load_config(workspace.config_path)
    with Store.open(workspace.db_path) as store:
        if not store.is_initialized():
            raise WorkspaceError(
                f"Workspace at {workspace.root} looks uninitialized or corrupted "
                "(library.sqlite has no schema). Re-run `shelf init --force`."
            )
        counts = store.counts()
        schema_version = store.schema_version
    return StatusReport(
        workspace_root=workspace.root,
        workspace_name=config.workspace.name or workspace.root.name,
        model=config.planner_model,
        remote_enabled=config.remote_enabled,
        notion_sync_mode=config.notion.sync_mode,
        schema_version=schema_version,
        counts=counts,
    )


def set_model(
    workspace: Workspace,
    role: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    provider: str | None = None,
) -> ModelProfile:
    """Update a model role profile in config.yaml and persist it.

    Works for any role (``planner``, ``embeddings``, ...). Only the fields passed are
    changed; the rest of the profile (e.g. base_url, capabilities) is preserved.
    """
    config = load_config(workspace.config_path)
    profile = config.models.get(role) or ModelProfile()
    if model is not None:
        profile.model = model
    if base_url is not None:
        profile.base_url = base_url
    if provider is not None:
        profile.provider = provider
    config.models[role] = profile
    save_config(config, workspace.config_path)
    return profile
