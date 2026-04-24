"""MySQL connector — requires PyMySQL."""
from __future__ import annotations

import logging
from typing import Any, Iterator

from datamigrate_qa.config.models import ConnectionConfig
from datamigrate_qa.models import CanonicalType, ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)

_MYSQL_TYPE_MAP: dict[str, CanonicalType] = {
    # integers
    "tinyint": CanonicalType.INTEGER,
    "smallint": CanonicalType.INTEGER,
    "mediumint": CanonicalType.INTEGER,
    "int": CanonicalType.INTEGER,
    "integer": CanonicalType.INTEGER,
    "bigint": CanonicalType.INTEGER,
    # floats
    "float": CanonicalType.FLOAT,
    "double": CanonicalType.FLOAT,
    "double precision": CanonicalType.FLOAT,
    "real": CanonicalType.FLOAT,
    # numeric
    "decimal": CanonicalType.NUMERIC,
    "numeric": CanonicalType.NUMERIC,
    "dec": CanonicalType.NUMERIC,
    # strings
    "char": CanonicalType.STRING,
    "varchar": CanonicalType.STRING,
    "tinytext": CanonicalType.STRING,
    "text": CanonicalType.STRING,
    "mediumtext": CanonicalType.STRING,
    "longtext": CanonicalType.STRING,
    "enum": CanonicalType.STRING,
    "set": CanonicalType.STRING,
    # boolean
    "bit": CanonicalType.BOOLEAN,
    "bool": CanonicalType.BOOLEAN,
    "boolean": CanonicalType.BOOLEAN,
    # date / time
    "date": CanonicalType.DATE,
    "datetime": CanonicalType.TIMESTAMP,
    "timestamp": CanonicalType.TIMESTAMP_TZ,
    "time": CanonicalType.STRING,
    "year": CanonicalType.INTEGER,
    # binary
    "binary": CanonicalType.BINARY,
    "varbinary": CanonicalType.BINARY,
    "tinyblob": CanonicalType.BINARY,
    "blob": CanonicalType.BINARY,
    "mediumblob": CanonicalType.BINARY,
    "longblob": CanonicalType.BINARY,
    # json
    "json": CanonicalType.JSON,
}


def _map_mysql_type(native_type: str) -> CanonicalType:
    # Strip display widths / lengths e.g. "int(11)" → "int", "varchar(255)" → "varchar"
    base = native_type.lower().split("(")[0].strip()
    return _MYSQL_TYPE_MAP.get(base, CanonicalType.UNKNOWN)


class MySQLConnector:
    """MySQL database connector (requires PyMySQL)."""

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._conn: Any = None

    @property
    def dialect_name(self) -> str:
        return "mysql"

    def connect(self) -> None:
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as e:
            raise ImportError(
                "Install MySQL support: pip install 'datamigrate-qa[mysql]'"
            ) from e

        password = (
            self._config.password.get_secret_value() if self._config.password else None
        )
        self._conn = pymysql.connect(
            host=self._config.host or "localhost",
            port=self._config.port or 3306,
            database=self._config.database,
            user=self._config.username,
            password=password or "",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        self.execute_scalar("SELECT 1")
        logger.info(
            "Connected to MySQL: %s:%s/%s",
            self._config.host,
            self._config.port,
            self._config.database,
        )

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "MySQLConnector":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    def _get_conn(self) -> Any:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn

    def list_tables(self, schema: str) -> list[str]:
        # In MySQL, schema == database name
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        with self._get_conn().cursor() as cur:
            cur.execute(sql, (schema,))
            return [row["table_name"] for row in cur.fetchall()]

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
             AND tc.table_name = kcu.table_name
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
                    name=row["column_name"],
                    canonical_type=_map_mysql_type(row["data_type"]),
                    is_nullable=(row["is_nullable"] == "YES"),
                    ordinal_position=row["ordinal_position"],
                    native_type=row["data_type"],
                )
                for row in rows
            ]

            cur.execute(pk_sql, (schema, table))
            primary_keys = [row["column_name"] for row in cur.fetchall()]

        return TableMetadata(
            schema=schema, table=table, columns=columns, primary_keys=primary_keys
        )

    def execute_scalar(self, sql: str) -> Any:
        with self._get_conn().cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            if row is None:
                return None
            # DictCursor returns a dict; grab the first value
            return next(iter(row.values())) if isinstance(row, dict) else row[0]

    def execute_query(self, sql: str, chunk_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        with self._get_conn().cursor() as cur:
            cur.execute(sql)
            while True:
                rows = cur.fetchmany(chunk_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
