"""Manual mapping overrides from YAML."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .mapping_model import ColumnMapping, MigrationMapping, TableMapping

logger = logging.getLogger(__name__)


def apply_yaml_overrides(
    migration_mapping: MigrationMapping,
    override_path: str | Path,
) -> MigrationMapping:
    """Apply manual column overrides from a YAML file."""
    path = Path(override_path)
    if not path.exists():
        raise FileNotFoundError(f"Override file not found: {override_path}")

    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    overrides: list[dict[str, Any]] = data.get("overrides", [])

    override_index: dict[str, dict[str, Any]] = {
        item["source_table"]: item for item in overrides if "source_table" in item
    }

    for table_mapping in migration_mapping.table_mappings:
        if table_mapping.source_fqn not in override_index:
            continue

        override = override_index[table_mapping.source_fqn]
        col_overrides: dict[str, dict[str, Any]] = {
            co["source"]: co for co in override.get("columns", [])
        }

        new_mappings: list[ColumnMapping] = []
        for cm in table_mapping.column_mappings:
            if cm.source_column in col_overrides:
                co = col_overrides[cm.source_column]
                new_mappings.append(
                    ColumnMapping(
                        source_column=cm.source_column,
                        target_column=co.get("target", cm.target_column),
                        is_manual_override=True,
                        skip=co.get("skip", False),
                    )
                )
                logger.info("Override applied: %s.%s -> %s", table_mapping.source_fqn, cm.source_column, co.get("target"))
            else:
                new_mappings.append(cm)

        # Add any new column mappings defined in overrides
        existing_sources = {cm.source_column for cm in table_mapping.column_mappings}
        for src_col, co in col_overrides.items():
            if src_col not in existing_sources:
                new_mappings.append(
                    ColumnMapping(
                        source_column=src_col,
                        target_column=co.get("target", ""),
                        is_manual_override=True,
                        skip=co.get("skip", False),
                    )
                )

        table_mapping.column_mappings = new_mappings

        # Override primary keys if specified
        if "primary_keys" in override:
            table_mapping.primary_keys = override["primary_keys"]

        if "skip" in override:
            table_mapping.skip = override["skip"]

    return migration_mapping
