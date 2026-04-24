"""Null and duplicate check test generator."""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)


class NullDuplicateGenerator:
    """Generates null count and duplicate check test cases."""

    @property
    def category(self) -> str:
        return "null_duplicate"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []

        for table_mapping in mapping.table_mappings:
            if table_mapping.skip:
                continue

            # Duplicate check using PK
            if table_mapping.has_primary_key:
                pk_cols = ", ".join(table_mapping.primary_keys)
                src_dup_sql = f"SELECT COUNT(*) FROM (SELECT {pk_cols}, COUNT(*) AS cnt FROM {table_mapping.source_fqn} GROUP BY {pk_cols} HAVING COUNT(*) > 1) t"
                tgt_dup_sql = f"SELECT COUNT(*) FROM (SELECT {pk_cols}, COUNT(*) AS cnt FROM {table_mapping.target_fqn} GROUP BY {pk_cols} HAVING COUNT(*) > 1) t"

                test_cases.append(
                    TestCase(
                        category=self.category,
                        table_pair=TablePair(
                            source_fqn=table_mapping.source_fqn,
                            target_fqn=table_mapping.target_fqn,
                        ),
                        source_sql=src_dup_sql,
                        target_sql=tgt_dup_sql,
                        comparison_strategy=ComparisonStrategy.EXACT,
                        description=f"Duplicate PK check: {table_mapping.source_fqn}",
                    )
                )

            # Null count for each mapped column
            for cm in table_mapping.mapped_columns():
                src_null_sql = f"SELECT COUNT(*) FROM {table_mapping.source_fqn} WHERE {cm.source_column} IS NULL"
                tgt_null_sql = f"SELECT COUNT(*) FROM {table_mapping.target_fqn} WHERE {cm.target_column} IS NULL"
                test_cases.append(
                    TestCase(
                        category=self.category,
                        table_pair=TablePair(
                            source_fqn=table_mapping.source_fqn,
                            target_fqn=table_mapping.target_fqn,
                        ),
                        source_sql=src_null_sql,
                        target_sql=tgt_null_sql,
                        comparison_strategy=ComparisonStrategy.EXACT,
                        description=f"Null count: {table_mapping.source_fqn}.{cm.source_column}",
                    )
                )

        return test_cases
