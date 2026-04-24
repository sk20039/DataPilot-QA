"""Tests for the row count generator."""
from __future__ import annotations

from datamigrate_qa.config.models import GeneratorOptions
from datamigrate_qa.generators.base import GeneratorConfig
from datamigrate_qa.generators.row_count import RowCountGenerator
from datamigrate_qa.mapping.mapping_model import MigrationMapping, TableMapping
from datamigrate_qa.models import ComparisonStrategy


def _make_mapping(*pairs: tuple[str, str]) -> MigrationMapping:
    return MigrationMapping(
        table_mappings=[
            TableMapping(source_fqn=src, target_fqn=tgt)
            for src, tgt in pairs
        ]
    )


def test_generates_one_case_per_table() -> None:
    mapping = _make_mapping(
        ("public.orders", "public.orders"),
        ("public.customers", "public.customers"),
    )
    gen = RowCountGenerator()
    config = GeneratorConfig(options=GeneratorOptions())
    cases = gen.generate(mapping, config)
    assert len(cases) == 2
    assert all(c.category == "row_count" for c in cases)


def test_sql_contains_table_names() -> None:
    mapping = _make_mapping(("public.orders", "public.orders"))
    gen = RowCountGenerator()
    config = GeneratorConfig(options=GeneratorOptions())
    cases = gen.generate(mapping, config)
    assert "public.orders" in cases[0].source_sql
    assert "COUNT(*)" in cases[0].source_sql.upper()


def test_comparison_strategy_is_exact() -> None:
    mapping = _make_mapping(("public.orders", "public.orders"))
    gen = RowCountGenerator()
    config = GeneratorConfig(options=GeneratorOptions())
    cases = gen.generate(mapping, config)
    assert cases[0].comparison_strategy == ComparisonStrategy.EXACT


def test_skipped_tables_excluded() -> None:
    mapping = MigrationMapping(
        table_mappings=[TableMapping(source_fqn="public.skip_me", target_fqn="public.skip_me", skip=True)]
    )
    gen = RowCountGenerator()
    config = GeneratorConfig(options=GeneratorOptions())
    cases = gen.generate(mapping, config)
    assert len(cases) == 0
