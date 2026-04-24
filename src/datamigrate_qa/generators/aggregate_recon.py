"""Aggregate reconciliation test generator."""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import CanonicalType, ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)

_NUMERIC_TYPES = {CanonicalType.INTEGER, CanonicalType.FLOAT, CanonicalType.NUMERIC}


class AggregateReconGenerator:
    """Generates SUM/AVG reconciliation test cases for numeric columns."""

    @property
    def category(self) -> str:
        return "aggregate_recon"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []
        tolerance = config.options.tolerance

        for table_mapping in mapping.table_mappings:
            if table_mapping.skip:
                continue

            for cm in table_mapping.mapped_columns():
                if cm.canonical_type not in _NUMERIC_TYPES:
                    logger.debug(
                        "Skipping SUM for %s.%s: non-numeric type %s",
                        table_mapping.source_fqn, cm.source_column, cm.canonical_type,
                    )
                    continue

                src_sql = f"SELECT SUM({cm.source_column}) FROM {table_mapping.source_fqn}"
                tgt_sql = f"SELECT SUM({cm.target_column}) FROM {table_mapping.target_fqn}"

                test_cases.append(
                    TestCase(
                        category=self.category,
                        table_pair=TablePair(
                            source_fqn=table_mapping.source_fqn,
                            target_fqn=table_mapping.target_fqn,
                        ),
                        source_sql=src_sql,
                        target_sql=tgt_sql,
                        comparison_strategy=ComparisonStrategy.NUMERIC_TOLERANCE,
                        tolerance=tolerance,
                        description=f"SUM reconciliation: {table_mapping.source_fqn}.{cm.source_column}",
                    )
                )

        return test_cases
