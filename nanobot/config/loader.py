"""Configuration loading utilities."""

import json
import os
from pathlib import Path
from typing import Any

from nanobot.config.schema import Config


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".nanobot" / "config.json"


def get_data_dir() -> Path:
    """Get the nanobot data directory."""
    from nanobot.utils.helpers import get_data_path
    return get_data_path()


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.
    
    Args:
        config_path: Optional path to config file. Uses default if not provided.
    
    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()
    
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            data = _migrate_config(data)
            data = convert_keys(data)
            # Env override for Docker/deploy (e.g. NANOBOT_CHANNELS__WHATSAPP__BRIDGE_URL=ws://bridge:3001)
            bridge_url = os.environ.get("NANOBOT_CHANNELS__WHATSAPP__BRIDGE_URL")
            if bridge_url and isinstance(data.get("channels"), dict) and isinstance(data["channels"].get("whatsapp"), dict):
                data["channels"]["whatsapp"]["bridge_url"] = bridge_url
            # Opção B: chaves dos providers via .env (não colar no config.json)
            _apply_provider_env_overrides(data)
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")
    
    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.
    
    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to camelCase format
    data = config.model_dump()
    data = convert_to_camel(data)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _apply_provider_env_overrides(data: dict) -> None:
    """Override provider API keys from env (NANOBOT_PROVIDERS__DEEPSEEK__API_KEY, etc.)."""
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return
    env_keys = (
        ("deepseek", "NANOBOT_PROVIDERS__DEEPSEEK__API_KEY"),
        ("xiaomi", "NANOBOT_PROVIDERS__XIAOMI__API_KEY"),
        ("openrouter", "NANOBOT_PROVIDERS__OPENROUTER__API_KEY"),
    )
    for key, env_var in env_keys:
        val = os.environ.get(env_var)
        if val is not None and key in providers and isinstance(providers[key], dict):
            providers[key]["api_key"] = val.strip()


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
    # Channels: only WhatsApp is supported; drop telegram, discord, feishu
    channels = data.get("channels", {})
    for key in ("telegram", "discord", "feishu"):
        channels.pop(key, None)
    # Web tools (search/fetch) removed; drop tools.web
    tools.pop("web", None)
    # File/shell tools removed; drop tools.exec and tools.restrictToWorkspace
    tools.pop("exec", None)
    tools.pop("restrictToWorkspace", None)
    return data


def convert_keys(data: Any) -> Any:
    """Convert camelCase keys to snake_case for Pydantic."""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """Convert snake_case keys to camelCase."""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
