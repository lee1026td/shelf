"""Configuration models and YAML (de)serialization for shelf."""

from __future__ import annotations

from shelf.config.loader import (
    CONFIG_FILENAME,
    default_config,
    load_config,
    save_config,
)
from shelf.config.models import (
    CONFIG_VERSION,
    Config,
    ModelCapabilities,
    ModelProfile,
    NotionConfig,
    PrivacyConfig,
    WorkspaceMeta,
)

__all__ = [
    "CONFIG_FILENAME",
    "CONFIG_VERSION",
    "Config",
    "ModelCapabilities",
    "ModelProfile",
    "NotionConfig",
    "PrivacyConfig",
    "WorkspaceMeta",
    "default_config",
    "load_config",
    "save_config",
]
