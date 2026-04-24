"""PostgreSQL connector implementation."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

from datamigrate_qa.config.models import ConnectionConfig
from datamigrate_qa.models import CanonicalType, ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)

_PG_TYPE_MAP: dict[str, CanonicalType] = {
    "character varying": CanonicalType.STRING,
    "varchar": CanonicalType.STRING,
    "character": CanonicalType.STRING,
    "char": CanonicalType.STRING,
    "text": CanonicalType.STRING,
    "name": CanonicalType.STRING,
    "smallint": CanonicalType.INTEGER,
    "integer": CanonicalType.INTEGER,
    "int": CanonicalType.INTEGER,
    "int2": CanonicalType.INTEGER,
    "int4": CanonicalType.INTEGER,
    "bigint": CanonicalType.INTEGER,
    "int8": CanonicalType.INTEGER,
    "real": CanonicalType.FLOAT,
    "float4": CanonicalType.FLOAT,
    "double precision": CanonicalType.FLOAT,
    "float8": CanonicalType.FLOAT,
    "numeric": CanonicalType.NUMERIC,
    "decimal": CanonicalType.NUMERIC,
    "boolean": CanonicalType.BOOLEAN,
    "bool": CanonicalType.BOOLEAN,
    "date": CanonicalType.DATE,
    "timestamp without time zone": CanonicalType.TIMESTAMP,
    "timestamp": CanonicalType.TIMESTAMP,
    "timestamp with time zone": CanonicalType.TIMESTAMP_TZ,
    "timestamptz": CanonicalType.TIMESTAMP_TZ,
    "bytea": CanonicalType.BINARY,
    "json": CanonicalType.JSON,
    "jsonb": CanonicalType.JSON,
    "array": CanonicalType.ARRAY,
    "ARRAY": CanonicalType.ARRAY,
}


def _map_pg_type(native_type: str) -> CanonicalType:
    normalized = native_type.lower().strip()
    if normalized.startswith("character varying") or normalized.startswith("varchar"):
        return CanonicalType.STRING
    if normalized.startswith("numeric") or normalized.startswith("decimal"):
        return CanonicalType.NUMERIC
    if normalized.endswith("[]") or normalized.startswith("array"):
        return CanonicalType.ARRAY
    return _PG_TYPE_MAP.get(normalized, CanonicalType.UNKNOWN)


class PostgresConnector:
    """PostgreSQL database connector."""

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._conn: psycopg2.extensions.connection | None = None

    @property
    def dialect_name(self) -> str:
        return "postgresql"

    def connect(self) -> None:
        password = (
            self._config.password.get_secret_value()
            if self._config.password
            else None
        )
        self._conn = psycopg2.connect(
            host=self._config.host,
            port=self._config.port or 5432,
            dbname=self._config.database,
            user=self._config.username,
            password=password,
        )
        # Validate connection
        self.execute_scalar("SELECT 1")
        logger.info("Connected to PostgreSQL: %s:%s/%s", self._config.host, self._config.port, self._config.database)

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "PostgresConnector":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    def _get_conn(self) -> psycopg2.extensions.connection:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn

    def list_tables(self, schema: str) -> list[str]:
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        with self._get_conn().cursor() as cur:
            cur.execute(sql, (schema,))
            return [row[0] for row in cur.fetchall()]

    def get_table_metadata(self, schema: str, table: str) -> TableMetadata:
        columns_sql = """
            SELECT column_name, data_type, is_nullable, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        pk_sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        with self._get_conn().cursor() as cur:
            cur.execute(columns_sql, (schema, table))
            rows = cur.fetchall()
            columns = [
                ColumnMetadata(
                    name=row[0],
                    canonical_type=_map_pg_type(row[1]),
                    is_nullable=(row[2] == "YES"),
                    ordinal_position=row[3],
                    native_type=row[1],
                )
                for row in rows
            ]

            cur.execute(pk_sql, (schema, table))
            primary_keys = [row[0] for row in cur.fetchall()]

        return TableMetadata(schema=schema, table=table, columns=columns, primary_keys=primary_keys)

    def execute_scalar(self, sql: str) -> Any:
        with self._get_conn().cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else None

    def execute_query(self, sql: str, chunk_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        with self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            while True:
                rows = cur.fetchmany(chunk_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
