"""Tests for the auto mapper."""
from __future__ import annotations

import pytest

from datamigrate_qa.config.models import TableConfig
from datamigrate_qa.mapping.auto_mapper import build_mapping
from datamigrate_qa.models import CanonicalType, ColumnMetadata, TableMetadata


def _col(name: str) -> ColumnMetadata:
    return ColumnMetadata(
        name=name,
        canonical_type=CanonicalType.STRING,
        is_nullable=True,
        ordinal_position=1,
        native_type="varchar",
    )


def _table(schema: str, table: str, cols: list[str], pks: list[str] | None = None) -> TableMetadata:
    return TableMetadata(
        schema=schema,
        table=table,
        columns=[_col(c) for c in cols],
        primary_keys=pks or [],
    )


def test_exact_match() -> None:
    tables = [TableConfig(source="public.orders", target="public.orders")]
    src_meta = {"public.orders": _table("public", "orders", ["id", "amount"], pks=["id"])}
    tgt_meta = {"public.orders": _table("public", "orders", ["id", "amount"], pks=["id"])}

    mapping = build_mapping(tables, src_meta, tgt_meta)
    assert len(mapping.table_mappings) == 1
    tm = mapping.table_mappings[0]
    assert len(tm.mapped_columns()) == 2
    assert tm.has_primary_key


def test_case_insensitive_match() -> None:
    tables = [TableConfig(source="public.orders", target="PUBLIC.ORDERS")]
    src_meta = {"public.orders": _table("public", "orders", ["order_id"], pks=["order_id"])}
    tgt_meta = {"PUBLIC.ORDERS": _table("PUBLIC", "ORDERS", ["ORDER_ID"], pks=["ORDER_ID"])}

    mapping = build_mapping(tables, src_meta, tgt_meta)
    tm = mapping.table_mappings[0]
    assert len(tm.mapped_columns()) == 1
    assert tm.mapped_columns()[0].target_column == "ORDER_ID"


def test_no_pk_warning() -> None:
    tables = [TableConfig(source="public.logs", target="public.logs")]
    src_meta = {"public.logs": _table("public", "logs", ["msg"])}
    tgt_meta = {"public.logs": _table("public", "logs", ["msg"])}

    mapping = build_mapping(tables, src_meta, tgt_meta)
    tm = mapping.table_mappings[0]
    assert not tm.has_primary_key
    assert any("no primary key" in w.lower() for w in tm.warnings)


def test_missing_source_metadata() -> None:
    tables = [TableConfig(source="public.missing", target="public.missing")]
    mapping = build_mapping(tables, {}, {})
    assert len(mapping.table_mappings) == 0
    assert any("missing" in w for w in mapping.warnings)
