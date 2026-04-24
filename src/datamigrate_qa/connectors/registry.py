"""Connector registry — maps dialect names to connector classes."""
from __future__ import annotations

from datamigrate_qa.config.models import ConnectionConfig
from datamigrate_qa.connectors.base import Connector
from datamigrate_qa.connectors.postgres import PostgresConnector


def get_connector(config: ConnectionConfig) -> Connector:
    """Instantiate the appropriate connector for the given dialect."""
    dialect = config.dialect.lower()
    if dialect in ("postgresql", "postgres"):
        return PostgresConnector(config)  # type: ignore[return-value]
    if dialect == "snowflake":
        from datamigrate_qa.connectors.snowflake import SnowflakeConnector
        return SnowflakeConnector(config)  # type: ignore[return-value]
    if dialect == "oracle":
        from datamigrate_qa.connectors.oracle import OracleConnector
        return OracleConnector(config)  # type: ignore[return-value]
    if dialect in ("mysql", "mariadb"):
        from datamigrate_qa.connectors.mysql import MySQLConnector
        return MySQLConnector(config)  # type: ignore[return-value]
    raise ValueError(f"Unsupported dialect: {config.dialect!r}")
