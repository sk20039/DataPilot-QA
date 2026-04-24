"""Snowflake connector stub — requires snowflake-connector-python."""
from __future__ import annotations

from typing import Any, Iterator

from datamigrate_qa.config.models import ConnectionConfig
from datamigrate_qa.models import CanonicalType, ColumnMetadata, TableMetadata


_SF_TYPE_MAP: dict[str, CanonicalType] = {
    "text": CanonicalType.STRING,
    "varchar": CanonicalType.STRING,
    "char": CanonicalType.STRING,
    "string": CanonicalType.STRING,
    "fixed": CanonicalType.NUMERIC,
    "number": CanonicalType.NUMERIC,
    "decimal": CanonicalType.NUMERIC,
    "numeric": CanonicalType.NUMERIC,
    "int": CanonicalType.INTEGER,
    "integer": CanonicalType.INTEGER,
    "bigint": CanonicalType.INTEGER,
    "smallint": CanonicalType.INTEGER,
    "tinyint": CanonicalType.INTEGER,
    "byteint": CanonicalType.INTEGER,
    "float": CanonicalType.FLOAT,
    "float4": CanonicalType.FLOAT,
    "float8": CanonicalType.FLOAT,
    "double": CanonicalType.FLOAT,
    "real": CanonicalType.FLOAT,
    "boolean": CanonicalType.BOOLEAN,
    "date": CanonicalType.DATE,
    "timestamp_ntz": CanonicalType.TIMESTAMP,
    "timestamp_ltz": CanonicalType.TIMESTAMP_TZ,
    "timestamp_tz": CanonicalType.TIMESTAMP_TZ,
    "binary": CanonicalType.BINARY,
    "varbinary": CanonicalType.BINARY,
    "variant": CanonicalType.JSON,
    "object": CanonicalType.JSON,
    "array": CanonicalType.ARRAY,
}


def _map_sf_type(native_type: str) -> CanonicalType:
    normalized = native_type.lower().strip()
    return _SF_TYPE_MAP.get(normalized, CanonicalType.UNKNOWN)


class SnowflakeConnector:
    """Snowflake database connector (requires snowflake-connector-python)."""

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._conn: Any = None

    @property
    def dialect_name(self) -> str:
        return "snowflake"

    def connect(self) -> None:
        try:
            import snowflake.connector
        except ImportError as e:
            raise ImportError("Install snowflake: pip install 'datamigrate-qa[snowflake]'") from e

        password = self._config.password.get_secret_value() if self._config.password else None
        self._conn = snowflake.connector.connect(
            account=self._config.account,
            user=self._config.username,
            password=password,
            database=self._config.database,
            schema=self._config.schema_,
        )
        self.execute_scalar("SELECT 1")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SnowflakeConnector":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    def _parse_fqn(self, fqn: str) -> tuple[str, str, str]:
        """Parse DB.SCHEMA.TABLE or SCHEMA.TABLE."""
        parts = fqn.upper().split(".")
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return self._config.database or "", parts[0], parts[1]
        return self._config.database or "", self._config.schema_ or "PUBLIC", parts[0]

    def list_tables(self, schema: str) -> list[str]:
        sql = f"SHOW TABLES IN SCHEMA {schema.upper()}"
        with self._conn.cursor() as cur:
            cur.execute(sql)
            return [row[1] for row in cur.fetchall()]

    def get_table_metadata(self, schema: str, table: str) -> TableMetadata:
        db, sch, tbl = self._parse_fqn(f"{schema}.{table}")
        cols_sql = f"""
            SELECT column_name, data_type, is_nullable, ordinal_position
            FROM {db}.information_schema.columns
            WHERE table_schema = '{sch}' AND table_name = '{tbl}'
            ORDER BY ordinal_position
        """
        with self._conn.cursor() as cur:
            cur.execute(cols_sql)
            rows = cur.fetchall()
            columns = [
                ColumnMetadata(
                    name=row[0].lower(),
                    canonical_type=_map_sf_type(row[1]),
                    is_nullable=(row[2] == "YES"),
                    ordinal_position=row[3],
                    native_type=row[1],
                )
                for row in rows
            ]
        return TableMetadata(schema=schema, table=table, columns=columns, primary_keys=[])

    def execute_scalar(self, sql: str) -> Any:
        with self._conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else None

    def execute_query(self, sql: str, chunk_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        with self._conn.cursor(snowflake.connector.DictCursor) as cur:
            cur.execute(sql)
            while True:
                rows = cur.fetchmany(chunk_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
