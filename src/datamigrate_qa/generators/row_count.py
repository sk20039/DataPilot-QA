"""Row count test generator."""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)

_EXACT_COUNT_SQL = "SELECT COUNT(*) FROM {fqn}"


class RowCountGenerator:
    """Generates row count test cases for each table pair."""

    @property
    def category(self) -> str:
        return "row_count"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []

        for table_mapping in mapping.table_mappings:
            if table_mapping.skip:
                continue

            source_sql = _EXACT_COUNT_SQL.format(fqn=table_mapping.source_fqn)
            target_sql = _EXACT_COUNT_SQL.format(fqn=table_mapping.target_fqn)

            test_cases.append(
                TestCase(
                    category=self.category,
                    table_pair=TablePair(
                        source_fqn=table_mapping.source_fqn,
                        target_fqn=table_mapping.target_fqn,
                    ),
                    source_sql=source_sql,
                    target_sql=target_sql,
                    comparison_strategy=ComparisonStrategy.EXACT,
                    description=f"Row count: {table_mapping.source_fqn} vs {table_mapping.target_fqn}",
                )
            )

        logger.info("Generated %d row count test cases", len(test_cases))
        return test_cases
