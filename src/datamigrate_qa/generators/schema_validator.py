"""Schema validation test generator."""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)


class SchemaValidatorGenerator:
    """Generates schema comparison test cases."""

    @property
    def category(self) -> str:
        return "schema"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []

        for table_mapping in mapping.table_mappings:
            if table_mapping.skip:
                continue

            # Generate a test case that captures column count comparison
            source_sql = f"""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = '{table_mapping.source_fqn.split('.')[0]}'
                  AND table_name = '{table_mapping.source_fqn.split('.')[1]}'
            """
            target_sql = f"""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = '{table_mapping.target_fqn.split('.')[0]}'
                  AND table_name = '{table_mapping.target_fqn.split('.')[1]}'
            """
            test_cases.append(
                TestCase(
                    category=self.category,
                    table_pair=TablePair(
                        source_fqn=table_mapping.source_fqn,
                        target_fqn=table_mapping.target_fqn,
                    ),
                    source_sql=source_sql.strip(),
                    target_sql=target_sql.strip(),
                    comparison_strategy=ComparisonStrategy.EXACT,
                    description=f"Schema column count: {table_mapping.source_fqn} vs {table_mapping.target_fqn}",
                )
            )

        return test_cases
