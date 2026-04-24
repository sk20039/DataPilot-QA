"""Tests for config loading."""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from datamigrate_qa.config.loader import load_config
from datamigrate_qa.config.models import AppConfig


def test_load_minimal_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""
            source:
              dialect: postgresql
              host: localhost
              port: 5432
              database: source_db
              username: user
              password: secret
            target:
              dialect: postgresql
              host: localhost
              port: 5433
              database: target_db
              username: user
              password: secret
            tables:
              - source: public.orders
                target: public.orders
        """)
    )
    config = load_config(config_file)
    assert isinstance(config, AppConfig)
    assert config.source.dialect == "postgresql"
    assert config.target.dialect == "postgresql"
    assert len(config.tables) == 1
    assert config.tables[0].source == "public.orders"


def test_env_var_substitution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PASS", "supersecret")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""
            source:
              dialect: postgresql
              host: localhost
              database: mydb
              username: user
              password: ${DB_PASS}
            target:
              dialect: postgresql
              host: remotehost
              database: mydb
              username: user
              password: ${DB_PASS}
        """)
    )
    config = load_config(config_file)
    assert config.source.password is not None
    assert config.source.password.get_secret_value() == "supersecret"


def test_missing_env_var_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""
            source:
              dialect: postgresql
              host: localhost
              database: mydb
              username: user
              password: ${DOES_NOT_EXIST_XYZ}
            target:
              dialect: postgresql
              host: localhost
              database: mydb
              username: user
        """)
    )
    with pytest.raises(ValueError, match="DOES_NOT_EXIST_XYZ"):
        load_config(config_file)


def test_missing_config_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.yaml")
