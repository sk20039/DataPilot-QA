"""Schema introspection utilities."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from datamigrate_qa.connectors.base import Connector
from datamigrate_qa.config.models import TableConfig
from datamigrate_qa.models import TableMetadata

logger = logging.getLogger(__name__)


@dataclass
class InspectionResult:
    """Result of introspecting a set of tables."""
    source_metadata: dict[str, TableMetadata]
    target_metadata: dict[str, TableMetadata]
    warnings: list[str]


def _parse_fqn(fqn: str, default_schema: str = "public") -> tuple[str, str]:
    """Split schema.table into (schema, table), falling back to default_schema."""
    parts = fqn.split(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return default_schema, fqn


def inspect_tables(
    source_connector: Connector,
    target_connector: Connector,
    table_configs: list[TableConfig],
    src_default_schema: str = "public",
    tgt_default_schema: str = "public",
) -> InspectionResult:
    """Fetch TableMetadata for all configured table pairs."""
    source_metadata: dict[str, TableMetadata] = {}
    target_metadata: dict[str, TableMetadata] = {}
    warnings: list[str] = []

    for tc in table_configs:
        if tc.skip:
            logger.info("Skipping table pair: %s -> %s", tc.source, tc.target)
            continue

        try:
            src_schema, src_table = _parse_fqn(tc.source, src_default_schema)
            src_meta = source_connector.get_table_metadata(src_schema, src_table)
            source_metadata[tc.source] = src_meta
        except Exception as exc:
            warnings.append(f"Cannot introspect source table {tc.source!r}: {exc}")
            logger.warning("Cannot introspect source table %s: %s", tc.source, exc)

        try:
            tgt_schema, tgt_table = _parse_fqn(tc.target, tgt_default_schema)
            tgt_meta = target_connector.get_table_metadata(tgt_schema, tgt_table)
            target_metadata[tc.target] = tgt_meta
        except Exception as exc:
            warnings.append(f"Cannot introspect target table {tc.target!r}: {exc}")
            logger.warning("Cannot introspect target table %s: %s", tc.target, exc)

    return InspectionResult(
        source_metadata=source_metadata,
        target_metadata=target_metadata,
        warnings=warnings,
    )
