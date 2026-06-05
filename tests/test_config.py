"""Config defaults and YAML round-trip."""

from __future__ import annotations

from shelf.config import default_config, load_config, save_config
from shelf.config.models import Config, ModelCapabilities


def test_default_config_is_local_only(tmp_path):
    cfg = default_config(tmp_path, "Lib")
    assert cfg.version == 1
    assert cfg.notion.enabled is False
    assert cfg.notion.sync_mode == "off"
    assert cfg.privacy.remote_search is False
    assert cfg.privacy.remote_llm is False
    assert cfg.privacy.remote_mcp is False
    assert cfg.remote_enabled is False
    assert set(cfg.models) == {"planner", "embeddings"}
    assert cfg.planner_model == "qwen3:32b"
    # The "OpenAI-compatible" part of acceptance criterion C.
    assert cfg.models["planner"].provider == "openai_compatible"
    assert cfg.models["embeddings"].provider == "openai_compatible"
    assert cfg.models["planner"].base_url
    assert cfg.models["embeddings"].capabilities.embeddings is True
    assert cfg.models["planner"].capabilities.json_schema == "partial"


def test_capabilities_string_booleans_coerced():
    """A hand-edited/quoted 'false'/'off'/'no' must not read as True."""
    caps = ModelCapabilities.from_dict(
        {"tools": "false", "vision": "off", "embeddings": "no", "json_schema": "partial"}
    )
    assert caps.tools is False
    assert caps.vision is False
    assert caps.embeddings is False
    assert caps.json_schema == "partial"
    truthy = ModelCapabilities.from_dict({"tools": "true", "embeddings": "yes"})
    assert truthy.tools is True
    assert truthy.embeddings is True


def test_config_round_trip(tmp_path):
    cfg = default_config(tmp_path, "Lib")
    path = tmp_path / ".shelf" / "config.yaml"
    save_config(cfg, path)
    loaded = load_config(path)
    # Full structural equality via the serialized form.
    assert loaded.to_dict() == cfg.to_dict()


def test_sync_mode_off_survives_yaml(tmp_path):
    """YAML parses bare `off` as False; we must keep it the string 'off'."""
    cfg = default_config(tmp_path, "Lib")
    path = tmp_path / "config.yaml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.notion.sync_mode == "off"


def test_remote_enabled_reflects_privacy(tmp_path):
    cfg = default_config(tmp_path, "Lib")
    cfg.privacy.remote_llm = True
    assert cfg.remote_enabled is True


def test_planner_model_none_when_unset():
    cfg = Config()
    assert cfg.planner_model == "none"
    assert cfg.remote_enabled is False
