"""End-to-end integration tests using testcontainers (Postgres -> Postgres)."""
from __future__ import annotations

import pytest

pytest.importorskip("testcontainers", reason="testcontainers not installed")

from testcontainers.postgres import PostgresContainer  # type: ignore

from datamigrate_qa.config.models import AppConfig, ConnectionConfig, GeneratorsConfig, GeneratorOptions, TableConfig, OutputConfig
from datamigrate_qa.connectors.postgres import PostgresConnector
from datamigrate_qa.executor.runner import SequentialRunner
from datamigrate_qa.generators.base import GeneratorConfig
from datamigrate_qa.generators.row_count import RowCountGenerator
from datamigrate_qa.introspection.schema_inspector import inspect_tables
from datamigrate_qa.mapping.auto_mapper import build_mapping
from datamigrate_qa.models import TestStatus


def _create_test_data(connector: PostgresConnector) -> None:
    """Create and populate test tables."""
    conn = connector._conn
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.orders (
                id SERIAL PRIMARY KEY,
                customer_id INT NOT NULL,
                amount NUMERIC(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO public.orders (customer_id, amount)
            SELECT i, (random() * 1000)::NUMERIC(10,2)
            FROM generate_series(1, 100) i
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.customers (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE
            )
        """)
        cur.execute("""
            INSERT INTO public.customers (name, email)
            SELECT 'Customer ' || i, 'customer' || i || '@example.com'
            FROM generate_series(1, 50) i
        """)
    conn.commit()


@pytest.fixture(scope="module")
def postgres_pair():
    """Spin up two Postgres containers."""
    with PostgresContainer("postgres:16") as source_pg, \
         PostgresContainer("postgres:16") as target_pg:

        src_config = ConnectionConfig(
            dialect="postgresql",
            host=source_pg.get_container_host_ip(),
            port=int(source_pg.get_exposed_port(5432)),
            database=source_pg.dbname,
            username=source_pg.username,
            password=source_pg.password,
        )
        tgt_config = ConnectionConfig(
            dialect="postgresql",
            host=target_pg.get_container_host_ip(),
            port=int(target_pg.get_exposed_port(5432)),
            database=target_pg.dbname,
            username=target_pg.username,
            password=target_pg.password,
        )
        yield src_config, tgt_config


@pytest.fixture
def connected_pair(postgres_pair):
    src_config, tgt_config = postgres_pair
    src = PostgresConnector(src_config)
    tgt = PostgresConnector(tgt_config)
    src.connect()
    tgt.connect()
    _create_test_data(src)
    _create_test_data(tgt)
    yield src, tgt
    src.disconnect()
    tgt.disconnect()


def test_row_count_pass(connected_pair) -> None:
    """Row counts should match when both DBs have identical data."""
    src, tgt = connected_pair
    tables = [
        TableConfig(source="public.orders", target="public.orders"),
        TableConfig(source="public.customers", target="public.customers"),
    ]
    inspection = inspect_tables(src, tgt, tables)
    migration_mapping = build_mapping(tables, inspection.source_metadata, inspection.target_metadata)

    gen = RowCountGenerator()
    cases = gen.generate(migration_mapping, GeneratorConfig(options=GeneratorOptions()))

    runner = SequentialRunner(src, tgt)
    results = runner.run(cases)

    assert len(results) == 2
    assert all(r.status == TestStatus.PASS for r in results), [r.diff for r in results]


def test_row_count_fail_on_mismatch(connected_pair) -> None:
    """Row count should FAIL when tables have different counts."""
    src, tgt = connected_pair
    # Insert extra row only in source
    with src._conn.cursor() as cur:
        cur.execute("INSERT INTO public.orders (customer_id, amount) VALUES (999, 1.00)")
    src._conn.commit()

    tables = [TableConfig(source="public.orders", target="public.orders")]
    inspection = inspect_tables(src, tgt, tables)
    migration_mapping = build_mapping(tables, inspection.source_metadata, inspection.target_metadata)

    gen = RowCountGenerator()
    cases = gen.generate(migration_mapping, GeneratorConfig(options=GeneratorOptions()))

    runner = SequentialRunner(src, tgt)
    results = runner.run(cases)

    assert results[0].status == TestStatus.FAIL
    assert results[0].source_value != results[0].target_value


def test_postgres_connector_list_tables(connected_pair) -> None:
    """list_tables should return the tables we created."""
    src, _ = connected_pair
    tables = src.list_tables("public")
    assert "orders" in tables
    assert "customers" in tables


def test_postgres_connector_get_metadata(connected_pair) -> None:
    """get_table_metadata should return correct PKs and columns."""
    src, _ = connected_pair
    meta = src.get_table_metadata("public", "orders")
    assert meta.table == "orders"
    assert "id" in meta.primary_keys
    col_names = [c.name for c in meta.columns]
    assert "id" in col_names
    assert "amount" in col_names
