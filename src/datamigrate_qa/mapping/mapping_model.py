"""Migration mapping data models."""
from __future__ import annotations

from dataclasses import dataclass, field

from datamigrate_qa.models import CanonicalType


@dataclass
class ColumnMapping:
    """Mapping between a source and target column."""
    source_column: str
    target_column: str
    canonical_type: CanonicalType | None = None
    is_manual_override: bool = False
    skip: bool = False


@dataclass
class TableMapping:
    """Mapping between a source and target table."""
    source_fqn: str
    target_fqn: str
    column_mappings: list[ColumnMapping] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    skip: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def has_primary_key(self) -> bool:
        return len(self.primary_keys) > 0

    def mapped_columns(self) -> list[ColumnMapping]:
        return [cm for cm in self.column_mappings if not cm.skip]


@dataclass
class MigrationMapping:
    """Full mapping for a migration run."""
    table_mappings: list[TableMapping] = field(default_factory=list)
    unmapped_source_tables: list[str] = field(default_factory=list)
    unmapped_target_tables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
