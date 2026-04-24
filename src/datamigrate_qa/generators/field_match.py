"""Hash-based field-level matching test generator."""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)


def _build_hash_sql(fqn: str, pk_cols: list[str], data_cols: list[str]) -> str:
    """Build hash aggregation SQL pushed into the DB."""
    pk_expr = " || '|' || ".join(f"COALESCE({col}::TEXT, 'NULL')" for col in pk_cols)
    col_exprs = " || '|' || ".join(f"COALESCE({col}::TEXT, 'NULL')" for col in data_cols)
    hash_expr = f"MD5({pk_expr} || '|' || {col_exprs})" if data_cols else f"MD5({pk_expr})"
    return f"SELECT {hash_expr} AS row_hash, COUNT(*) FROM {fqn} GROUP BY row_hash ORDER BY row_hash"


class FieldMatchGenerator:
    """Generates hash-based field matching test cases, skips tables without PKs."""

    @property
    def category(self) -> str:
        return "field_match"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []

        for table_mapping in mapping.table_mappings:
            if table_mapping.skip:
                continue

            if not table_mapping.has_primary_key:
                logger.warning(
                    "Skipping field_match for %s: no primary key", table_mapping.source_fqn
                )
                continue

            active_mappings = table_mapping.mapped_columns()
            if not active_mappings:
                continue

            src_data_cols = [cm.source_column for cm in active_mappings if cm.source_column not in table_mapping.primary_keys]
            tgt_data_cols = [cm.target_column for cm in active_mappings if cm.target_column not in table_mapping.primary_keys]

            source_sql = _build_hash_sql(table_mapping.source_fqn, table_mapping.primary_keys, src_data_cols)
            target_sql = _build_hash_sql(table_mapping.target_fqn, table_mapping.primary_keys, tgt_data_cols)

            test_cases.append(
                TestCase(
                    category=self.category,
                    table_pair=TablePair(
                        source_fqn=table_mapping.source_fqn,
                        target_fqn=table_mapping.target_fqn,
                    ),
                    source_sql=source_sql,
                    target_sql=target_sql,
                    comparison_strategy=ComparisonStrategy.SET_EQUALITY,
                    description=f"Field hash match: {table_mapping.source_fqn} vs {table_mapping.target_fqn}",
                )
            )

        return test_cases
