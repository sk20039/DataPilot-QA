"""TestGenerator Protocol definition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from datamigrate_qa.config.models import GeneratorOptions
from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import TestCase


@dataclass
class GeneratorConfig:
    """Configuration passed to each generator."""
    options: GeneratorOptions


@runtime_checkable
class TestGenerator(Protocol):
    """Protocol that all test generators must implement."""

    @property
    def category(self) -> str: ...

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]: ...
