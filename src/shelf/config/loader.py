"""Load, save, and construct default shelf configuration.

The on-disk format is YAML at ``<workspace>/.shelf/config.yaml``. Secrets are never
written here (see ARCHITECTURE.md §9); only flags and non-sensitive endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from shelf.config.models import (
    Config,
    ModelCapabilities,
    ModelProfile,
    NotionConfig,
    PrivacyConfig,
    WorkspaceMeta,
)
from shelf.errors import ConfigError

CONFIG_FILENAME = "config.yaml"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_config(root: Path | str, name: str, created_at: str | None = None) -> Config:
    """Build the default local-only configuration for a new workspace.

    Defaults reflect the plan: Notion off, all remote egress off, and an
    OpenAI-compatible ``planner`` + ``embeddings`` profile pointed at a local
    Ollama-style endpoint (the user re-points these via ``/model`` in Phase 2).
    """
    root_str = str(Path(root))
    return Config(
        workspace=WorkspaceMeta(
            name=name,
            root=root_str,
            created_at=created_at or _utc_now_iso(),
        ),
        models={
            "planner": ModelProfile(
                provider="openai_compatible",
                base_url="http://localhost:11434/v1",
                model="qwen3:32b",
                capabilities=ModelCapabilities(
                    tools=False, json_schema="partial", vision=False, embeddings=False
                ),
            ),
            "embeddings": ModelProfile(
                provider="openai_compatible",
                base_url="http://localhost:11434/v1",
                model="nomic-embed-text",
                capabilities=ModelCapabilities(embeddings=True),
            ),
        },
        notion=NotionConfig(enabled=False, sync_mode="off"),
        privacy=PrivacyConfig(),
    )


def load_config(path: Path | str) -> Config:
    """Read and parse a ``config.yaml`` into a :class:`Config`.

    Raises :class:`ConfigError` if the file is missing or malformed.
    """
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"Config file not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - exercised via malformed input
        raise ConfigError(f"Could not parse {p}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(raw).__name__}: {p}")
    return Config.from_dict(raw)


def save_config(config: Config, path: Path | str) -> Path:
    """Serialize ``config`` to YAML at ``path`` (creating parents). Returns the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = config.to_dict()
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    p.write_text(text, encoding="utf-8")
    return p
