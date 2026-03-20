"""Configuration module for zappelin."""


from zapista.config.loader import load_config, get_config_path
from zapista.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
