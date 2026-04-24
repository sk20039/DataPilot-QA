"""Automatic column mapping: exact match then case-insensitive."""
from __future__ import annotations

import logging

from datamigrate_qa.config.models import TableConfig
from datamigrate_qa.models import TableMetadata

from .mapping_model import ColumnMapping, MigrationMapping, TableMapping

logger = logging.getLogger(__name__)


def _map_columns(
    src_meta: TableMetadata,
    tgt_meta: TableMetadata,
) -> tuple[list[ColumnMapping], list[str]]:
    """Map columns from source to target. Returns (mappings, warnings)."""
    warnings: list[str] = []
    mappings: list[ColumnMapping] = []

    target_by_name: dict[str, str] = {col.name: col.name for col in tgt_meta.columns}
    target_by_lower: dict[str, str] = {col.name.lower(): col.name for col in tgt_meta.columns}
    src_type_by_name = {col.name: col.canonical_type for col in src_meta.columns}
    matched_targets: set[str] = set()

    for src_col in src_meta.columns:
        # Exact match
        if src_col.name in target_by_name:
            mappings.append(ColumnMapping(source_column=src_col.name, target_column=src_col.name, canonical_type=src_type_by_name.get(src_col.name)))
            matched_targets.add(src_col.name)
        # Case-insensitive match
        elif src_col.name.lower() in target_by_lower:
            tgt_col_name = target_by_lower[src_col.name.lower()]
            mappings.append(ColumnMapping(source_column=src_col.name, target_column=tgt_col_name, canonical_type=src_type_by_name.get(src_col.name)))
            matched_targets.add(tgt_col_name)
        else:
            warnings.append(
                f"Source column {src_meta.fqn}.{src_col.name!r} has no match in target"
            )
            mappings.append(ColumnMapping(source_column=src_col.name, target_column="", skip=True))

    for tgt_col in tgt_meta.columns:
        if tgt_col.name not in matched_targets:
            warnings.append(
                f"Target column {tgt_meta.fqn}.{tgt_col.name!r} has no match in source"
            )

    return mappings, warnings


def build_mapping(
    table_configs: list[TableConfig],
    source_metadata: dict[str, TableMetadata],
    target_metadata: dict[str, TableMetadata],
) -> MigrationMapping:
    """Build a MigrationMapping from source/target metadata."""
    table_mappings: list[TableMapping] = []
    global_warnings: list[str] = []

    for tc in table_configs:
        if tc.skip:
            continue

        src_meta = source_metadata.get(tc.source)
        tgt_meta = target_metadata.get(tc.target)

        if src_meta is None:
            global_warnings.append(f"No source metadata for {tc.source!r} — skipping mapping")
            continue
        if tgt_meta is None:
            global_warnings.append(f"No target metadata for {tc.target!r} — skipping mapping")
            continue

        column_mappings, col_warnings = _map_columns(src_meta, tgt_meta)

        # Use source PKs for field-level comparison
        primary_keys = src_meta.primary_keys

        table_mapping = TableMapping(
            source_fqn=src_meta.fqn,
            target_fqn=tgt_meta.fqn,
            column_mappings=column_mappings,
            primary_keys=primary_keys,
            warnings=col_warnings,
        )

        if not table_mapping.has_primary_key:
            table_mapping.warnings.append(
                f"Table {tc.source!r} has no primary key — field-level comparison will be skipped"
            )
            logger.warning("Table %s has no primary key", tc.source)

        table_mappings.append(table_mapping)

    return MigrationMapping(
        table_mappings=table_mappings,
        warnings=global_warnings,
    )
