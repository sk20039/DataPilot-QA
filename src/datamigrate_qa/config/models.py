"""Pydantic v2 configuration models."""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field, SecretStr, field_validator


class ConnectionConfig(BaseModel):
    """Database connection configuration."""
    dialect: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: SecretStr | None = None
    account: str | None = None  # Snowflake
    schema_: str | None = Field(default=None, alias="schema")
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class TableConfig(BaseModel):
    """A source/target table pair in config."""
    source: str
    target: str
    skip: bool = False
    primary_key_override: list[str] | None = None


class GeneratorOptions(BaseModel):
    """Options for a single generator."""
    enabled: bool = True
    tolerance: float = 1e-6
    row_count_method: str = "exact"  # "exact" or "statistics"


class GeneratorsConfig(BaseModel):
    """Configuration for all generators."""
    row_count: GeneratorOptions = Field(default_factory=GeneratorOptions)
    schema: GeneratorOptions = Field(default_factory=GeneratorOptions)
    field_match: GeneratorOptions = Field(default_factory=GeneratorOptions)
    null_duplicate: GeneratorOptions = Field(default_factory=GeneratorOptions)
    aggregate_recon: GeneratorOptions = Field(default_factory=GeneratorOptions)


class OutputConfig(BaseModel):
    """Output configuration."""
    json: str | None = None
    html: str | None = None


class AppConfig(BaseModel):
    """Root application configuration."""
    source: ConnectionConfig
    target: ConnectionConfig
    tables: list[TableConfig] = Field(default_factory=list)
    generators: GeneratorsConfig = Field(default_factory=GeneratorsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    run_id: str | None = None
    max_workers: int = 4
