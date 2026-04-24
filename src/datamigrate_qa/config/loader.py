"""YAML config loader with env var substitution."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from .models import AppConfig


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _substitute_env_vars(text: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            raise ValueError(f"Environment variable '{var_name}' is not set")
        return value
    return _ENV_VAR_PATTERN.sub(replace, text)


def _resolve_secret_files(obj: object) -> object:
    """Recursively resolve secret_file: references."""
    if isinstance(obj, dict):
        result: dict[str, object] = {}
        for k, v in obj.items():
            if k == "secret_file" and isinstance(v, str):
                secret_path = Path(v)
                if not secret_path.exists():
                    raise ValueError(f"Secret file not found: {v}")
                return secret_path.read_text().strip()
            result[k] = _resolve_secret_files(v)
        return result
    if isinstance(obj, list):
        return [_resolve_secret_files(item) for item in obj]
    return obj


def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw_text = path.read_text()
    substituted = _substitute_env_vars(raw_text)
    data = yaml.safe_load(substituted)
    data = _resolve_secret_files(data)
    return AppConfig.model_validate(data)
