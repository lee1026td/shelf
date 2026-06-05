"""Dataclass config models with explicit dict (de)serialization.

We use dataclasses rather than pydantic this milestone to avoid a dependency and
v1/v2 ambiguity (see IMPLEMENTATION_PLAN.md assumption 4). Each model owns its own
``to_dict``/``from_dict`` so the YAML shape is stable and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONFIG_VERSION = 1

# Allowed Notion sync modes (plan §7.4). "off" == local-only.
SYNC_MODES = ("curated", "metadata_only", "full", "off")


@dataclass
class ModelCapabilities:
    """What an OpenAI-compatible endpoint actually supports (plan §11.1).

    ``json_schema`` may be a bool or the string ``"partial"``; the rest are bools.
    The gateway (Phase 2) must probe rather than trust these values.
    """

    tools: bool = False
    json_schema: bool | str = False
    vision: bool = False
    embeddings: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ModelCapabilities:
        data = data or {}
        return cls(
            tools=_coerce_bool(data.get("tools", False)),
            json_schema=_coerce_tristate(data.get("json_schema", False)),
            vision=_coerce_bool(data.get("vision", False)),
            embeddings=_coerce_bool(data.get("embeddings", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools": self.tools,
            "json_schema": self.json_schema,
            "vision": self.vision,
            "embeddings": self.embeddings,
        }


@dataclass
class ModelProfile:
    """A role-specific model endpoint (e.g. ``planner``, ``embeddings``)."""

    provider: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelProfile:
        return cls(
            provider=str(data.get("provider", "openai_compatible")),
            base_url=str(data.get("base_url", "")),
            model=str(data.get("model", "")),
            capabilities=ModelCapabilities.from_dict(data.get("capabilities")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "capabilities": self.capabilities.to_dict(),
        }


@dataclass
class NotionConfig:
    """Notion is an optional surface; default is local-only (``off``)."""

    enabled: bool = False
    sync_mode: str = "off"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NotionConfig:
        data = data or {}
        return cls(
            enabled=_coerce_bool(data.get("enabled", False)),
            sync_mode=_coerce_sync_mode(data.get("sync_mode", "off")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "sync_mode": self.sync_mode}


@dataclass
class PrivacyConfig:
    """Egress gates (plan §11.3). All off by default."""

    remote_search: bool = False
    remote_llm: bool = False
    remote_mcp: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PrivacyConfig:
        data = data or {}
        return cls(
            remote_search=_coerce_bool(data.get("remote_search", False)),
            remote_llm=_coerce_bool(data.get("remote_llm", False)),
            remote_mcp=_coerce_bool(data.get("remote_mcp", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_search": self.remote_search,
            "remote_llm": self.remote_llm,
            "remote_mcp": self.remote_mcp,
        }


@dataclass
class WorkspaceMeta:
    """Identity of the workspace this config belongs to."""

    name: str = ""
    root: str = ""
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WorkspaceMeta:
        data = data or {}
        return cls(
            name=str(data.get("name", "")),
            root=str(data.get("root", "")),
            created_at=str(data.get("created_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "root": self.root, "created_at": self.created_at}


@dataclass
class Config:
    """Top-level shelf configuration, persisted to ``.shelf/config.yaml``."""

    version: int = CONFIG_VERSION
    workspace: WorkspaceMeta = field(default_factory=WorkspaceMeta)
    models: dict[str, ModelProfile] = field(default_factory=dict)
    notion: NotionConfig = field(default_factory=NotionConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)

    @property
    def remote_enabled(self) -> bool:
        """True if any egress path is enabled (drives the status bar's ``remote``)."""
        return (
            self.privacy.remote_search
            or self.privacy.remote_llm
            or self.privacy.remote_mcp
            or self.notion.enabled
        )

    @property
    def planner_model(self) -> str:
        """Model id of the ``planner`` profile, or ``"none"`` if unset."""
        profile = self.models.get("planner")
        return profile.model if profile and profile.model else "none"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        models_raw = data.get("models") or {}
        models = {
            role: ModelProfile.from_dict(profile)
            for role, profile in models_raw.items()
            if isinstance(profile, dict)
        }
        return cls(
            version=int(data.get("version", CONFIG_VERSION)),
            workspace=WorkspaceMeta.from_dict(data.get("workspace")),
            models=models,
            notion=NotionConfig.from_dict(data.get("notion")),
            privacy=PrivacyConfig.from_dict(data.get("privacy")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "workspace": self.workspace.to_dict(),
            "models": {role: profile.to_dict() for role, profile in self.models.items()},
            "notion": self.notion.to_dict(),
            "privacy": self.privacy.to_dict(),
        }


def _coerce_bool(value: Any) -> bool:
    """Coerce a YAML scalar to bool, treating string ``false/no/off/""`` as False.

    Guards the same footgun as :func:`_coerce_tristate`: a hand-edited or quoted
    ``"false"``/``"off"`` must not become ``True`` via a bare ``bool()``.
    """
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "on", "1"):
            return True
        if lowered in ("false", "no", "off", "", "0"):
            return False
    return bool(value)


def _coerce_tristate(value: Any) -> bool | str:
    """Normalize a capability that may be ``True``/``False``/``"partial"``."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "partial":
            return "partial"
        if lowered in ("true", "yes", "on"):
            return True
        if lowered in ("false", "no", "off", ""):
            return False
        return value
    return bool(value)


def _coerce_sync_mode(value: Any) -> str:
    """Normalize ``sync_mode``, defending against YAML's ``off`` -> ``False``."""
    if value is False:
        return "off"
    if value is True:
        return "curated"
    text = str(value).strip().lower()
    return text if text in SYNC_MODES else "off"
