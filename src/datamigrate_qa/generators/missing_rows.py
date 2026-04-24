"""Missing row detection generator.

Identifies which specific primary key values are present in the source but
absent from the target (and vice versa), giving migration engineers the exact
row IDs they need to investigate rather than just a count mismatch.
"""
from __future__ import annotations

import logging

from datamigrate_qa.mapping.mapping_model import MigrationMapping
from datamigrate_qa.models import ComparisonStrategy, TablePair, TestCase

from .base import GeneratorConfig

logger = logging.getLogger(__name__)


class MissingRowsGenerator:
    """Generates missing-row detection test cases for tables that have a primary key."""

    @property
    def category(self) -> str:
        return "missing_rows"

    def generate(self, mapping: MigrationMapping, config: GeneratorConfig) -> list[TestCase]:
        test_cases: list[TestCase] = []

        for tm in mapping.table_mappings:
            if tm.skip:
                continue
            if not tm.primary_keys:
                logger.debug(
                    "Skipping missing-rows check for %s — no primary key detected",
                    tm.source_fqn,
                )
                continue

            pk_csv = ", ".join(tm.primary_keys)
            test_cases.append(
                TestCase(
                    category=self.category,
                    table_pair=TablePair(
                        source_fqn=tm.source_fqn,
                        target_fqn=tm.target_fqn,
                    ),
                    # source_sql / target_sql carry the PK fetch queries;
                    # the runner dispatches on category="missing_rows" and
                    # diffs them in Python rather than comparing scalars.
                    source_sql=f"SELECT {pk_csv} FROM {tm.source_fqn}",
                    target_sql=f"SELECT {pk_csv} FROM {tm.target_fqn}",
                    comparison_strategy=ComparisonStrategy.EXACT,
                    description=f"Missing rows: {tm.source_fqn} \u2194 {tm.target_fqn}",
                )
            )

        logger.info("Generated %d missing-rows test cases", len(test_cases))
        return test_cases
