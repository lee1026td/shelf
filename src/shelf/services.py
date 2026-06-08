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
from shelf.util import slugify
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


def enable_remote_llm(workspace: Workspace) -> None:
    """Turn on the remote-LLM egress gate (``privacy.remote_llm``) and persist it.

    The model picker calls this only after the user explicitly confirms sending
    library content off-machine (product principle 5: egress is visible).
    """
    config = load_config(workspace.config_path)
    config.privacy.remote_llm = True
    save_config(config, workspace.config_path)


def enable_remote_search(workspace: Workspace) -> None:
    """Turn on the remote web-search egress gate (``privacy.remote_search``) and persist it.

    Called by ``/explore`` only after the user explicitly confirms sending their query
    to a web search engine (product principle 5: egress is visible).
    """
    config = load_config(workspace.config_path)
    config.privacy.remote_search = True
    save_config(config, workspace.config_path)


def track_topic(workspace: Workspace, topic: str, *, frequency: str = "weekly") -> str:
    """Promote a topic to *tracked* with a refresh frequency. Returns the topic slug.

    This is the Phase-3 half of ``/track``: it records intent (status + discovery
    policy). It does NOT auto-watch sources — the watchlist still grows only through
    the review queue (principle 3), and actual periodic collection is the Phase-4
    watcher's job. Idempotent: re-tracking just updates the frequency.
    """
    slug = slugify(topic, fallback="topic")
    with Store.open(workspace.db_path) as store:
        store.ensure_topic(topic, slug, intent=topic)
        store.set_topic_tracking(slug, status="tracked", discovery_policy={"frequency": frequency})
    return slug
