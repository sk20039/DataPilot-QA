"""Oracle connector stub — requires oracledb package."""
from __future__ import annotations

from typing import Any, Iterator

from datamigrate_qa.config.models import ConnectionConfig
from datamigrate_qa.models import CanonicalType, ColumnMetadata, TableMetadata


_ORA_TYPE_MAP: dict[str, CanonicalType] = {
    "varchar2": CanonicalType.STRING,
    "nvarchar2": CanonicalType.STRING,
    "char": CanonicalType.STRING,
    "nchar": CanonicalType.STRING,
    "clob": CanonicalType.STRING,
    "nclob": CanonicalType.STRING,
    "number": CanonicalType.NUMERIC,
    "float": CanonicalType.FLOAT,
    "binary_float": CanonicalType.FLOAT,
    "binary_double": CanonicalType.FLOAT,
    "date": CanonicalType.TIMESTAMP,  # Oracle DATE includes time component
    "timestamp": CanonicalType.TIMESTAMP,
    "timestamp with time zone": CanonicalType.TIMESTAMP_TZ,
    "timestamp with local time zone": CanonicalType.TIMESTAMP_TZ,
    "raw": CanonicalType.BINARY,
    "blob": CanonicalType.BINARY,
    "xmltype": CanonicalType.JSON,
}


def _map_ora_type(native_type: str) -> CanonicalType:
    normalized = native_type.lower().strip()
    # NUMBER(p,s), NUMBER(p), NUMBER
    if normalized.startswith("number"):
        if "," in normalized:
            return CanonicalType.NUMERIC
        return CanonicalType.INTEGER if normalized == "number" or "0" in normalized else CanonicalType.NUMERIC
    if normalized.startswith("varchar2") or normalized.startswith("nvarchar2"):
        return CanonicalType.STRING
    if normalized.startswith("timestamp"):
        if "time zone" in normalized:
            return CanonicalType.TIMESTAMP_TZ
        return CanonicalType.TIMESTAMP
    return _ORA_TYPE_MAP.get(normalized, CanonicalType.UNKNOWN)


class OracleConnector:
    """Oracle database connector (requires oracledb package)."""

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._conn: Any = None

    @property
    def dialect_name(self) -> str:
        return "oracle"

    def connect(self) -> None:
        try:
            import oracledb
        except ImportError as e:
            raise ImportError("Install oracledb: pip install 'datamigrate-qa[oracle]'") from e

        password = self._config.password.get_secret_value() if self._config.password else None
        dsn = f"{self._config.host}:{self._config.port or 1521}/{self._config.database}"
        self._conn = oracledb.connect(user=self._config.username, password=password, dsn=dsn)
        self.execute_scalar("SELECT 1 FROM DUAL")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "OracleConnector":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    def list_tables(self, schema: str) -> list[str]:
        sql = "SELECT table_name FROM all_tables WHERE owner = :schema ORDER BY table_name"
        with self._conn.cursor() as cur:
            cur.execute(sql, schema=schema.upper())
            return [row[0] for row in cur.fetchall()]

    def get_table_metadata(self, schema: str, table: str) -> TableMetadata:
        cols_sql = """
            SELECT column_name, data_type, nullable, column_id
            FROM all_tab_columns
            WHERE owner = :schema AND table_name = :table
            ORDER BY column_id
        """
        pk_sql = """
            SELECT cols.column_name
            FROM all_constraints cons
            JOIN all_cons_columns cols ON cons.constraint_name = cols.constraint_name
              AND cons.owner = cols.owner
            WHERE cons.constraint_type = 'P'
              AND cons.owner = :schema
              AND cons.table_name = :table
            ORDER BY cols.position
        """
        with self._conn.cursor() as cur:
            cur.execute(cols_sql, schema=schema.upper(), table=table.upper())
            rows = cur.fetchall()
            columns = [
                ColumnMetadata(
                    name=row[0].lower(),
                    canonical_type=_map_ora_type(row[1]),
                    is_nullable=(row[2] == "Y"),
                    ordinal_position=row[3],
                    native_type=row[1],
                )
                for row in rows
            ]
            cur.execute(pk_sql, schema=schema.upper(), table=table.upper())
            primary_keys = [row[0].lower() for row in cur.fetchall()]

        return TableMetadata(schema=schema, table=table, columns=columns, primary_keys=primary_keys)

    def execute_scalar(self, sql: str) -> Any:
        with self._conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else None

    def execute_query(self, sql: str, chunk_size: int = 10_000) -> Iterator[list[dict[str, Any]]]:
        with self._conn.cursor() as cur:
            cur.execute(sql)
            cols = [desc[0].lower() for desc in cur.description]
            while True:
                rows = cur.fetchmany(chunk_size)
                if not rows:
                    break
                yield [dict(zip(cols, row)) for row in rows]
